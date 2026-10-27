// Inferensi tree ensemble dari aliran rekaman 72 bit (image flash, format di hw/golden/flash_image.py).
// Simpul satu pohon lewat berurutan dan anak selalu sesudah induk, jadi cukup satu penunjuk "simpul yang
// ditunggu" untuk pohon yang sedang lewat; simpul lain dilewati. Hasil identik dengan tree_engine.sv.
// galat = struktur tidak sah (indeks fitur di luar jangkauan, anak tidak sesudah induk, pohon habis sebelum
// daun, atau jumlah simpul tidak cocok); header buruk -> hdr_ok = 0. Isi image dijamin hash di model_flash.sv.
module tree_stream #(
    parameter int N_FITUR    = 82,
    parameter int N_KELAS    = 7,
    parameter int FW         = 48,
    parameter int SW         = 32,
    parameter int MAX_POHON  = 1024,
    parameter int MAX_SIMPUL = 16384
) (
    input  logic                  clk,
    input  logic                  rst_n,
    // fitur
    input  logic                  fitur_we,
    input  logic [6:0]            fitur_addr,
    input  logic signed [FW-1:0]  fitur_data,
    // aliran rekaman
    input  logic                  mulai,
    input  logic                  rek_valid,
    input  logic [71:0]           rek,
    output logic                  hdr_siap,     // header sudah dibaca
    output logic                  hdr_ok,
    output logic [16:0]           n_rek,        // jumlah rekaman seluruh image (valid saat hdr_siap)
    output logic                  selesai,      // rekaman terakhir sudah diproses
    output logic                  galat,
    output logic [N_KELAS*SW-1:0] skor,
    output logic [2:0]            kelas
);
    typedef enum logic [2:0] {HEADER, BASE, POHON, SIMPUL, SELESAI} tahap_t;
    tahap_t tahap;

    logic signed [FW-1:0] fitur [N_FITUR];
    always_ff @(posedge clk) if (fitur_we) fitur[fitur_addr] <= fitur_data;

    logic [15:0]          n_pohon, n_simpul, p, sisa, idx, tunggu;
    logic [2:0]           k, kelas_p;
    logic                 aktif;
    logic signed [SW-1:0] acc [N_KELAS];

    wire                  daun    = rek[71];
    wire [6:0]            fi      = rek[70:64];
    wire signed [FW-1:0]  ambang  = rek[63:16];
    wire [15:0]           kiri    = rek[15:0];
    wire signed [SW-1:0]  nilai   = rek[SW-1:0];
    wire                  fi_ok   = (fi < 7'(N_FITUR));
    wire                  ke_kiri = fi_ok && (fitur[fi_ok ? fi : 7'd0] < ambang);
    wire                  kena    = aktif && (idx == tunggu);
    wire                  aktif_n = aktif && !(kena && daun);

    wire hdr_baik = rek[71:56] == 16'h4354 && rek[55:48] == 8'd1 && rek[15:8] == 8'(N_KELAS)
                  && rek[47:32] != 0 && rek[47:32] <= 16'(MAX_POHON)
                  && rek[31:16] != 0 && rek[31:16] <= 16'(MAX_SIMPUL);

    assign selesai = (tahap == SELESAI);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= HEADER; hdr_siap <= 1'b0; hdr_ok <= 1'b0; n_rek <= '0; galat <= 1'b0;
            n_pohon <= '0; n_simpul <= '0; p <= '0; sisa <= '0; idx <= '0; tunggu <= '0; k <= '0; kelas_p <= '0;
            aktif <= 1'b0;
            for (int i = 0; i < N_KELAS; i++) acc[i] <= '0;
        end else if (mulai) begin
            tahap <= HEADER; hdr_siap <= 1'b0; hdr_ok <= 1'b0; galat <= 1'b0; p <= '0; idx <= '0; k <= '0;
            aktif <= 1'b0;
            for (int i = 0; i < N_KELAS; i++) acc[i] <= '0;
        end else if (rek_valid)
            case (tahap)
                HEADER: begin
                    hdr_siap <= 1'b1;
                    hdr_ok   <= hdr_baik;
                    n_pohon  <= rek[47:32];
                    n_simpul <= rek[31:16];
                    n_rek    <= 17'(N_KELAS + 1) + 17'(rek[47:32]) + 17'(rek[31:16]);
                    tahap    <= hdr_baik ? BASE : SELESAI;
                end
                BASE: begin
                    acc[k] <= rek[SW-1:0];
                    k      <= k + 3'd1;
                    if (k == 3'(N_KELAS - 1)) tahap <= POHON;
                end
                POHON: begin
                    kelas_p <= rek[18:16];
                    sisa    <= rek[15:0];
                    tunggu  <= idx;
                    aktif   <= 1'b1;
                    if (rek[15:0] == 0 || rek[18:16] >= 3'(N_KELAS)) galat <= 1'b1;
                    tahap   <= SIMPUL;
                end
                SIMPUL: begin
                    if (kena) begin
                        if (daun) acc[kelas_p] <= acc[kelas_p] + nilai;
                        else begin
                            if (!fi_ok || kiri <= idx) galat <= 1'b1;
                            tunggu <= ke_kiri ? kiri : kiri + 16'd1;
                        end
                    end
                    aktif <= aktif_n;
                    idx   <= idx + 16'd1;
                    sisa  <= sisa - 16'd1;
                    if (sisa == 16'd1) begin
                        if (aktif_n) galat <= 1'b1;                    // pohon habis sebelum daun
                        p <= p + 16'd1;
                        if (p == n_pohon - 16'd1) begin
                            if (idx + 16'd1 != n_simpul) galat <= 1'b1;
                            tahap <= SELESAI;
                        end else
                            tahap <= POHON;
                    end
                end
                default: galat <= 1'b1;                                // rekaman lebih dari header
            endcase
    end

    // skor dan argmax (seri -> indeks terkecil), sama dengan tree_engine.sv
    always_comb begin
        logic signed [SW-1:0] terbaik;
        terbaik = acc[0];
        kelas   = 3'd0;
        for (int i = 0; i < N_KELAS; i++) begin
            skor[i*SW +: SW] = acc[i];
            if (acc[i] > terbaik) begin
                terbaik = acc[i];
                kelas   = 3'(i);
            end
        end
    end
endmodule
