// SPDX-FileCopyrightText: © 2025 Leo Moser <leo.moser@pm.me>
// SPDX-License-Identifier: Apache-2.0
//
// Verilog port of fabric_spi_receiver.sv from greyhound-ihp-v2
// (ip/fabric_config), logic unchanged.
//
// Waits until 4 bytes have been received over SPI, then writes the 32 bit
// word to bitstream_data_o and pulses bitstream_valid_o. MOSI is sampled on
// the falling SCLK edge with SCLK idling low, MSB first (SPI mode 1, as
// greyhound's testbench drives it). The bit counter is not reset by CS, so
// a host must only send whole 32 bit words.

`default_nettype none

module fabric_spi_receiver (
    input wire clk_i,
    input wire rst_ni,

    // Bitstream data
    output wire [31:0] bitstream_data_o,
    output reg         bitstream_valid_o,

    // Enable the SPI receiver
    input wire enable_i,

    // SPI
    input  wire sclk_i,
    input  wire cs_ni,
    input  wire mosi_i,
    output wire miso_o
);

    reg [31:0] shift_register;
    reg [4:0]  shift_cnt;

    // Sync sclk_i
    reg [1:0] sclk_d;
    wire      sclk_sync;
    always @(posedge clk_i) begin
        sclk_d <= {sclk_d[0], sclk_i};
    end
    assign sclk_sync = sclk_d[1];

    // Sync cs_ni
    reg [1:0] cs_n_d;
    wire      cs_n_sync;
    always @(posedge clk_i) begin
        cs_n_d <= {cs_n_d[0], cs_ni};
    end
    assign cs_n_sync = cs_n_d[1];

    // Sync mosi_i
    reg [1:0] mosi_d;
    wire      mosi_sync;
    always @(posedge clk_i) begin
        mosi_d <= {mosi_d[0], mosi_i};
    end
    assign mosi_sync = mosi_d[1];

    // Detect spi_clk edge
    reg spi_sclk_delayed;
    always @(posedge clk_i) begin
        spi_sclk_delayed <= sclk_sync;
    end

    wire spi_sclk_falling;
    assign spi_sclk_falling = spi_sclk_delayed && !sclk_sync;

    always @(posedge clk_i, negedge rst_ni) begin
        if (!rst_ni) begin
            shift_register    <= 32'b0;
            shift_cnt         <= 5'b0;
            bitstream_valid_o <= 1'b0;
        end else begin
            bitstream_valid_o <= 1'b0;

            if (enable_i && !cs_n_sync && spi_sclk_falling) begin
                shift_register <= {shift_register[30:0], mosi_sync};
                shift_cnt      <= shift_cnt + 1'b1;

                if (shift_cnt == 5'd31) begin
                    bitstream_valid_o <= 1'b1;
                end
            end
        end
    end

    assign bitstream_data_o = shift_register;
    assign miso_o = 1'b0;

endmodule
`resetall
