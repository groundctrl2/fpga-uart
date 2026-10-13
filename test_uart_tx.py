"""
Basic reset test for the UART transmitter module.
This checks that the simulator and cocotb work together and that TX
stays idle-high after reset. It does not test byte transmission yet.
"""

import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def tx_idle_after_reset(dut):
    """Check TX during reset and for five clock cycles afterward."""
    dut.clk.value = 0
    dut.reset.value = 1

    # A 50 MHz clock has a 20 ns period: 10 ns for each half-cycle.
    # Hold reset high for five complete cycles.
    for _ in range(5):
        await Timer(10, unit="ns")
        dut.clk.value = 1
        await Timer(10, unit="ns")
        dut.clk.value = 0

    assert int(dut.tx.value) == 1, "TX must be high during reset"

	# Release reset and check that the output remains idle-high.
    dut.reset.value = 0

    for _ in range(5):
        await Timer(10, unit="ns")
        dut.clk.value = 1
        await Timer(10, unit="ns")
        dut.clk.value = 0
        assert int(dut.tx.value) == 1, "TX must remain idle-high"