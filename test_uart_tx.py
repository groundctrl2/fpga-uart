"""Independent UART TX tests for reset and an 8N1 serial frame."""

import cocotb
from cocotb.triggers import Timer

# Match the transmitter's default timing parameter.
# At 50 MHz, 434 clocks per bit gives a baud rate of 115,207 (50M/434).
CLKS_PER_BIT = 434

async def clock_cycle(dut):
    """Generate one 20 ns clock cycle and allow outputs to settle."""
    dut.clk.value = 0 # Drive the clock low for 10 ns.
    await Timer(10, unit="ns")
    dut.clk.value = 1 # Drive the clock high for 10 ns.
    await Timer(10, unit="ns")

    # The final wait lets the HDL's registered outputs update before the caller reads them.
    # One complete cycle is 20 ns, or 50 MHz. 

async def reset_tx(dut):
    """Apply the synchronous reset for five clock cycles."""
    # Initialize all inputs so the test starts from known values.
    dut.clk.value = 0
    dut.reset.value = 1
    dut.send.value = 0
    dut.data_in.value = 0

    # Synchronous reset takes effect on a rising clock edge.
    for _ in range(5):
        await clock_cycle(dut)

    # Read the simulated output values as Python integers. 
    # An assertion fails the test if its condition is false.
    assert int(dut.tx.value) == 1, "TX must be high during reset"
    assert int(dut.busy.value) == 0, "TX must not be busy during reset"

    # Release reset and let the transmitter execute one normal cycle.
    dut.reset.value = 0
    await clock_cycle(dut)

@cocotb.test()
async def tx_idle_after_reset(dut):
    """Check that TX remains idle-high when no transmission is requested."""
    await reset_tx(dut)

    # With send held low, the transmitter should remain idle.
    for _ in range(5):
        await clock_cycle(dut)
        assert int(dut.tx.value) == 1, "TX must remain idle-high"
        assert int(dut.busy.value) == 0, "TX must remain available"

@cocotb.test()
async def transmit_ascii_a(dut):
    """Check every clock cycle of the start, data, and stop bits."""
    await reset_tx(dut)

    byte = 0x41  # ASCII 'A' = 0x41 = 01000001.

    # Construct the expected 8N1 frame: start bit, 8 data bits, stop bit.
    # UART sends the LSB first, so the frame is:
    # Start bit (0), data bits (1,0,0,0,0,0,1,0), stop bit (1).
    expected_frame = ([0]+[(byte >> bit) & 1 for bit in range(8)]+[1])

    # Present the byte and hold send high for one clock cycle to request transmission.
    dut.data_in.value = byte
    dut.send.value = 1
    await clock_cycle(dut)
    dut.send.value = 0

    # Change the input after acceptance to check that TX captured it.
    # The current frame should still contain 0x41.
    dut.data_in.value = 0xFF

    # The request cycle already advanced to the start bit's first sample.
    # Check that sample immediately; advance before all later samples.
    first_sample = True

    # Enumerate supplies both the frame position and its expected value. 
    for frame_bit, expected in enumerate(expected_frame):
        # Check each bit for exactly CLKS_PER_BIT clock-cycle samples.
        for cycle in range(CLKS_PER_BIT):
            if not first_sample:
                await clock_cycle(dut)
            first_sample = False

            actual = int(dut.tx.value)

            # Include the bit and cycle positions to help locate failures.
            assert actual == expected, (
                f"Frame bit {frame_bit}, cycle {cycle}: "
                f"expected TX={expected}, got {actual}"
            )

            # Busy must stay high through the entire stop-bit period.
            assert int(dut.busy.value) == 1, (
                f"Busy dropped before frame bit {frame_bit} finished"
            )

    # Advance to the edge that completes the stop-bit period.
    await clock_cycle(dut)
    assert int(dut.tx.value) == 1, "TX must return to idle-high"
    assert int(dut.busy.value) == 0, "Busy must clear after the frame"

    # Check that no additional frame starts without another send request.
    for _ in range(5):
        await clock_cycle(dut)
        assert int(dut.tx.value) == 1
        assert int(dut.busy.value) == 0