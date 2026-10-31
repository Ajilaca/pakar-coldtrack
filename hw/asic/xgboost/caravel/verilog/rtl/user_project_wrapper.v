// SPDX-FileCopyrightText: 2020 Efabless Corporation
// SPDX-FileCopyrightText: 2026 Faza Dzil
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
// SPDX-License-Identifier: Apache-2.0

`default_nettype none
/*
 * user_project_wrapper ColdTrack: makro coldtrack_asic (pakar-coldtrack hw/asic/xgboost, layout RUN_AK) di area user
 * Caravel.
 *
 * Clock dan reset dari SoC manajemen (wb_clk_i, wb_rst_i aktif tinggi); target clock 10 MHz (CLOCK_PERIOD layout
 * makro 100 ns). Host luar bicara lewat SPI slave chip; model XGBoost dibaca dari flash QSPI luar.
 *
 *   mprj_io  fungsi          arah
 *   25       spi_sck         masuk
 *   24       spi_cs_n        masuk
 *   23       spi_mosi        masuk
 *   22       spi_miso        keluar, tri-state (spi_miso_oe)
 *   21       alarm_waspada   keluar
 *   20       alarm_kritis    keluar
 *   19       alarm_sensor    keluar
 *   18       qspi_sck        keluar
 *   17       qspi_cs_n       keluar
 *   13..16   qspi_io[0..3]   dua arah (qspi_io_oe)
 *
 * Alarm juga dikirim ke user_irq[2:0] supaya firmware SoC bisa bereaksi. Wishbone dan logic analyzer tidak dipakai
 * (keluaran diikat 0); pin mprj_io lain sebagai masukan (io_oeb 1).
 */

module user_project_wrapper #(
    parameter BITS = 32
) (
`ifdef USE_POWER_PINS
    inout vdda1,	// User area 1 3.3V supply
    inout vdda2,	// User area 2 3.3V supply
    inout vssa1,	// User area 1 analog ground
    inout vssa2,	// User area 2 analog ground
    inout vccd1,	// User area 1 1.8V supply
    inout vccd2,	// User area 2 1.8v supply
    inout vssd1,	// User area 1 digital ground
    inout vssd2,	// User area 2 digital ground
`endif

    input wb_clk_i,
    input wb_rst_i,
    input wbs_stb_i,
    input wbs_cyc_i,
    input wbs_we_i,
    input [3:0] wbs_sel_i,
    input [31:0] wbs_dat_i,
    input [31:0] wbs_adr_i,
    output wbs_ack_o,
    output [31:0] wbs_dat_o,

    input  [127:0] la_data_in,
    output [127:0] la_data_out,
    input  [127:0] la_oenb,

    input  [`MPRJ_IO_PADS-1:0] io_in,
    output [`MPRJ_IO_PADS-1:0] io_out,
    output [`MPRJ_IO_PADS-1:0] io_oeb,

    inout [`MPRJ_IO_PADS-10:0] analog_io,

    input   user_clock2,

    output [2:0] user_irq
);
    wire       spi_miso, spi_miso_oe;
    wire       qspi_sck, qspi_cs_n;
    wire [3:0] qspi_io_o, qspi_io_oe;
    wire       alarm_waspada, alarm_kritis, alarm_sensor;

    // Rantai buffer clock: wb_clk_i ada di pojok kiri bawah wrapper, pin clk makro di sisi atas (~4 mm). CTS tidak
    // melihat pin makro sebagai sink dan repair_design melewati net clock, jadi buffer dipasang di sini (placer
    // menyebarnya di sepanjang kanal kiri dan pita atas).
    localparam N_CLKBUF = 6;
    wire [N_CLKBUF:0] clk_rantai;
    assign clk_rantai[0] = wb_clk_i;
    genvar i;
    generate
        for (i = 0; i < N_CLKBUF; i = i + 1) begin : g_clkbuf
            (* keep *) sky130_fd_sc_hd__clkbuf_8 u_buf (
`ifdef USE_POWER_PINS
                .VPWR(vccd1), .VGND(vssd1), .VPB(vccd1), .VNB(vssd1),
`endif
                .A(clk_rantai[i]), .X(clk_rantai[i+1]));
        end
    endgenerate

    coldtrack_asic u_ct (
`ifdef USE_POWER_PINS
        .VPWR(vccd1),
        .VGND(vssd1),
`endif
        .clk(clk_rantai[N_CLKBUF]),
        .rst_n(~wb_rst_i),
        .spi_sck(io_in[25]),
        .spi_cs_n(io_in[24]),
        .spi_mosi(io_in[23]),
        .spi_miso(spi_miso),
        .spi_miso_oe(spi_miso_oe),
        .qspi_sck(qspi_sck),
        .qspi_cs_n(qspi_cs_n),
        .qspi_io_o(qspi_io_o),
        .qspi_io_oe(qspi_io_oe),
        .qspi_io_i(io_in[16:13]),
        .alarm_waspada(alarm_waspada),
        .alarm_kritis(alarm_kritis),
        .alarm_sensor(alarm_sensor)
    );

    // io_oeb aktif rendah: 0 = pin dikemudikan chip
    assign io_out[37:26] = 12'b0;
    assign io_oeb[37:26] = {12{1'b1}};
    assign io_out[25:23] = 3'b0;
    assign io_oeb[25:23] = 3'b111;
    assign io_out[22]    = spi_miso;
    assign io_oeb[22]    = ~spi_miso_oe;
    assign io_out[21:17] = {alarm_waspada, alarm_kritis, alarm_sensor, qspi_sck, qspi_cs_n};
    assign io_oeb[21:17] = 5'b0;
    assign io_out[16:13] = qspi_io_o;
    assign io_oeb[16:13] = ~qspi_io_oe;
    assign io_out[12:0]  = 13'b0;
    assign io_oeb[12:0]  = {13{1'b1}};

    assign user_irq    = {alarm_sensor, alarm_waspada, alarm_kritis};
    assign wbs_ack_o   = 1'b0;
    assign wbs_dat_o   = 32'b0;
    assign la_data_out = 128'b0;
endmodule	// user_project_wrapper

`default_nettype wire
