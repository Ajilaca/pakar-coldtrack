// Testbench coldtrack_top mode flash (MODEL_FLASH = 1) + model flash QSPI, dengan port AXI4-Lite yang sama
// namanya dengan coldtrack_top supaya tb/test_coldtrack_top.py bisa dipakai untuk kedua mode.
module coldtrack_top_flash_tb #(
    parameter               BERKAS_A   = "",
    parameter logic [255:0] HASH_MODEL = '0
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic [11:0] s_axil_awaddr,
    input  logic        s_axil_awvalid,
    output logic        s_axil_awready,
    input  logic [31:0] s_axil_wdata,
    input  logic [3:0]  s_axil_wstrb,
    input  logic        s_axil_wvalid,
    output logic        s_axil_wready,
    output logic [1:0]  s_axil_bresp,
    output logic        s_axil_bvalid,
    input  logic        s_axil_bready,
    input  logic [11:0] s_axil_araddr,
    input  logic        s_axil_arvalid,
    output logic        s_axil_arready,
    output logic [31:0] s_axil_rdata,
    output logic [1:0]  s_axil_rresp,
    output logic        s_axil_rvalid,
    input  logic        s_axil_rready,
    output logic        alarm_waspada,
    output logic        alarm_kritis,
    output logic        alarm_sensor,
    input  logic        tulis,
    input  logic [16:0] tulis_addr,
    input  logic [7:0]  tulis_data,
    output logic        perintah_salah
);
    logic       sck, cs_n;
    logic [3:0] io_o, io_oe, io_flash;
    /* verilator lint_off UNUSEDSIGNAL */
    logic [31:0] jumlah_byte;
    /* verilator lint_on UNUSEDSIGNAL */

    coldtrack_top #(.MODEL_FLASH(1'b1), .HASH_MODEL(HASH_MODEL)) u_dut (
        .clk(clk), .rst_n(rst_n),
        .s_axil_awaddr(s_axil_awaddr), .s_axil_awvalid(s_axil_awvalid), .s_axil_awready(s_axil_awready),
        .s_axil_wdata(s_axil_wdata), .s_axil_wstrb(s_axil_wstrb), .s_axil_wvalid(s_axil_wvalid),
        .s_axil_wready(s_axil_wready), .s_axil_bresp(s_axil_bresp), .s_axil_bvalid(s_axil_bvalid),
        .s_axil_bready(s_axil_bready), .s_axil_araddr(s_axil_araddr), .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready), .s_axil_rdata(s_axil_rdata), .s_axil_rresp(s_axil_rresp),
        .s_axil_rvalid(s_axil_rvalid), .s_axil_rready(s_axil_rready),
        .alarm_waspada(alarm_waspada), .alarm_kritis(alarm_kritis), .alarm_sensor(alarm_sensor),
        .qspi_sck(sck), .qspi_cs_n(cs_n), .qspi_io_o(io_o), .qspi_io_oe(io_oe), .qspi_io_i(io_flash)
    );

    spi_flash_model #(.BERKAS_A(BERKAS_A)) u_flash (
        .clk(clk), .sck(sck), .cs_n(cs_n), .io_dut(io_o), .oe_dut(io_oe), .io_flash(io_flash),
        .pakai_b(1'b0), .tulis(tulis), .tulis_addr(tulis_addr), .tulis_data(tulis_data),
        .perintah_salah(perintah_salah), .jumlah_byte(jumlah_byte)
    );
endmodule
