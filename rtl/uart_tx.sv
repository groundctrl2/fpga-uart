`timescale 1ns/1ps

// UART transmitter: 8 data bits, no parity, and 1 stop bit.
// At 50 MHz, 434 clocks per bit gives a baud rate of 115,207 (50M/434).
// CLKS_PER_BIT must be at least 1.
module uart_tx #(parameter integer CLKS_PER_BIT = 434) (
    input  logic clk, // System clock; the testbench uses 50 MHz.
    input  logic reset, // Active-high synchronous reset.
    input logic [7:0] data_in, // Byte to transmit.
    input logic send, // One-cycle request; accepted only when idle. 
    output logic tx, // UART serial output.
    output logic busy // High while sending a frame; low when ready.
);
    // UART line levels.
    localparam logic UART_IDLE = 1'b1; // Idle state is high.
    localparam logic UART_START = 1'b0; // Start bit is low.
    localparam logic UART_STOP = 1'b1; // Stop bit is high.

    // Busy signal levels.
    localparam logic TX_BUSY = 1'b1; // Busy state is high.
    localparam logic TX_READY = 1'b0; // Busy state is low when ready.

    // Idle waits for a request; the remaining states transmit the frame.
    typedef enum logic [1:0] {
        IDLE,
        START,
        DATA,
        STOP
    } state_t;

    state_t state; // Current state of the transmitter.
    logic [7:0] shift_reg; // Stores the byte being sent, even if data_in changes.
    logic [2:0] bit_index; // Which data bit is being sent (0-7).
    integer unsigned baud_count; // Counts clock cycles spent sending each bit.


    always_ff @(posedge clk) begin
	    // On a rising clock edge, reset stops any transmission and returns TX to idle.
        if (reset) begin 
            state <= IDLE;
            busy <= TX_READY;
            tx <= UART_IDLE;
            shift_reg <= 8'b0; // Cleared shift register.
            bit_index <= 3'b0; // Start with first bit.
            baud_count <= 0;

        // Process the state machine.
        end else begin
            case (state)
                // Wait for a request to send a byte.
                IDLE: begin
                    busy <= TX_READY;
                    tx <= UART_IDLE;
                    baud_count <= 0;

                    // Save the byte and start sending. Requests made while busy are ignored. 
                    if (send) begin
                        state <= START;
                        shift_reg <= data_in; // Load the shift register.
                        busy <= TX_BUSY;
                        tx <= UART_START;
                        bit_index <= 0; // Reset bit index.
                    end
                end

                // Transmit the start bit, then move to the data bits.
                START: begin
                    if (baud_count == CLKS_PER_BIT - 1) begin // Hold for one bit period.
                        state <= DATA;
                        baud_count <= 0;
                        tx <= shift_reg[0]; // Send the LSB.
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end
                end

                // Transmit the data bits, LSB first.
                DATA: begin
                    if (baud_count == CLKS_PER_BIT - 1) begin // Hold for one bit period.
                        baud_count <= 0;

                        // // All 8 bits have been sent.
                        if (bit_index == 7) begin
                            state <= STOP;
                            tx <= UART_STOP;
                        
                        // Send the next bit, working from LSB to MSB. 
                        end else begin
                            // Both assignments read the old shift_reg value.
                            tx <= shift_reg[1]; // Send the next bit.
                            shift_reg <= shift_reg >> 1; // Move the remaining bits one place right.
                            bit_index <= bit_index + 1'b1; // Move to the next bit number.
                        end
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end
                end

                // Keep TX high for one bit period, then return to idle.
                STOP: begin
                    if (baud_count == CLKS_PER_BIT - 1) begin // Hold for one bit period.
                        state <= IDLE;
                        busy <= TX_READY;
                        baud_count <= 0;
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end 
                end

                // Return to idle if the state is invalid.
                default: begin
                    state <= IDLE;
                    tx <= UART_IDLE;
                    busy <= TX_READY;
                    baud_count <= 0;
                end
            endcase
        end
    end

endmodule