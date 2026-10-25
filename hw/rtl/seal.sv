// Segel data: rantai hash per bacaan sensor dan HMAC-SHA256 per paket hasil, berbagi satu sha256_core.
//
// Rantai : h_i = SHA256(h_{i-1} || rekaman_i), rekaman 23 byte (format di hw/golden/seal.py).
//          32 + 23 = 55 byte muat satu blok: {h_prev, rekaman, 8'h80, 64'd440}.
// HMAC   : HMAC-SHA256(kunci 32 byte, rantai || hasil 16 byte) = 4 kompresi:
//          SHA(K^ipad) -> SHA(.., {pesan 48 B, 0x80, 0, len 896}) -> SHA(K^opad) -> SHA(.., {dalam, 0x80, 0, len 768}).
// Kunci hanya bisa ditulis sebelum dikunci (kunci_kunci); tidak ada jalur baca balik kunci.
module seal (
    input  logic         clk,
    input  logic         rst_n,
    // kunci HMAC
    input  logic         kunci_tulis,
    input  logic [255:0] kunci_data,
    input  logic         kunci_kunci,      // setelah 1, kunci tidak bisa diubah sampai reset
    output logic         kunci_terkunci,
    // rantai hash
    input  logic         rantai_reset,     // h <- 0 (awal trip)
    input  logic         segel_start,
    input  logic [183:0] rekaman,
    output logic [255:0] rantai,
    // HMAC atas {rantai, hasil}
    input  logic         mac_start,
    input  logic [127:0] hasil,
    output logic [255:0] mac,
    output logic         busy,
    output logic         done              // pulsa 1 siklus setelah segel atau mac selesai
);
    localparam logic [511:0] IPAD = {64{8'h36}};
    localparam logic [511:0] OPAD = {64{8'h5c}};

    typedef enum logic [2:0] {DIAM, SEGEL, MAC_IPAD, MAC_PESAN, MAC_OPAD, MAC_LUAR} tahap_t;
    tahap_t tahap;

    logic [255:0] kunci;
    logic [255:0] h_dalam;
    logic         c_start, c_use_iv, c_busy, c_done;
    logic [255:0] c_h_in, c_h_out;
    logic [511:0] c_block;

    sha256_core u_sha (
        .clk(clk), .rst_n(rst_n), .start(c_start), .use_iv(c_use_iv), .h_in(c_h_in),
        .block(c_block), .busy(c_busy), .done(c_done), .h_out(c_h_out)
    );

    assign busy = (tahap != DIAM);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap          <= DIAM;
            kunci          <= '0;
            kunci_terkunci <= 1'b0;
            rantai         <= '0;
            mac            <= '0;
            h_dalam        <= '0;
            c_start        <= 1'b0;
            c_use_iv       <= 1'b0;
            c_h_in         <= '0;
            c_block        <= '0;
            done           <= 1'b0;
        end else begin
            c_start <= 1'b0;
            done    <= 1'b0;
            if (kunci_tulis && !kunci_terkunci) kunci <= kunci_data;
            if (kunci_kunci) kunci_terkunci <= 1'b1;

            case (tahap)
                DIAM: if (!c_busy) begin
                    if (rantai_reset) begin
                        rantai <= '0;
                    end else if (segel_start) begin
                        c_block  <= {rantai, rekaman, 8'h80, 64'd440};
                        c_use_iv <= 1'b1;
                        c_start  <= 1'b1;
                        tahap    <= SEGEL;
                    end else if (mac_start) begin
                        c_block  <= {kunci, 256'd0} ^ IPAD;
                        c_use_iv <= 1'b1;
                        c_start  <= 1'b1;
                        tahap    <= MAC_IPAD;
                    end
                end
                SEGEL: if (c_done) begin
                    rantai <= c_h_out;
                    done   <= 1'b1;
                    tahap  <= DIAM;
                end
                MAC_IPAD: if (c_done) begin
                    c_block  <= {rantai, hasil, 8'h80, 56'd0, 64'd896};
                    c_h_in   <= c_h_out;
                    c_use_iv <= 1'b0;
                    c_start  <= 1'b1;
                    tahap    <= MAC_PESAN;
                end
                MAC_PESAN: if (c_done) begin
                    h_dalam  <= c_h_out;
                    c_block  <= {kunci, 256'd0} ^ OPAD;
                    c_use_iv <= 1'b1;
                    c_start  <= 1'b1;
                    tahap    <= MAC_OPAD;
                end
                MAC_OPAD: if (c_done) begin
                    c_block  <= {h_dalam, 8'h80, 184'd0, 64'd768};
                    c_h_in   <= c_h_out;
                    c_use_iv <= 1'b0;
                    c_start  <= 1'b1;
                    tahap    <= MAC_LUAR;
                end
                MAC_LUAR: if (c_done) begin
                    mac   <= c_h_out;
                    done  <= 1'b1;
                    tahap <= DIAM;
                end
                default: tahap <= DIAM;
            endcase
        end
    end
endmodule
