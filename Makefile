# Choose which module to test: make TARGET=uart_tx or make TARGET=uart_rx.
TARGET ?= uart_tx # Running make without a target selection default tests TX.

SIM = icarus # Use Icarus for cocotb simulation in the Windows/MSYS2 environment.
TOPLEVEL_LANG = verilog # SystemVerilog sources are handled through the Verilog language setting.

# Hardware source, top-level module, and Python test module.
VERILOG_SOURCES = $(PWD)/rtl/$(TARGET).sv
COCOTB_TOPLEVEL = $(TARGET)
COCOTB_TEST_MODULES = test_$(TARGET) # Excluding the .py extension.

# Keep each module's compiled simulation in its own directory.
SIM_BUILD = sim_build_$(TARGET)

# Use cocotb's build rules to compile the design and run the tests.
include $(shell cocotb-config --makefiles)/Makefile.sim