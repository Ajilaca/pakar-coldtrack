// Model perilaku flash QSPI untuk simulasi: hanya perintah 0x6B (Fast Read Quad Output), mode SPI 0.
// Dua isi (A dan B) dipilih lewat pakai_b untuk uji tukar model; isi A bisa ditimpa per byte (uji manipulasi).
// perintah_salah = 1 bila perintah bukan 0x6B atau IO1 ikut dikemudikan chip saat fase perintah.
module spi_flash_model #(
    parameter     BERKAS_A = "",
    parameter     BERKAS_B = "",
    parameter int UKURAN   = 131072
) (
    input  logic        clk,
    input  logic        sck,
    input  logic        cs_n,
    input  logic [3:0]  io_dut,
    input  logic [3:0]  oe_dut,
    output logic [3:0]  io_flash,
    input  logic        pakai_b,
    input  logic        tulis,
    input  logic [16:0] tulis_addr,
    input  logic [7:0]  tulis_data,
    output logic        perintah_salah,
    output logic [31:0] jumlah_byte       // byte yang sudah dikirim sejak CS turun
);
    logic [7:0] mem_a [UKURAN];
    logic [7:0] mem_b [UKURAN];
    initial begin
        if (BERKAS_A != "") $readmemh(BERKAS_A, mem_a);
        if (BERKAS_B != "") $readmemh(BERKAS_B, mem_b);
    end
    always_ff @(posedge clk) if (tulis) mem_a[tulis_addr] <= tulis_data;

    logic [31:0] naik;            // tepi naik SCK sejak CS turun
    logic [31:0] sr;
    logic        salah;

    always @(posedge sck or posedge cs_n) begin
        if (cs_n) begin
            naik  <= '0;
            salah <= 1'b0;
        end else begin
            if (naik < 32) begin
                sr <= {sr[30:0], io_dut[0]};
                if (oe_dut[1]) salah <= 1'b1;
            end
            if (naik == 32 && sr[31:24] != 8'h6B) salah <= 1'b1;
            naik <= naik + 1;
        end
    end

    // data: nibble ke-j keluar sesudah tepi turun yang menyusul tepi naik ke-(40 + j)
    always @(negedge sck or posedge cs_n) begin
        if (cs_n) io_flash <= 4'h0;
        else if (naik >= 40) begin
            automatic int j = int'(naik) - 40;
            automatic int a = int'(sr[23:0]) + j / 2;
            automatic logic [7:0] v = pakai_b ? mem_b[a % UKURAN] : mem_a[a % UKURAN];
            io_flash <= (j % 2 == 0) ? v[7:4] : v[3:0];
        end
    end

    assign perintah_salah = salah;
    assign jumlah_byte    = (naik > 40) ? (naik - 40) / 2 : 0;
endmodule
