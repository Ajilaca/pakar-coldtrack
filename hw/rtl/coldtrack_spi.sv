// Top chip ASIC: coldtrack_top di belakang SPI slave (4 pin ke mikrokontroler), bobot pohon di flash QSPI.
// Register map sama dengan KV260 (hw/golden/regmap.py); hanya jalurnya: SPI -> spi_axil_bridge -> AXI4-Lite.
// Pin: clk, rst_n, SPI 4 (+ miso_oe), QSPI 6 (io tiga keadaan di pad), alarm 3.
module coldtrack_spi #(
    parameter               BERKAS_SIMPUL = "",
    parameter               BERKAS_POHON  = "",
    parameter               BERKAS_BASE   = "",
    parameter bit           MODEL_FLASH   = 1'b1,
    parameter logic [255:0] HASH_MODEL    = '0,
    parameter int           SETENGAH_SCK  = 1
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
    logic [11:0] awaddr, araddr;
    logic [31:0] wdata, rdata;
    logic [3:0]  wstrb;
    logic [1:0]  bresp, rresp;
    logic        awvalid, awready, wvalid, wready, bvalid, bready, arvalid, arready, rvalid, rready;

    spi_axil_bridge u_spi (
        .clk(clk), .rst_n(rst_n),
        .spi_sck(spi_sck), .spi_cs_n(spi_cs_n), .spi_mosi(spi_mosi), .spi_miso(spi_miso), .spi_miso_oe(spi_miso_oe),
        .m_axil_awaddr(awaddr), .m_axil_awvalid(awvalid), .m_axil_awready(awready), .m_axil_wdata(wdata),
        .m_axil_wstrb(wstrb), .m_axil_wvalid(wvalid), .m_axil_wready(wready), .m_axil_bresp(bresp),
        .m_axil_bvalid(bvalid), .m_axil_bready(bready), .m_axil_araddr(araddr), .m_axil_arvalid(arvalid),
        .m_axil_arready(arready), .m_axil_rdata(rdata), .m_axil_rresp(rresp), .m_axil_rvalid(rvalid),
        .m_axil_rready(rready)
    );

    coldtrack_top #(.BERKAS_SIMPUL(BERKAS_SIMPUL), .BERKAS_POHON(BERKAS_POHON), .BERKAS_BASE(BERKAS_BASE),
                    .MODEL_FLASH(MODEL_FLASH), .HASH_MODEL(HASH_MODEL), .SETENGAH_SCK(SETENGAH_SCK)) u_ct (
        .clk(clk), .rst_n(rst_n),
        .s_axil_awaddr(awaddr), .s_axil_awvalid(awvalid), .s_axil_awready(awready), .s_axil_wdata(wdata),
        .s_axil_wstrb(wstrb), .s_axil_wvalid(wvalid), .s_axil_wready(wready), .s_axil_bresp(bresp),
        .s_axil_bvalid(bvalid), .s_axil_bready(bready), .s_axil_araddr(araddr), .s_axil_arvalid(arvalid),
        .s_axil_arready(arready), .s_axil_rdata(rdata), .s_axil_rresp(rresp), .s_axil_rvalid(rvalid),
        .s_axil_rready(rready),
        .alarm_waspada(alarm_waspada), .alarm_kritis(alarm_kritis), .alarm_sensor(alarm_sensor),
        .qspi_sck(qspi_sck), .qspi_cs_n(qspi_cs_n), .qspi_io_o(qspi_io_o), .qspi_io_oe(qspi_io_oe),
        .qspi_io_i(qspi_io_i)
    );
endmodule
