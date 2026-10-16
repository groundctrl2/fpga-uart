"""UART loopback verification: send bytes through TX and check RX."""

import cocotb
from cocotb.triggers import Timer, RisingEdge

# Match the clocks-per-bit setting in uart_loopback.sv.
CLKS_PER_BIT = 434
CLOCK_NS = 20
BIT_NS = CLKS_PER_BIT * CLOCK_NS
FRAME_NS = 10 * BIT_NS # Start bit, eight data bits, and stop bit.