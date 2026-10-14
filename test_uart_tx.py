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

    # The final wait allows registered outputs to update before we read them.
    # One complete cycle lasts 20 ns, corresponding to a 50 MHz clock. 

# Helper: Check that the transmitter remains available between frames.
async def check_idle(dut, cycles=5):
    """Verify that TX stays idle and no unexpected frame starts."""
    for cycle in range(cycles):
        await clock_cycle(dut)

        # An idle UART line is high; an available transmitter has busy low.
        assert int(dut.tx.value) == 1, f"Idle cycle {cycle}: TX must be high"
        assert int(dut.busy.value) == 0, f"Idle cycle {cycle}: busy must be low"

# Helper: Place the transmitter in a known initial state.
async def reset_tx(dut):
    """Initialize inputs and apply the synchronous reset for five clock cycles."""
    dut.clk.value = 0
    dut.reset.value = 1
    dut.send.value = 0
    dut.data_in.value = 0

    # Synchronous reset takes effect on each rising clock edge.
    # Verify the outputs after every reset cycle.
    for _ in range(5):
        await clock_cycle(dut)
        assert int(dut.tx.value) == 1, "TX must be high during reset"
        assert int(dut.busy.value) == 0, "TX must not be busy during reset"

    # Release reset and let the transmitter execute one normal cycle.
    dut.reset.value = 0
    await clock_cycle(dut)

# Helper: Send a byte and compare its serial output against an expected frame.
async def transmit_and_check(dut, byte, busy_request=False):
    """Request one byte and verify every clock sample of its 8N1 frame."""
    assert int(dut.busy.value) == 0, "TX must be idle before requesting"

    # Build the frame: start bit (0), eight data bits, and stop bit (1).
    # Shift each data bit into position 0, then mask with & 1 to extract it.
    # Iterating from bit 0 to bit 7 produces UART's LSB-first ordering.
    expected_frame = ([0] + [(byte >> bit) & 1 for bit in range(8)] + [1])

    # Present the byte and assert send for exactly one rising clock edge.
    dut.data_in.value = byte
    dut.send.value = 1
    await clock_cycle(dut)
    dut.send.value = 0

    # XOR with 0xFF flips all eight bits.
    # Changing the input must not change the byte already captured by TX.
    dut.data_in.value = byte ^ 0xFF

    # An 8N1 frame has ten bits, each lasting CLKS_PER_BIT clock cycles.
    total_samples = 10 * CLKS_PER_BIT

    # Sample 3 * CLKS_PER_BIT is the beginning of data bit 2.
    # Optionally inject another request here, while TX is busy.
    request_sample = 3 * CLKS_PER_BIT

    for sample in range(total_samples):
        # The initial request cycle already produced start-bit sample 0.
        # Advance the clock only before subsequent samples.
        if sample > 0:
            if busy_request and sample == request_sample:
                dut.data_in.value = byte ^ 0xFF
                dut.send.value = 1

            elif busy_request and sample == request_sample + 1:
                dut.send.value = 0 # Remove the injected request after one clock cycle.

            await clock_cycle(dut)

        # Integer division identifies the frame bit (0 through 9).
        # The remainder identifies the clock position within that bit.
        frame_bit = sample // CLKS_PER_BIT
        cycle_in_bit = sample % CLKS_PER_BIT

        expected = expected_frame[frame_bit]
        actual = int(dut.tx.value)

        # Check both the serial value and busy on every clock cycle.
        # Include the byte, bit, and cycle to make failures easier to locate.
        assert actual == expected, (
            f"Byte 0x{byte:02X}, frame bit {frame_bit}, "
            f"cycle {cycle_in_bit}: expected TX={expected}, got {actual}"
        )
        assert int(dut.busy.value) == 1, f"Byte 0x{byte:02X}: busy dropped at sample {sample}"

    # Advance to the edge that completes the full stop-bit period.
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

# Test: Exhaustively verify the transmitter's eight-bit data values.
@cocotb.test()
async def transmit_all_byte_values(dut):
    """Verify every possible 8-bit value."""
    await reset_tx(dut)

    # range(256) produces 0 through 255, including 0x55 and 0xAA.
    for byte in range(256):
        await transmit_and_check(dut, byte)
        await check_idle(dut, cycles=2) # Verify idle behavior for two clock cycles between frames.

# Test: A request during transmission must be discarded.
@cocotb.test()
async def ignore_send_while_busy(dut):
    """A send pulse during a frame neither corrupts nor queues data."""
    await reset_tx(dut)

    # The helper injects a request for 0xAA while transmitting 0x55.
    # It verifies that the entire original frame remains correct.
    await transmit_and_check(dut, 0x55, busy_request=True)

    # Observe idle for a full frame duration.
    # Any queued transmission would cause TX or busy to violate idle.
    await check_idle(dut, cycles=10 * CLKS_PER_BIT)

    # A fresh request made while idle must still be accepted.
    await transmit_and_check(dut, 0xAA)
    await check_idle(dut)

# Test: Reset must interrupt a frame and allow normal operation afterward.
@cocotb.test()
async def reset_during_transmission(dut):
    """Reset interrupts a frame and allows a fresh transmission."""
    # Each offset counts additional clock cycles after the request edge.
    # These offsets place the reset within three different frame regions.
    abort_points = [
        ("start", CLKS_PER_BIT // 2),
        ("data", 4 * CLKS_PER_BIT),
        ("stop", 9 * CLKS_PER_BIT + CLKS_PER_BIT // 2),
    ]

    for stage, elapsed_cycles in abort_points:
        await reset_tx(dut) # Start each reset scenario from a known state.

        dut.data_in.value = 0x55
        dut.send.value = 1
        await clock_cycle(dut)
        dut.send.value = 0

        # Advance into the selected region of the active frame.
        for _ in range(elapsed_cycles):
            await clock_cycle(dut)

        assert int(dut.busy.value) == 1, f"TX must still be busy before resetting during {stage}"

        # Assert synchronous reset and check its effect after one rising edge.
        dut.reset.value = 1
        await clock_cycle(dut)

        assert int(dut.tx.value) == 1, f"Reset during {stage} must restore TX high"
        assert int(dut.busy.value) == 0, f"Reset during {stage} must clear busy"

        # Release reset and verify that TX remains idle before the next request.
        dut.reset.value = 0
        await check_idle(dut)

        # Verify a complete new frame to check recovery of timing and data state.
        await transmit_and_check(dut, 0xA6)
        await check_idle(dut)

# Test: Send multiple frames with the minimum gap supported by this interface.
@cocotb.test()
async def consecutive_transmissions(dut):
    """Request each new byte immediately after busy clears."""
    await reset_tx(dut)

    for byte in [0x00, 0xFF, 0x55, 0xAA, 0x41]:
        # The helper returns immediately after the stop bit completes.
        # The next call presents send before the next rising edge.
        # This produces one system-clock cycle of idle time between frames.
        await transmit_and_check(dut, byte)

    await check_idle(dut) # After the final frame, TX should remain idle.