`timescale 1ns/1ps

// Connect the UART transmitter to the receiver for loopback testing.
module uart_loopback #(parameter integer CLKS_PER_BIT = 434) (
    input  logic clk,
    input  logic reset,

    // Transmitter interface.
    input  logic [7:0] data_in,
    input  logic send,
    output logic busy,

    // Receiver interface.
    output logic [7:0] data_out,
    output logic data_valid,
    output logic framing_error
);

    // Internal serial connection from TX's output to RX's input.
    logic serial_line;

    // TODO: Instantiate uart_tx.
    // Pass CLKS_PER_BIT to its parameter.
    // Connect clk, reset, data_in, send, and busy.
    // Connect its tx output to serial_line.


    // TODO: Instantiate uart_rx.
    // Pass CLKS_PER_BIT to its parameter.
    // Connect clk, reset, data_out, data_valid, and framing_error.
    // Connect its rx input to serial_line.


endmodule