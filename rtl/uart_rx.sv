`timescale 1ns/1ps

// UART receiver: 8 data bits, no parity, and 1 stop bit.
// At 50 MHz, 434 clocks per bit gives a baud rate of 115,207 (50M/434).
module uart_rx #(parameter integer CLKS_PER_BIT = 434) (
    input  logic clk, // System clock; the testbench uses 50 MHz.
    input  logic reset, // Active-high synchronous reset.
    input  logic rx, // Incoming UART serial signal.
    output logic [7:0] data_out, // Most recently accepted byte.
    output logic data_valid, // One-clock pulse when a byte is accepted.
    output logic framing_error // One-clock pulse when the stop bit is low.
);
	// UART line levels.
    localparam logic UART_IDLE = 1'b1; // Idle state is high.
    localparam logic UART_START = 1'b0; // Start bit is low.
    localparam logic UART_STOP = 1'b1; // Stop bit is high.

    // Half-bit delay before checking the start bit (CLKS_PER_BIT must be at least 2).
    localparam integer HALF_BIT_CLKS = CLKS_PER_BIT / 2;

    // Two-stage (two-flip-flop) synchronizer.
	// RX can change between clock edges, so this makes reading safer.
	// The 2nd register gives the 1st time to settle before we read it.
    logic rx_meta; // 1st register: Samples RX (the asynchronous input).
    logic rx_sync; // 2nd register: Version used by RX (the synchronized signal).

    always_ff @(posedge clk) begin
		// Reset both registers to high (UART's idle level).
        if (reset) begin
            rx_meta <= UART_IDLE;
            rx_sync <= UART_IDLE;
		
		// Move RX through the 1st register, then the 2nd. 
        end else begin
            rx_meta <= rx;
            rx_sync <= rx_meta; // Copies the previous rx_meta value.
        end
    end

    // Idle waits for a start bit; the remaining states receive the frame.
    typedef enum logic [1:0] {
        IDLE,
        START,
        DATA,
        STOP
    } state_t;

    state_t state; // Current state of the RX.
    integer unsigned baud_count; // Counts clock cycles between checks of RX.
    logic [2:0] bit_index; // Identifies the data bit being received (0-7).
    logic [7:0] shift_reg; // Stores incoming bits until the frame is validated.

	// Update RX's state, counters, and outputs on each rising clock edge. 
    always_ff @(posedge clk) begin
        // Reset on rising clock edge, clearing the RX (including an unfinished byte).
        if (reset) begin
            state <= IDLE;
            baud_count <= 0;
            bit_index <= 0;
            shift_reg <= 0;
            data_out <= 0;
            data_valid <= 0;
            framing_error <= 0;

        // Process the state machine.
        end else begin
            // Clear both signals each clock.
            // STOP sets one high when a frame finishes.
            data_valid <= 0;
            framing_error <= 0;

            case (state)
                // Wait for a low level indicating a possible start bit.
                IDLE: begin
                    baud_count <= 0;
                    bit_index <= 0;

                    if (rx_sync == UART_START) begin
                        state <= START;
                    end
                end

				// Check that RX is still low.
                START: begin
                    if (baud_count == HALF_BIT_CLKS - 1) begin // Wait for one half bit period (until midpoint).
                        baud_count <= 0;

                        if (rx_sync == UART_START) begin
                            state <= DATA; // Start bit confirmed.
                        end else begin
                            state <= IDLE; // Reject a false start.
                        end
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end
                end

                // Read each data bit near its center, LSB first.
                DATA: begin
                    if (baud_count == CLKS_PER_BIT - 1) begin // Wait for one bit period.
                        baud_count <= 0;

                        shift_reg[bit_index] <= rx_sync; // Store each received bit directly in its corresponding position.

                        if (bit_index == 7) begin
                            state <= STOP; // All eight data bits have been received.
                        end else begin
                            bit_index <= bit_index + 1'b1; // Move to the next bit.
                        end
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end
                end

                // Read the stop bit after data bit 7 (one bit period later).
                STOP: begin
                    if (baud_count == CLKS_PER_BIT - 1) begin // Wait for one bit period.
                        baud_count <= 0;
                        state <= IDLE; // Ready before the next frame begins.

                        if (rx_sync == UART_STOP) begin
                            // Correct stop bit: make the received byte available.
                            data_out <= shift_reg;
                            data_valid <= 1'b1;
                        end else begin
                            // Wrong stop bit: report an error (keeping prev data_out value).
                            framing_error <= 1'b1;
                        end
                    end else begin
                        baud_count <= baud_count + 1; // Count another clock.
                    end
                end

                // Return to idle if the state is invalid.
                default: begin
                    state <= IDLE;
                    baud_count <= 0;
                    bit_index <= 0;
                end
            endcase
        end
    end

endmodule