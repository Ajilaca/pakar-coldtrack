// Testbench model_flash + model flash QSPI (tb/test_model_flash.py).
module model_flash_tb #(
    parameter               BERKAS_A   = "",
    parameter               BERKAS_B   = "",
    parameter logic [255:0] HASH_MODEL = '0,
    parameter int           SETENGAH   = 1
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               fitur_we,
    input  logic [6:0]         fitur_addr,
    input  logic signed [47:0] fitur_data,
    input  logic               start,
    output logic               busy,
    output logic               done,
    output logic [7:0]         pola_sah,
    output logic [7*32-1:0]    skor,
    output logic [2:0]         kelas,
    input  logic               pakai_b,
    input  logic               tulis,
    input  logic [16:0]        tulis_addr,
    input  logic [7:0]         tulis_data,
    output logic               perintah_salah,
    output logic [31:0]        jumlah_byte,
    output logic               cs_n
);
    logic       sck;
    logic [3:0] io_o, io_oe, io_flash;

    model_flash #(.HASH_MODEL(HASH_MODEL), .SETENGAH(SETENGAH)) u_dut (
        .clk(clk), .rst_n(rst_n), .fitur_we(fitur_we), .fitur_addr(fitur_addr), .fitur_data(fitur_data),
        .start(start), .busy(busy), .done(done), .pola_sah(pola_sah), .skor(skor), .kelas(kelas),
        .qspi_sck(sck), .qspi_cs_n(cs_n), .qspi_io_o(io_o), .qspi_io_oe(io_oe), .qspi_io_i(io_flash)
    );

    spi_flash_model #(.BERKAS_A(BERKAS_A), .BERKAS_B(BERKAS_B)) u_flash (
        .clk(clk), .sck(sck), .cs_n(cs_n), .io_dut(io_o), .oe_dut(io_oe), .io_flash(io_flash),
        .pakai_b(pakai_b), .tulis(tulis), .tulis_addr(tulis_addr), .tulis_data(tulis_data),
        .perintah_salah(perintah_salah), .jumlah_byte(jumlah_byte)
    );
endmodule
