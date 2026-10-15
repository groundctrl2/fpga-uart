`timescale 1ns/1ps

// UART receiver: 8 data bits, no parity, and 1 stop bit.
// At 50 MHz, 434 clocks per bit gives a baud rate of 115,207 (50M/434).
module uart_rx #(
    parameter integer CLKS_PER_BIT = 434
) (
    input  logic clk, // System clock.
    input  logic reset, // Active-high synchronous reset.
    input  logic rx, // Incoming UART serial signal.
    output logic [7:0] data_out, // Most recently accepted byte.
    output logic data_valid, // One-clock pulse when a byte is accepted.
    output logic framing_error // One-clock pulse when the stop bit is low.
);

endmodule