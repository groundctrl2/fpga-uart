"""UART TX verification: byte coverage, busy requests, reset, and consecutive frames."""

import cocotb
from cocotb.triggers import Timer

# Match the transmitter's (uart_tx.sv) default timing parameter.
# At 50 MHz, 434 clocks per bit gives a baud rate of 115,207 (50M/434).
CLKS_PER_BIT = 434

# Helper: Advance the simulation by one system-clock cycle.
async def clock_cycle(dut):
    """Generate one 20 ns clock cycle and allow outputs to settle."""
    dut.clk.value = 0 # Drive the clock low for 10 ns.
    await Timer(10, unit="ns")
    dut.clk.value = 1 # Drive the clock high for 10 ns.
    await Timer(10, unit="ns")

    # Wait after the rising edge so outputs update before we read them.
    # Each full clock cycle is 20 ns (50 MHz).

# Helper: Check that TX stays idle and ready.
async def check_idle(dut, cycles=5):
    """Verify that TX stays idle and no unexpected frame starts."""
    for cycle in range(cycles):
        await clock_cycle(dut)

        # An idle UART line is high; an available transmitter has busy low.
        assert int(dut.tx.value) == 1, f"Idle cycle {cycle}: TX must be high"
        assert int(dut.busy.value) == 0, f"Idle cycle {cycle}: busy must be low"

# Helper: Place the transmitter in a known initial state.
async def reset_tx(dut):
    """Set starting inputs and hold reset high for five clocks."""
    dut.clk.value = 0
    dut.reset.value = 1
    dut.send.value = 0
    dut.data_in.value = 0

    # Reset takes effect on rising clock edges. Check outputs after each one.
    for _ in range(5):
        await clock_cycle(dut)
        assert int(dut.tx.value) == 1, "TX must be high during reset"
        assert int(dut.busy.value) == 0, "TX must not be busy during reset"

    # Turn reset off and advance one clock.
    dut.reset.value = 0
    await clock_cycle(dut)

# Helper: Send a byte and check its start, data, and stop bits.
async def transmit_and_check(dut, byte, busy_request=False):
    """Send one byte and check TX and busy every clock."""
    assert int(dut.busy.value) == 0, "TX must be idle before requesting"

    # Expected frame: start (0), data bits 0 through 7, then stop (1).
    # (byte >> bit) & 1 extracts one bit, starting with the lowest bit.
    expected_frame = ([0] + [(byte >> bit) & 1 for bit in range(8)] + [1])

    # Set the byte and hold send high for one clock.
    dut.data_in.value = byte
    dut.send.value = 1
    await clock_cycle(dut)
    dut.send.value = 0

    # XOR with 0xFF flips all eight bits.
    # TX must keep sending the byte it already saved.
    dut.data_in.value = byte ^ 0xFF

    # An 8N1 frame has ten bits, each lasting CLKS_PER_BIT clock cycles.
    total_samples = 10 * CLKS_PER_BIT

    # If busy_request is True, request another byte when data bit 2 begins.
    request_sample = 3 * CLKS_PER_BIT

    for sample in range(total_samples):
        # The request clock already gave us sample 0.
        # Advance one clock before each remaining sample.
        if sample > 0:
            if busy_request and sample == request_sample:
                dut.data_in.value = byte ^ 0xFF
                dut.send.value = 1

            elif busy_request and sample == request_sample + 1:
                dut.send.value = 0 # End the extra request after one clock.

            await clock_cycle(dut)

        # Integer division tells us which frame bit we are checking (0-9).
        # The remainder tells us how many clocks into that bit we are.
        frame_bit = sample // CLKS_PER_BIT
        cycle_in_bit = sample % CLKS_PER_BIT

        expected = expected_frame[frame_bit]
        actual = int(dut.tx.value)

        # Check TX and busy every clock.
        # Error messages identify the byte, frame bit, and clock where a check failed.
        assert actual == expected, (
            f"Byte 0x{byte:02X}, frame bit {frame_bit}, "
            f"cycle {cycle_in_bit}: expected TX={expected}, got {actual}"
        )
        assert int(dut.busy.value) == 1, f"Byte 0x{byte:02X}: busy dropped at sample {sample}"

    # Advance one more clock to finish the stop bit.
    await clock_cycle(dut)
    assert int(dut.tx.value) == 1, "TX must be high after the frame"
    assert int(dut.busy.value) == 0, "busy must clear after the frame"

# Test: Reset leaves TX idle, with no transmission requested.
@cocotb.test()
async def tx_idle_after_reset(dut):
    """Check that TX remains idle-high when no transmission is requested."""
    await reset_tx(dut)
    await check_idle(dut)

# Test: Verify a known byte using the reusable frame checker.
@cocotb.test()
async def transmit_ascii_a(dut):
    """Verify the start, data, and stop bits for ASCII 'A'."""
    await reset_tx(dut)
    await transmit_and_check(dut, 0x41) # ASCII 'A' = 0x41 = 01000001.
    await check_idle(dut) # No further frame should start without another request.

# Test: Send and check all 256 possible bytes.
@cocotb.test()
async def transmit_all_byte_values(dut):
    """Verify every possible 8-bit value."""
    await reset_tx(dut)

    # range(256) produces 0 through 255, including 0x55 and 0xAA.
    for byte in range(256):
        await transmit_and_check(dut, byte)
        await check_idle(dut, cycles=2) # Check two idle clocks between frames.

# Test: Ignore a new send request while busy.
@cocotb.test()
async def ignore_send_while_busy(dut):
    """An extra request must not change the current frame or start another later."""
    await reset_tx(dut)

    # Request 0xAA while sending 0x55, and check that 0x55 is sent correctly.
    await transmit_and_check(dut, 0x55, busy_request=True)

    # Stay idle for as long as a full frame takes.
    # This checks that the ignored request does not start a delayed transmission.
    await check_idle(dut, cycles=10 * CLKS_PER_BIT)

    # Check that a new request works once TX is idle.
    await transmit_and_check(dut, 0xAA)
    await check_idle(dut)

# Test: Reset must interrupt a frame and allow normal operation afterward.
@cocotb.test()
async def reset_during_transmission(dut):
    """Reset interrupts a frame and allows a fresh transmission."""
    # Clocks to wait after the send request before resetting.
    # Try reset during the start bit, data bits, and stop bit.
    abort_points = [
        ("start", CLKS_PER_BIT // 2),
        ("data", 4 * CLKS_PER_BIT),
        ("stop", 9 * CLKS_PER_BIT + CLKS_PER_BIT // 2),
    ]

    for stage, elapsed_cycles in abort_points:
        await reset_tx(dut) # Start each case with a reset.

        dut.data_in.value = 0x55
        dut.send.value = 1
        await clock_cycle(dut)
        dut.send.value = 0

        # Wait until the chosen part of the frame.
        for _ in range(elapsed_cycles):
            await clock_cycle(dut)

        assert int(dut.busy.value) == 1, f"TX must still be busy before resetting during {stage}"

        # Turn reset on and advance one clock to apply it.
        dut.reset.value = 1
        await clock_cycle(dut)

        assert int(dut.tx.value) == 1, f"Reset during {stage} must restore TX high"
        assert int(dut.busy.value) == 0, f"Reset during {stage} must clear busy"

        # Turn reset off and check that TX stays idle.
        dut.reset.value = 0
        await check_idle(dut)

        # Send another byte to check that TX works after reset.
        await transmit_and_check(dut, 0xA6)
        await check_idle(dut)

# Test: Request the next byte as soon as busy goes low.
@cocotb.test()
async def consecutive_transmissions(dut):
    """Request each new byte immediately after busy clears."""
    await reset_tx(dut)

    for byte in [0x00, 0xFF, 0x55, 0xAA, 0x41]:
        # Each call finishes when busy goes low.
        # Set send before the next rising edge, leaving one idle clock between frames.
        await transmit_and_check(dut, byte)

    await check_idle(dut) # After the final frame, TX should remain idle.