`timescale 1ns/1ps

// Connect the UART transmitter to the receiver for loopback testing.
// Both modules use the same clock, reset, and clocks-per-bit setting.
module uart_loopback #(parameter integer CLKS_PER_BIT = 434) (
    input  logic clk, // System clock; the testbench uses 50 MHz.
    input  logic reset, // Active-high synchronous reset for both modules.

    // Transmitter interface.
    input  logic [7:0] data_in, // Byte to transmit.
    input  logic send, // One-clock request to send a byte; accepted only when idle.
    output logic busy, // High while TX is sending; low when ready.

    // Receiver interface.
    output logic [7:0] data_out, // Most recently accepted byte.
    output logic data_valid, // One-clock pulse when RX accepts a byte.
    output logic framing_error // One-clock pulse when RX finds a low stop bit.
);

    // Carries the serial bits from TX to RX inside this wrapper.
    logic serial_line;

    // Add a transmitter (tx_inst).
    uart_tx #(
        .CLKS_PER_BIT(CLKS_PER_BIT) // Set how many clock cycles each bit lasts.
    ) tx_inst (
        // Connect each TX port (left) to a signal in this file (right).
		.clk(clk), // Use the wrapper's system clock.
        .reset(reset), // Use the wrapper's reset.
        .data_in(data_in), // Pass the byte to TX.
        .send(send), // Pass the send request to TX.
        .tx(serial_line), // Put TX's serial output on the internal connection.
        .busy(busy) // Make TX's busy status available outside the wrapper.
    );

    // Add a receiver (rx_inst).
    uart_rx #(
        .CLKS_PER_BIT(CLKS_PER_BIT) // Set how many clock cycles each bit lasts.
    ) rx_inst (
        // Connect each RX port (left) to a signal in this file (right).
        .clk(clk), // Use the wrapper's system clock.
        .reset(reset), // Use the wrapper's reset.
        .rx(serial_line), // Read the serial bits sent by TX.
        .data_out(data_out), // Make RX's received byte available outside the wrapper.
        .data_valid(data_valid), // Report when RX accepts a byte.
        .framing_error(framing_error) // Report when RX finds a low stop bit.
    );

endmodule