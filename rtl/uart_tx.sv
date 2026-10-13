`timescale 1ns/1ps

// Initial UART transmitter module.
// For now, this module only sets TX to its idle-high level on reset. 
// Baud timing and serial transmission will be implemented later.
module uart_tx (
    input  logic clk,    // System clock; the testbench uses 50 MHz.
    input  logic reset,  // Active-high synchronous reset.
    output logic tx      // UART serial output.
);

	// Reset takes effect on a rising clock edge.
	// With no other assignment yet, TX holds its value after reset. 
    always_ff @(posedge clk) begin
        if (reset)
            tx <= 1'b1;
    end
endmodule