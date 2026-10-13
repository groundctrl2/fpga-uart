SIM = icarus # Use Icarus for cocotb simulation in the Windows/MSYS2 environment.
TOPLEVEL_LANG = verilog # SystemVerilog sources are handled through the Verilog language setting.

# Hardware source, top-level module, and Python test module.
VERILOG_SOURCES = $(PWD)/rtl/uart_tx.sv
COCOTB_TOPLEVEL = uart_tx
COCOTB_TEST_MODULES = test_uart_tx # Excluding the .py extension.

# Use cocotb's build rules to compile the design and run the tests.
include $(shell cocotb-config --makefiles)/Makefile.sim