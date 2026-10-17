"""UART loopback verification: send bytes through TX and check RX."""

import cocotb
from cocotb.triggers import Timer, RisingEdge

# Match the clocks-per-bit setting in uart_loopback.sv.
# At 50 MHz, each clock lasts 20 ns and each bit lasts 8680 ns.
CLKS_PER_BIT = 434
CLOCK_NS = 20
BIT_NS = CLKS_PER_BIT * CLOCK_NS
FRAME_NS = 10 * BIT_NS # Start bit, eight data bits, and stop bit.

# Helper: Run the system clock continuously.
# Same as run_clock() in test_uart_rx.py.
async def run_clock(dut):
    """Generate a 50 MHz clock until the test ends."""
    while True:
        dut.clk.value = 0
        await Timer(CLOCK_NS // 2, unit="ns") # Keep the clock low for 10 ns.
        dut.clk.value = 1
        await Timer(CLOCK_NS // 2, unit="ns") # Keep the clock high for 10 ns.

# Helper: Wait one clock and allow outputs to update.
async def clock_cycle(dut):
    """Read outputs 1 ns after the next rising clock edge."""
    await RisingEdge(dut.clk) # Wait for clock to change low to high.
    await Timer(1, unit="ns")

# Helper: Reset both modules before testing.
async def reset_loopback(dut):
    """Reset TX and RX and check their starting outputs."""
    dut.reset.value = 1
    dut.send.value = 0 # Do not request a transmission during reset.
    dut.data_in.value = 0

	# Hold reset high for five rising clock edges.
    # Both modules should clear their outputs after each edge.
    for _ in range(5):
        await clock_cycle(dut)
        assert int(dut.busy.value) == 0, "Reset must clear busy"
        assert int(dut.data_out.value) == 0, "Reset must clear data_out"
        assert int(dut.data_valid.value) == 0, "Reset must clear data_valid"
        assert int(dut.framing_error.value) == 0, "Reset must clear framing_error"

	# Turn reset off and allow normal operation to begin.
    dut.reset.value = 0
    await clock_cycle(dut)

# Helper: Watch RX while TX sends data.
# Adapted from monitor_rx() in test_uart_rx.py.
async def monitor_rx(dut, received):
    """Collect received bytes and check the result signals every clock."""
    # Save the previous values so we can check what changes each clock.
    previous_valid = 0
    previous_data = int(dut.data_out.value)

    while True:
        await clock_cycle(dut)

		# Convert the hardware signals into Python integers.
        valid = int(dut.data_valid.value)
        error = int(dut.framing_error.value)
        data = int(dut.data_out.value)
        
        if int(dut.reset.value):
            # Reset clears RX's outputs, even during an unfinished frame.
            assert data == 0, "Reset must clear data_out"
            assert valid == 0, "Reset must clear data_valid"
            assert error == 0, "Reset must clear framing_error"
        else:
            # TX should generate valid stop bits, so RX should report no errors.
            assert error == 0, "Unexpected framing error during loopback"

            # data_valid must return low after one clock.
            assert not (valid and previous_valid), "data_valid lasted longer than one clock"
            if valid: 
                # Save each byte when RX says it is ready.
                received.append(data)
            else:
                # Without a new byte, data_out must keep its previous value.
                assert data == previous_data, "data_out changed without data_valid"

		# Save this clock's values for the next comparison.
        previous_valid = valid
        previous_data = data

# Helper: Ask TX to send one byte.
async def send_byte(dut, byte):
    """Wait until TX is ready, then request a transmission."""
    # Allow enough clocks for a complete frame, plus five extra clocks.
    for _ in range(10 * CLKS_PER_BIT + 5):
        if int(dut.busy.value) == 0:
            break # TX is ready, stop waiting.
        await clock_cycle(dut)
    else:
        # A for-loop's else runs if the loop finishes without reaching break.
        raise AssertionError("Timed out waiting for TX to become ready")

    # Set the byte and hold send high through one rising clock edge.
    dut.data_in.value = byte
    dut.send.value = 1
    await clock_cycle(dut)
    dut.send.value = 0 # End the request so it only lasts one clock.

    assert int(dut.busy.value) == 1, "TX did not accept the send request"

	# Return while TX is still sending.
    # The background monitor will collect the byte when RX accepts it.

# Helper: Start the clock, reset the modules, and start watching RX.
async def setup_loopback(dut):
    """Prepare the loopback and return the list of received bytes."""
    # Set known inputs before starting the clock.
    dut.clk.value = 0
    dut.reset.value = 1
    dut.send.value = 0
    dut.data_in.value = 0

	# Run the clock in the background while the test continues.
    cocotb.start_soon(run_clock(dut))
    await reset_loopback(dut)

	# The monitor adds bytes to this list while the test sends them.
    received = []
    cocotb.start_soon(monitor_rx(dut, received))

	# Return the same list so the test can check what the monitor collects.
    return received

# Test: Send a known byte through the actual TX and RX modules.
@cocotb.test()
async def loopback_ascii_a(dut):
    """Verify that sending ASCII 'A' produces one matching received byte."""
    received = await setup_loopback(dut)

	# Python requests the byte, TX generates the bits and RX reads them.
    await send_byte(dut, 0x41) # ASCII 'A'.

    # Wait for the frame to finish and allow a few extra clocks.
    # The clock and RX monitor keep running during this wait.
    await Timer(FRAME_NS + 5 * CLOCK_NS, unit="ns")

    assert int(dut.busy.value) == 0, "TX must be ready after the frame"

	# The list must contain exactly one byte, matching the byte we sent.
    assert received == [0x41], f"Expected one received byte [0x41], got {received}"

    # Stay idle long enough to catch an unwanted extra byte.
    await Timer(FRAME_NS, unit="ns")
    assert received == [0x41], f"Unexpected received bytes: {received}"

# TODO: Test all 256 possible byte values.
# TODO: Test consecutive transmissions.
# TODO: Test reproducible randomized traffic.