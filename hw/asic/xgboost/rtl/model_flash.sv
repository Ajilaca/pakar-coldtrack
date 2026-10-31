// Versi ASIC model_flash (pengganti hw/rtl/model_flash.sv di daftar berkas ASIC, antarmuka sama): model di flash
// boleh diganti tanpa membuat chip baru. Chip tidak lagi mengunci satu hash; flash berisi image lalu tag 32 byte
//   tag = HMAC-SHA256(kunci, SHA256(image))          (dibuat oleh hw/asic/xgboost/golden/flash_tag.py)
// dan diagnosis hanya sah bila tag cocok. Kunci ditanam saat sintesis lewat parameter HASH_MODEL; namanya tetap
// karena coldtrack_top (hw/rtl, tidak diubah) meneruskan parameter dengan nama itu. Siapa pun yang memegang kunci
// bisa menerbitkan model baru; tanpa kunci, image yang diubah atau ditukar ditolak.
// Per inferensi: image dibaca dari alamat 0 dalam satu sapuan; tiap byte masuk sha256_stream sekaligus dirakit jadi
// rekaman 9 byte untuk tree_stream, lalu 32 byte sesudah image ditampung sebagai tag. sha256_stream yang sama dipakai
// dua kali lagi untuk HMAC: dalam = SHA256(K^ipad || digest), luar = SHA256(K^opad || dalam). Perbandingan dengan tag
// dicatat dua kali pada siklus berbeda sebagai pola multi-bit (pengaman glitch); pola_sah = 8'hA5 berarti sah.
// done selalu muncul, termasuk saat header buruk (baca dihentikan lebih awal).
module model_flash #(
    parameter int           N_FITUR    = 82,
    parameter int           N_KELAS    = 7,
    parameter int           FW         = 48,
    parameter int           SW         = 32,
    parameter int           MAX_POHON  = 1024,
    parameter int           MAX_SIMPUL = 16384,
    parameter logic [255:0] HASH_MODEL = '0,        // kunci HMAC model (byte pertama = bit 255..248)
    parameter logic [23:0]  ALAMAT     = 24'h000000,
    parameter int           SETENGAH   = 1
) (
    input  logic                  clk,
    input  logic                  rst_n,
    // fitur
    input  logic                  fitur_we,
    input  logic [6:0]            fitur_addr,
    input  logic signed [FW-1:0]  fitur_data,
    // jalankan
    input  logic                  start,
    output logic                  busy,
    output logic                  done,
    output logic [7:0]            pola_sah,
    output logic [N_KELAS*SW-1:0] skor,
    output logic [2:0]            kelas,
    // flash QSPI
    output logic                  qspi_sck,
    output logic                  qspi_cs_n,
    output logic [3:0]            qspi_io_o,
    output logic [3:0]            qspi_io_oe,
    input  logic [3:0]            qspi_io_i
);
    localparam logic [255:0] KUNCI = HASH_MODEL;

    typedef enum logic [2:0] {DIAM, BACA, TAG, MAC_ISI, MAC_TUNGGU, CEK1, CEK2, AKHIR} tahap_t;
    tahap_t tahap;

    logic        q_mulai, q_henti, q_siap, q_valid;
    logic [7:0]  q_byte;
    logic        h_mulai, h_valid, h_akhiri, h_siap, h_done;
    logic [7:0]  h_byte;
    logic [255:0] h_digest;
    logic        rek_valid;
    logic [71:0] rek;
    logic [63:0] rek_sr;
    logic [3:0]  rek_isi;
    logic        t_hdr_siap, t_hdr_ok, t_selesai, t_galat;
    logic [16:0] t_n_rek;
    logic [20:0] n_byte, total;
    logic [255:0] tag;           // 32 byte sesudah image
    logic [5:0]  n_tag;
    logic [255:0] pesan;         // digest image, lalu hash dalam; digeser keluar byte demi byte ke HMAC
    logic        d_siap;         // digest image sudah ditampung di pesan
    logic        m_mulai, luar;  // luar = 0: hash dalam (ipad), 1: hash luar (opad)
    logic [6:0]  j;              // byte HMAC ke-j: 0..63 kunci^pad, 64..95 pesan
    (* keep = "true" *) logic [7:0] pola1, pola2;

    qspi_reader #(.ALAMAT(ALAMAT), .SETENGAH(SETENGAH)) u_qspi (
        .clk(clk), .rst_n(rst_n), .mulai(q_mulai), .henti(q_henti), .siap(q_siap),
        .byte_valid(q_valid), .byte_data(q_byte),
        .sck(qspi_sck), .cs_n(qspi_cs_n), .io_o(qspi_io_o), .io_oe(qspi_io_oe), .io_i(qspi_io_i)
    );

    sha256_stream u_hash (
        .clk(clk), .rst_n(rst_n), .mulai(h_mulai), .byte_valid(h_valid), .byte_data(h_byte), .siap(h_siap),
        .akhiri(h_akhiri), .done(h_done), .digest(h_digest)
    );

    tree_stream #(.N_FITUR(N_FITUR), .N_KELAS(N_KELAS), .FW(FW), .SW(SW), .MAX_POHON(MAX_POHON),
                  .MAX_SIMPUL(MAX_SIMPUL)) u_pohon (
        .clk(clk), .rst_n(rst_n), .fitur_we(fitur_we), .fitur_addr(fitur_addr), .fitur_data(fitur_data),
        .mulai(q_mulai), .rek_valid(rek_valid), .rek(rek),
        .hdr_siap(t_hdr_siap), .hdr_ok(t_hdr_ok), .n_rek(t_n_rek), .selesai(t_selesai), .galat(t_galat),
        .skor(skor), .kelas(kelas)
    );

    // semua submodul direset pada tepi yang sama dengan masuk BACA, supaya status header run sebelumnya
    // (mis. header buruk, atau panjang image lain) tidak terbaca di siklus pertama
    assign q_mulai = (tahap == DIAM) && start;

    // sha256_stream: byte image dari flash saat BACA, byte HMAC buatan sendiri saat MAC_ISI
    wire [7:0] k_byte = KUNCI[255 - 8 * j[4:0] -: 8];
    wire       m_valid = (tahap == MAC_ISI) && !m_mulai && h_siap && (j < 7'd96);
    assign h_mulai = q_mulai || m_mulai;
    assign h_valid = ((tahap == BACA) && q_valid) || m_valid;
    assign h_byte  = (tahap == BACA) ? q_byte
                   : j[6] ? pesan[255:248]
                   : ((j[5] ? 8'h00 : k_byte) ^ (luar ? 8'h5C : 8'h36));

    wire cocok = (h_digest == tag);
    // sebelum header terbaca total = 9 byte, jadi pembaca berhenti tepat setelah header sampai panjangnya diketahui
    assign q_siap = ((tahap == BACA) && h_siap && (n_byte < total)) || ((tahap == TAG) && (n_tag < 6'd32));
    assign busy   = (tahap != DIAM);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= DIAM; q_henti <= 1'b0; h_akhiri <= 1'b0; done <= 1'b0;
            rek_valid <= 1'b0; rek <= '0; rek_sr <= '0; rek_isi <= '0; n_byte <= '0; total <= '0;
            tag <= '0; n_tag <= '0; pesan <= '0; d_siap <= 1'b0; m_mulai <= 1'b0; luar <= 1'b0; j <= '0;
            pola1 <= '0; pola2 <= '0; pola_sah <= '0;
        end else begin
            q_henti   <= 1'b0;
            h_akhiri  <= 1'b0;
            m_mulai   <= 1'b0;
            done      <= 1'b0;
            rek_valid <= 1'b0;
            if (q_valid && tahap == BACA) begin
                n_byte <= n_byte + 21'd1;
                if (rek_isi == 4'd8) begin
                    rek       <= {rek_sr, q_byte};
                    rek_valid <= 1'b1;
                    rek_isi   <= '0;
                end else begin
                    rek_sr  <= {rek_sr[55:0], q_byte};
                    rek_isi <= rek_isi + 4'd1;
                end
            end
            if (q_valid && tahap == TAG) begin
                tag   <= {tag[247:0], q_byte};
                n_tag <= n_tag + 6'd1;
            end
            if (m_valid) begin
                j <= j + 7'd1;
                if (j[6]) pesan <= {pesan[247:0], 8'h00};
            end
            case (tahap)
                DIAM: if (start) begin
                    n_byte   <= '0;
                    total    <= 21'd9;
                    rek_isi  <= '0;
                    n_tag    <= '0;
                    d_siap   <= 1'b0;
                    pola1    <= '0;
                    pola2    <= '0;
                    pola_sah <= '0;
                    tahap    <= BACA;
                end
                BACA: begin
                    if (t_hdr_siap && !t_hdr_ok) begin               // header buruk: berhenti, tidak sah
                        q_henti <= 1'b1;
                        tahap   <= AKHIR;
                    end else if (t_hdr_siap && total == 21'd9)
                        total <= {t_n_rek, 3'b000} + 21'(t_n_rek);  // 9 byte per rekaman
                    else if (t_hdr_siap && n_byte == total) begin     // image habis: tutup hash, lanjut baca tag
                        h_akhiri <= 1'b1;
                        tahap    <= TAG;
                    end
                end
                TAG: begin
                    if (h_done) begin
                        pesan  <= h_digest;
                        d_siap <= 1'b1;
                    end
                    if (n_tag == 6'd32 && d_siap) begin
                        q_henti <= 1'b1;
                        m_mulai <= 1'b1;
                        luar    <= 1'b0;
                        j       <= '0;
                        tahap   <= MAC_ISI;
                    end
                end
                MAC_ISI: if (j == 7'd96) begin
                    h_akhiri <= 1'b1;
                    tahap    <= MAC_TUNGGU;
                end
                MAC_TUNGGU: if (h_done) begin
                    if (!luar) begin                                 // hash dalam selesai -> hash luar
                        pesan   <= h_digest;
                        m_mulai <= 1'b1;
                        luar    <= 1'b1;
                        j       <= '0;
                        tahap   <= MAC_ISI;
                    end else
                        tahap <= CEK1;                               // h_digest = HMAC, ditahan sampai mulai lagi
                end
                CEK1: begin
                    pola1 <= cocok ? 8'hA5 : 8'h00;
                    tahap <= CEK2;
                end
                CEK2: begin
                    pola2 <= cocok ? 8'h5A : 8'h00;
                    tahap <= AKHIR;
                end
                AKHIR: begin
                    pola_sah <= (pola1 == 8'hA5 && pola2 == 8'h5A && t_hdr_ok && t_selesai && !t_galat) ? 8'hA5 : 8'h00;
                    done     <= 1'b1;
                    tahap    <= DIAM;
                end
                default: tahap <= DIAM;
            endcase
        end
    end
endmodule
