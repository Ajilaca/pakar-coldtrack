// Testbench top ASIC coldtrack_spi (SPI + flash QSPI) dengan model flash, untuk tb/test_coldtrack_top.py (CT_SPI=1).
module coldtrack_spi_tb #(
    parameter               BERKAS_A   = "",
    parameter logic [255:0] HASH_MODEL = '0
) (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        spi_sck,
    input  logic        spi_cs_n,
    input  logic        spi_mosi,
    output logic        spi_miso,
    output logic        spi_miso_oe,
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

    coldtrack_spi #(.HASH_MODEL(HASH_MODEL)) u_dut (
        .clk(clk), .rst_n(rst_n),
        .spi_sck(spi_sck), .spi_cs_n(spi_cs_n), .spi_mosi(spi_mosi), .spi_miso(spi_miso), .spi_miso_oe(spi_miso_oe),
        .qspi_sck(sck), .qspi_cs_n(cs_n), .qspi_io_o(io_o), .qspi_io_oe(io_oe), .qspi_io_i(io_flash),
        .alarm_waspada(alarm_waspada), .alarm_kritis(alarm_kritis), .alarm_sensor(alarm_sensor)
    );

    spi_flash_model #(.BERKAS_A(BERKAS_A)) u_flash (
        .clk(clk), .sck(sck), .cs_n(cs_n), .io_dut(io_o), .oe_dut(io_oe), .io_flash(io_flash),
        .pakai_b(1'b0), .tulis(tulis), .tulis_addr(tulis_addr), .tulis_data(tulis_data),
        .perintah_salah(perintah_salah), .jumlah_byte(jumlah_byte)
    );
endmodule
