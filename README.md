# fpga-uart
A UART (Universal Asynchronous Receiver/Transmitter) implementation written in SystemVerilog, designed to transmit and receive serial data through configurable digital hardware.

This project focuses on FPGA-oriented digital design, serial communication protocols, and hardware verification. The transmitter (TX) and receiver (RX) will be developed and tested using simulation, without requiring physical FPGA hardware.

## Project Objectives
- Design UART transmitter and receiver modules in synthesizable SystemVerilog.
- Implement finite-state machines (FSMs), baud-rate timing, and serial data handling.
- Develop Python-based testbenches to generate test sequences and verify transmitted and received data.
- Validate functionality through simulation, waveform analysis, and automated testing.
- Integrate GitHub Actions for continuous integration (CI).

## Technical Specifications
| Parameter | Initial Configuration |
|---|---|
| Hardware Description Language | SystemVerilog |
| Protocol | UART |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Baud Rate | 115200 bps |
| Clock Frequency | 50 MHz |
| Hardware Target | Simulation-first, FPGA-oriented |

## Development Tools
| Tool | Purpose |
|---|---|
| SystemVerilog | UART TX/RX hardware implementation |
| Verilator | HDL simulation and linting |
| Python/cocotb | Test generation and automated verification |
| GTKWave | Digital waveform visualization |
| GitHub Actions | Continuous integration and automated testing |
| VS Code | Development environment |

## Verification Plan
The UART implementation will be tested against a variety of input sequences and operating conditions.

| Test | Description |
|---|---|
| Basic Transmission | Verify transmission and reception of `0x41` (ASCII 'A'). |
| Full Byte Range | Test all 256 possible 8-bit values (`0x00`–`0xFF`). |
| Alternating Bits | Test `0x55` and `0xAA` to verify bit ordering and transitions. |
| Randomized Traffic | Test 10,000 reproducibly generated random bytes. |
| Baud Rate Tolerance | Evaluate receiver behavior under baud-rate mismatch. |
| Framing Errors | Verify detection of invalid stop bits. |
| Continuous Transmission | Test consecutive frames without additional idle time. |
| Parity Errors | Verify parity checking if parity support is implemented. |

Python-based cocotb testbenches will independently validate TX and RX behavior before testing the modules together in loopback.

## References
- [OpenTitan UART Documentation](https://opentitan.org/book/hw/ip/uart/)
- [OpenTitan UART Verification Plan](https://github.com/lowRISC/opentitan/blob/master/hw/ip/uart/data/uart_testplan.hjson)
- [Verilator Documentation](https://verilator.org/guide/latest/)
- [cocotb Documentation](https://docs.cocotb.org/en/stable/)
