"""UART RX verification: idle behavior, received bytes, and output pulses."""

import cocotb
from cocotb.triggers import Timer

# Match the receiver's (uart_rx.sv) default timing parameter.
# At 50 MHz, each clock is 20 ns and each bit lasts 8680 ns.
CLKS_PER_BIT = 434
CLOCK_NS = 20
BIT_NS = CLKS_PER_BIT * CLOCK_NS

# Helper: Run the system clock continuously.
async def run_clock(dut):
    """Generate a 50 MHz clock until the test ends."""
    while True:
        dut.clk.value = 0
        await Timer(CLOCK_NS // 2, unit="ns")
        dut.clk.value = 1
        await Timer(CLOCK_NS // 2, unit="ns")