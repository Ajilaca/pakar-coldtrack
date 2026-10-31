// Top layout ASIC: coldtrack_spi (hw/rtl, tidak diubah) di belakang sinkroniser reset.
// Pin sama dengan coldtrack_spi: clk, rst_n, SPI 4 (+ miso_oe), QSPI 6 (io tiga keadaan di pad), alarm 3.
// rst_n dari pin boleh turun kapan saja (reset seketika), tetapi dilepas ke seluruh chip sinkron dengan clk (D).
// Di dalam, versi ASIC physics/features/model_flash (hw/asic/xgboost/rtl) dipakai lewat daftar berkas, nama modulnya sama.
// KUNCI_MODEL = kunci HMAC model di flash (hw/asic/xgboost/rtl/model_flash.sv); diteruskan lewat parameter HASH_MODEL
// coldtrack_spi/coldtrack_top karena RTL itu tidak diubah. Isinya rahasia: diisi run_layout.sh dari berkas kunci.
module coldtrack_asic #(
    parameter logic [255:0] KUNCI_MODEL  = '0,
    parameter int           SETENGAH_SCK = 1
) (
    input  logic       clk,
    input  logic       rst_n,
    // SPI slave ke mikrokontroler (mode 0, SCK <= clk/8)
    input  logic       spi_sck,
    input  logic       spi_cs_n,
    input  logic       spi_mosi,
    output logic       spi_miso,
    output logic       spi_miso_oe,
    // flash QSPI bobot pohon
    output logic       qspi_sck,
    output logic       qspi_cs_n,
    output logic [3:0] qspi_io_o,
    output logic [3:0] qspi_io_oe,
    input  logic [3:0] qspi_io_i,
    // alarm sopir
    output logic       alarm_waspada,
    output logic       alarm_kritis,
    output logic       alarm_sensor
);
    logic rst_n_sinkron;

    rst_sync u_rst (.clk(clk), .rst_n_in(rst_n), .rst_n_out(rst_n_sinkron));

    coldtrack_spi #(.MODEL_FLASH(1'b1), .HASH_MODEL(KUNCI_MODEL), .SETENGAH_SCK(SETENGAH_SCK)) u_chip (
        .clk(clk), .rst_n(rst_n_sinkron),
        .spi_sck(spi_sck), .spi_cs_n(spi_cs_n), .spi_mosi(spi_mosi), .spi_miso(spi_miso), .spi_miso_oe(spi_miso_oe),
        .qspi_sck(qspi_sck), .qspi_cs_n(qspi_cs_n), .qspi_io_o(qspi_io_o), .qspi_io_oe(qspi_io_oe),
        .qspi_io_i(qspi_io_i),
        .alarm_waspada(alarm_waspada), .alarm_kritis(alarm_kritis), .alarm_sensor(alarm_sensor)
    );
endmodule
