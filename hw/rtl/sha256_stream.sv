// SHA-256 atas aliran byte dengan padding sendiri (FIPS 180-4), memakai sha256_core.
// mulai -> byte masuk lewat byte_valid selama siap=1 -> akhiri (pulsa setelah byte terakhir) -> padding 0x80, nol,
// panjang 64 bit -> done + digest. siap=1 berarti satu byte lagi boleh dikirim; byte saat siap=0 hilang.
// Blok penuh langsung dikompresi (core membaca blok saat start), jadi pengisian blok berikutnya tidak menunggu.
module sha256_stream (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         mulai,
    input  logic         byte_valid,
    input  logic [7:0]   byte_data,
    output logic         siap,
    input  logic         akhiri,
    output logic         done,
    output logic [255:0] digest
);
    typedef enum logic [2:0] {DIAM, ISI, PAD80, PAD0, PANJANG, TUTUP} tahap_t;
    tahap_t tahap;

    logic [511:0] blok;
    logic [6:0]   isi;          // byte di blok, 0..64
    logic [60:0]  n_byte;
    logic [63:0]  n_bit;
    logic [2:0]   k;
    logic         pertama, terakhir;

    logic         c_start, c_busy, c_done;
    logic [255:0] c_h_out;

    wire penuh = (isi == 7'd64);
    assign c_start = penuh && !c_busy;
    assign siap    = (tahap == ISI) && !penuh;

    sha256_core u_sha (
        .clk(clk), .rst_n(rst_n), .start(c_start), .use_iv(pertama), .h_in(c_h_out), .block(blok),
        .busy(c_busy), .done(c_done), .h_out(c_h_out)
    );

    // byte yang masuk blok siklus ini: dari luar saat ISI, atau byte padding
    logic       tulis;
    logic [7:0] b;
    always_comb begin
        tulis = 1'b0;
        b     = 8'h00;
        if (!penuh)
            case (tahap)
                ISI:     begin tulis = byte_valid; b = byte_data; end
                PAD80:   begin tulis = 1'b1; b = 8'h80; end
                PAD0:    tulis = (isi != 7'd56);
                PANJANG: begin tulis = 1'b1; b = n_bit[63 - 8 * k -: 8]; end
                default: ;
            endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= DIAM; blok <= '0; isi <= '0; n_byte <= '0; n_bit <= '0; k <= '0;
            pertama <= 1'b0; terakhir <= 1'b0; done <= 1'b0; digest <= '0;
        end else begin
            done <= 1'b0;
            if (tulis) begin
                blok <= {blok[503:0], b};
                isi  <= isi + 7'd1;
            end
            if (c_start) begin
                isi      <= '0;
                pertama  <= 1'b0;
                terakhir <= (tahap == TUTUP);
            end
            if (mulai) begin
                tahap <= ISI; isi <= '0; n_byte <= '0; pertama <= 1'b1; terakhir <= 1'b0;
            end else
                case (tahap)
                    ISI: begin
                        if (tulis) n_byte <= n_byte + 61'd1;
                        if (akhiri) begin
                            n_bit <= {n_byte, 3'b000};
                            tahap <= PAD80;
                        end
                    end
                    PAD80:   if (!penuh) tahap <= PAD0;
                    PAD0:    if (!penuh && isi == 7'd56) begin k <= '0; tahap <= PANJANG; end
                    PANJANG: if (!penuh) begin
                        k <= k + 3'd1;
                        if (k == 3'd7) tahap <= TUTUP;
                    end
                    TUTUP: if (c_done && terakhir) begin
                        digest <= c_h_out;
                        done   <= 1'b1;
                        tahap  <= DIAM;
                    end
                    default: ;
                endcase
        end
    end
endmodule
