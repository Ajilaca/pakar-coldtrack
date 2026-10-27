// Pembaca flash QSPI berurutan: perintah 0x6B (Fast Read Quad Output), mode SPI 0, mulai dari ALAMAT.
// Perintah dan alamat 24 bit lewat IO0 (IO2/IO3 ditahan 1), 8 siklus dummy, lalu 4 bit per siklus SCK,
// nibble atas dulu. SCK = clk / (2*SETENGAH). Flash mengganti data sesudah tepi turun; data dicuplik pada clk
// yang menaikkan SCK. Sebelum tiap byte siap dicek: bila 0, SCK ditahan rendah dan flash menahan keluarannya,
// jadi konsumen tidak pernah kebanjiran. Bit QE flash harus sudah 1 (diset saat flash diprogram).
module qspi_reader #(
    parameter logic [23:0] ALAMAT   = 24'h000000,
    parameter int          SETENGAH = 1
) (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       mulai,        // pulsa: CS turun, kirim perintah, alirkan data
    input  logic       henti,        // pulsa: CS naik, kembali diam
    input  logic       siap,         // konsumen sanggup menerima satu byte lagi
    output logic       byte_valid,
    output logic [7:0] byte_data,
    // pin flash (penyangga tiga keadaan di pad / IOBUF)
    output logic       sck,
    output logic       cs_n,
    output logic [3:0] io_o,
    output logic [3:0] io_oe,
    input  logic [3:0] io_i
);
    typedef enum logic [1:0] {DIAM, PERINTAH, DUMMY, DATA} tahap_t;
    tahap_t tahap;

    localparam int FW = (SETENGAH > 1) ? $clog2(SETENGAH) : 1;
    logic [FW-1:0] fase;
    logic [31:0]   sr;
    logic [5:0]    n;
    logic          nib;            // 0 = nibble atas berikutnya
    logic [3:0]    atas;

    wire tik  = (fase == FW'(SETENGAH - 1));
    wire naik = tik && !sck && !(tahap == DATA && !nib && !siap);

    assign io_o  = {2'b11, 1'b0, sr[31]};
    assign io_oe = (tahap == PERINTAH) ? 4'b1101 : 4'b0000;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= DIAM; fase <= '0; sr <= '0; n <= '0; nib <= 1'b0; atas <= '0;
            sck <= 1'b0; cs_n <= 1'b1; byte_valid <= 1'b0; byte_data <= '0;
        end else begin
            byte_valid <= 1'b0;
            if (henti) begin
                tahap <= DIAM;
                sck   <= 1'b0;
                cs_n  <= 1'b1;
            end else if (mulai) begin
                tahap <= PERINTAH;
                sr    <= {8'h6B, ALAMAT};
                n     <= 6'd32;
                fase  <= '0;
                sck   <= 1'b0;
                cs_n  <= 1'b0;
            end else if (tahap != DIAM) begin
                if (!tik) fase <= fase + 1'b1;
                else if (naik) begin
                    fase <= '0;
                    sck  <= 1'b1;
                    if (tahap == DATA) begin
                        nib <= !nib;
                        if (nib) begin
                            byte_data  <= {atas, io_i};
                            byte_valid <= 1'b1;
                        end else
                            atas <= io_i;
                    end
                end else if (sck) begin                       // tepi turun
                    fase <= '0;
                    sck  <= 1'b0;
                    case (tahap)
                        PERINTAH: begin
                            sr <= sr << 1;
                            n  <= n - 6'd1;
                            if (n == 6'd1) begin
                                tahap <= DUMMY;
                                n     <= 6'd8;
                            end
                        end
                        DUMMY: begin
                            n <= n - 6'd1;
                            if (n == 6'd1) begin
                                tahap <= DATA;
                                nib   <= 1'b0;
                            end
                        end
                        default: ;
                    endcase
                end
                // tik, SCK rendah, menunggu siap: tetap di tempat
            end
        end
    end
endmodule
