# Choose what to test (running without a target default tests TX).
TARGET ?= uart_tx

SIM = icarus # Use Icarus for cocotb simulation in the Windows/MSYS2 environment.
TOPLEVEL_LANG = verilog # SystemVerilog sources are handled through the Verilog language setting.

# Hardware source, top-level module, and Python test module.
ifeq ($(TARGET),uart_loopback) # Loopback needs the wrapper and both UART modules.
VERILOG_SOURCES = $(CURDIR)/rtl/uart_tx.sv $(CURDIR)/rtl/uart_rx.sv $(CURDIR)/rtl/uart_loopback.sv
else # Individual TX and RX tests only need their own module.
VERILOG_SOURCES = $(CURDIR)/rtl/$(TARGET).sv
endif

# Select the hardware module and Python test file.
COCOTB_TOPLEVEL = $(TARGET)
COCOTB_TEST_MODULES = test_$(TARGET) # Excluding the .py extension.

# Convert the test path on Windows/MSYS2; use the native path elsewhere.
ifeq ($(OS),Windows_NT)
export PYTHONPATH := $(shell cygpath -m "$(CURDIR)/tests") # Tell Python where to find the test files (converts the folder path).
else
export PYTHONPATH := $(CURDIR)/tests
endif

# Keep each module's compiled simulation in its own directory.
SIM_BUILD = sim_build_$(TARGET)

# Use cocotb's build rules to compile the design and run the tests.
include $(shell cocotb-config --makefiles)/Makefile.sim