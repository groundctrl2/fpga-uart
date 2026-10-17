"""UART RX verification: bytes, false starts, framing errors, reset, and timing."""

import cocotb
from cocotb.triggers import Timer, RisingEdge

# Use the same clocks-per-bit setting as uart_rx.sv.
# At 50 MHz, each clock is 20 ns and each bit lasts 8680 ns.
CLKS_PER_BIT = 434
CLOCK_NS = 20
BIT_NS = CLKS_PER_BIT * CLOCK_NS

# Helper: Run the system clock continuously.
async def run_clock(dut):
    """Generate a 50 MHz clock until the test ends."""
    while True:
        dut.clk.value = 0
        await Timer(CLOCK_NS // 2, unit="ns") # Keep the clock low for 10 ns.
        dut.clk.value = 1
        await Timer(CLOCK_NS // 2, unit="ns") # Keep the clock high for 10 ns.

# Helper: Wait a set number of clocks.
async def wait_clocks(cycles):
    """Wait while the background clock keeps running."""
    await Timer(cycles * CLOCK_NS, unit="ns")

# Helper: Reset the receiver before testing.
async def reset_rx(dut):
    """Reset RX while keeping its input high (idle)."""
    dut.reset.value = 1
    dut.rx.value = 1

    # Reset takes effect on rising clock edges.
    for _ in range(5):
        await wait_clocks(1)
        assert int(dut.data_out.value) == 0, "Reset must clear data_out"
        assert int(dut.data_valid.value) == 0, "Reset must clear data_valid"
        assert int(dut.framing_error.value) == 0, "Reset must clear framing_error"

    # Turn reset off and allow the receiver to return to waiting (wait 5 clocks).
    dut.reset.value = 0
    await wait_clocks(5)

# Helper: Check the outputs while the test sends data.
async def monitor_rx(dut, received, errors=None):
    """Collect received bytes and check the outputs every clock."""
    previous_valid = 0
    previous_error = 0
    previous_data = int(dut.data_out.value)

    while True:
        # Read 1 ns after each rising edge so outputs have time to update.
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        valid = int(dut.data_valid.value)
        error = int(dut.framing_error.value)
        data = int(dut.data_out.value)

        if int(dut.reset.value):
            # Reset clears the outputs, even during an unfinished frame.
            assert data == 0, "Reset must clear data_out"
            assert valid == 0, "Reset must clear data_valid"
            assert error == 0, "Reset must clear framing_error"
        else:
            # Both result signals must last only one clock.
            assert not (valid and previous_valid), "data_valid lasted longer than one clock"
            assert not (error and previous_error), "framing_error lasted longer than one clock"
            assert not (valid and error), "Both result signals were high together"

            if error:
                # Most tests reject errors. The framing test records them.
                assert errors is not None, "Unexpected framing error"
                errors.append(data)

            if valid:
                received.append(data)
            else:
                # An error must also leave the last accepted byte unchanged.
                assert data == previous_data, "data_out changed without data_valid"

        previous_valid = valid
        previous_error = error
        previous_data = data

# Helper: Start the clock, reset RX, and start the output monitor.
async def setup_rx(dut, errors=None):
    """Start the clock, reset RX, and begin watching its outputs."""
    dut.clk.value = 0
    dut.reset.value = 1
    dut.rx.value = 1

    cocotb.start_soon(run_clock(dut))
    await reset_rx(dut)

    received = []
    cocotb.start_soon(monitor_rx(dut, received, errors))

    # Start sending between clock edges, like an outside device could.
    await Timer(3, unit="ns")
    return received

# Helper: Send a UART frame using Python instead of uart_tx.sv.
async def send_serial_byte(dut, byte, bit_ns=BIT_NS, stop_bit=1):
    """Send a start bit, eight data bits, and a chosen stop bit."""
    frame = [0] + [(byte >> bit) & 1 for bit in range(8)] + [stop_bit]

    # Set RX to each bit and wait one bit period.
    # The receiver's clock keeps running while we wait.
    for bit in frame:
        dut.rx.value = bit
        await Timer(bit_ns, unit="ns")

    # Return to idle, including after an incorrect stop bit.
    dut.rx.value = 1

# Helper: Send one byte and check what RX received.
async def receive_and_check(dut, received, byte):
    """Check that RX reports the sent byte exactly once."""
    before = len(received)
    await send_serial_byte(dut, byte)

    # Give RX and the monitor 5 extra clocks to finish.
    await wait_clocks(5)

    actual = received[before:]
    assert actual == [byte], (
        f"Sent 0x{byte:02X}: expected one matching byte, got {actual}"
    )

# Test: RX must not report a byte when no data is sent.
@cocotb.test()
async def rx_idle_after_reset(dut):
    """Check that an idle input produces no received bytes."""
    received = await setup_rx(dut)

    # Wait as long as a complete frame takes.
    await wait_clocks(10 * CLKS_PER_BIT)

    assert received == [], "Idle RX must not report a byte"
    assert int(dut.data_out.value) == 0, "data_out must stay zero before the first byte"

# Test: Send a known byte and check that RX receives it.
@cocotb.test()
async def receive_ascii_a(dut):
    """Check that RX receives ASCII 'A'."""
    received = await setup_rx(dut)

    await receive_and_check(dut, received, 0x41) # ASCII 'A'.

    # No extra byte should appear after the frame.
    await wait_clocks(10 * CLKS_PER_BIT)
    assert received == [0x41], f"Unexpected received bytes: {received}"

# Test: Send and check all 256 possible bytes.
@cocotb.test()
async def receive_all_byte_values(dut):
    """Verify every possible 8-bit value."""
    received = await setup_rx(dut)

    for byte in range(256):
        await receive_and_check(dut, received, byte)

    # Check that nothing extra appears after the last frame.
    await wait_clocks(10 * CLKS_PER_BIT)
    assert received == list(range(256)), "Received byte sequence did not match"

# Test: Ignore a short low pulse that is not a full start bit.
@cocotb.test()
async def reject_false_start(dut):
    """Reject short low pulses and receive a valid frame afterward."""
    received = await setup_rx(dut)

    # Try several low pulses shorter than half a bit.
    for low_clocks in [1, CLKS_PER_BIT // 8, CLKS_PER_BIT // 4]:
        dut.rx.value = 0
        await wait_clocks(low_clocks)
        dut.rx.value = 1

        # Wait long enough to catch a wrongly accepted frame.
        await wait_clocks(10 * CLKS_PER_BIT)
        assert received == [], f"A {low_clocks}-clock low pulse produced a byte: {received}"
        assert int(dut.data_out.value) == 0, "False start changed data_out"

    # A rejected start must not prevent the next valid frame.
    await receive_and_check(dut, received, 0xA6)
    await wait_clocks(10 * CLKS_PER_BIT)
    assert received == [0xA6], f"Unexpected received bytes: {received}"

# Test: Report an incorrect stop bit and recover afterward.
@cocotb.test()
async def framing_error_and_recovery(dut):
    """Reject a bad stop bit without changing the last accepted byte."""
    errors = []
    received = await setup_rx(dut, errors)

    # Save a valid byte first so we can check that an error preserves it.
    await receive_and_check(dut, received, 0xA6)
    assert errors == [], "Valid frame caused a framing error"

    # Send a different byte with a low stop bit.
    await send_serial_byte(dut, 0x55, stop_bit=0)

    # Leave the line high long enough for RX to return to waiting.
    await wait_clocks(10 * CLKS_PER_BIT)

    assert received == [0xA6], "RX accepted a frame with a bad stop bit"
    assert errors == [0xA6], f"Expected one error preserving 0xA6, got {errors}"
    assert int(dut.data_out.value) == 0xA6, "Bad frame changed data_out"

    # A valid frame must still work after the error.
    await receive_and_check(dut, received, 0x3C)
    await wait_clocks(10 * CLKS_PER_BIT)

    assert received == [0xA6, 0x3C], f"Unexpected received bytes: {received}"
    assert errors == [0xA6], "Unexpected extra framing error"

# Test: Reset must discard an unfinished frame.
@cocotb.test()
async def reset_during_reception(dut):
    """Reset during the start, data, and stop bits, then receive again."""
    received = await setup_rx(dut)

    # Times measured from the beginning of the incoming start bit.
    # Reset early in the stop bit, before RX checks its midpoint.
    abort_points = [
        ("start", BIT_NS // 4),
        ("data", 4 * BIT_NS),
        ("stop", 9 * BIT_NS + BIT_NS // 4),
    ]

    for stage, delay_ns in abort_points:
        # Begin each case with a previously accepted byte.
        await receive_and_check(dut, received, 0xA6)
        before = len(received)

        # Send in the background so this test can interrupt the frame.
        sender = cocotb.start_soon(send_serial_byte(dut, 0x55))
        await Timer(delay_ns, unit="ns")

        sender.cancel() # Stop the sender before it can change RX again. 
        await reset_rx(dut) # Reset also returns the input high and checks the cleared outputs.

        # No byte from the interrupted frame should appear later.
        await wait_clocks(10 * CLKS_PER_BIT)
        assert len(received) == before, f"Reset during {stage} did not discard the frame"
        assert int(dut.data_out.value) == 0, f"Reset during {stage} did not clear data_out"

        # Verify that the receiver works again after reset.
        await receive_and_check(dut, received, 0x3C)
        await wait_clocks(10 * CLKS_PER_BIT)
        assert received[before:] == [0x3C], f"Unexpected bytes after reset during {stage}: {received[before:]}"

# Test: Receive frames with no extra idle time between them.
@cocotb.test()
async def consecutive_receptions(dut):
    """Receive the next start bit immediately after each stop bit."""
    received = await setup_rx(dut)
    expected = list(range(256))

    # Do not use receive_and_check here: it adds five idle clocks.
    # Each new frame starts as soon as the previous stop bit ends.
    for byte in expected:
        await send_serial_byte(dut, byte)

    # Wait for the monitor and check for unwanted extra bytes.
    await wait_clocks(10 * CLKS_PER_BIT)
    assert received == expected, "Consecutive received bytes did not match"

# Test: Receive frames that start at different times and use different bit lengths.
@cocotb.test()
async def receive_with_timing_changes(dut):
    """Check different start offsets and bit periods within plus or minus 2%."""
    received = await setup_rx(dut)
    expected = []

    # Shorter bit periods mean a faster sender; longer means a slower sender.
    bit_periods = [
        BIT_NS * 98 // 100,
        BIT_NS * 99 // 100,
        BIT_NS,
        BIT_NS * 101 // 100,
        BIT_NS * 102 // 100,
    ]

    # Try several positions within a 20 ns system-clock cycle.
    offsets_ns = [1, 5, 9, 13, 19]
    test_bytes = [0x00, 0xFF, 0x55, 0xAA, 0x41]

    for bit_ns in bit_periods:
        for offset_ns in offsets_ns:
            for byte in test_bytes:
                # Start this frame a chosen time after a falling clock edge.
                await RisingEdge(dut.clk)
                await Timer(CLOCK_NS // 2 + offset_ns, unit="ns")

                before = len(received)
                await send_serial_byte(dut, byte, bit_ns=bit_ns)

                # Leave an idle bit between these individual timing cases.
                await Timer(BIT_NS, unit="ns")

                actual = received[before:]
                assert actual == [byte], (
                    f"Bit period {bit_ns} ns, offset {offset_ns} ns, "
                    f"sent 0x{byte:02X}: got {actual}"
                )
                expected.append(byte)

    # Check that nothing extra appears after the last frame.
    await wait_clocks(10 * CLKS_PER_BIT)
    assert received == expected, "Received timing-test sequence did not match"