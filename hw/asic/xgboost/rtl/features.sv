// features versi ASIC. Fungsi dan antarmuka identik dengan hw/rtl/features.sv (versi FPGA, tidak diubah);
// hasil harus sama bit per bit dengan hw/golden/trees.py: fitur_bulat. Perbedaan dari versi FPGA:
//   A. ring buffer 256 x 111 bit lewat ring_sram.sv (4 makro DFFRAM RAM256), bukan array yang menjadi flip-flop.
//   B. jumlah kuadrat per kolom (s_sq) memakai SATU pengali kuadrat bersama, satu kolom per siklus (13 siklus per
//      entri jendela), menggantikan 13 pengali kuadrat paralel. Pembacaan jendela diperlambat: entri berikutnya
//      baru dibaca setelah entri sekarang selesai diproses. Lintasan konteks (240 entri) satu entri per dua siklus,
//      karena alamat baca DFFRAM harus tetap satu siklus sesudah dicuplik (lihat ring_sram.sv).
// Latensi per sampel naik dari ~650 menjadi ~1.450 siklus; tetap jauh di bawah jeda satu menit.
//
// Satuan masukan = rekaman segel: suhu/ambien/rh/kecepatan 0,01; radiasi 1/16 W/m2; duty 1/10000.
// Fitur hanya dihitung bila menit >= 59 (siap). Suhu hilang (temp_ok=0) diisi nilai terakhir;
// lengkap=0 bila ada bacaan hilang di jendela + 1 menit sebelumnya (dataset membuang jendela seperti itu).
module features #(
    parameter int FW      = 48,
    parameter int N_FITUR = 82       // 76 = tanpa statistik duty
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 trip_reset,
    input  logic                 sampel,
    input  logic                 temp_ok,
    input  logic signed [15:0]   temp,
    input  logic signed [15:0]   amb,
    input  logic [15:0]          solar,
    input  logic [15:0]          rh,
    input  logic [15:0]          speed,
    input  logic [15:0]          duty,
    input  logic                 door,
    input  logic                 reefer,
    input  logic [7:0]           harsh,
    input  logic [4:0]           hour,
    output logic                 busy,
    output logic                 done,
    output logic [15:0]          menit,
    output logic                 siap,
    output logic                 lengkap,
    output logic                 fitur_we,
    output logic [6:0]           fitur_addr,
    output logic signed [FW-1:0] fitur_data
);
    localparam int NK = 13;          // 12 kolom jendela + duty
    localparam int XW = 18;

    // ---------------- ring buffer (A: makro DFFRAM) ----------------
    // [15:0] temp_ff | [31:16] amb | [47:32] solar | [63:48] rh | [79:64] speed | [95:80] duty |
    // [103:96] harsh | [108:104] hour | [109] door | [110] reefer
    // Register alamat/kontrol port RAM: satu salinan per makro (indeks = nomor makro), lihat "register port RAM"
    // di bawah. Nilai keempat salinan selalu identik.
    logic [3:0][7:0] rd_addr;
    logic [110:0] rd_r;              // keluaran baca makro, setara register rd_r versi FPGA
    (* keep = "true" *) logic [110:0] rd_q;
    logic [3:0]      wr_en;
    logic [3:0][7:0] wr_addr;
    logic [110:0] wr_data;

    ring_sram u_ring (
        .clk(clk), .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data), .rd_addr(rd_addr), .rd_data(rd_r)
    );
    always_ff @(posedge clk) rd_q <= rd_r;

    typedef enum logic [3:0] {DIAM, JENDELA, KONTEKS, RATA, RATA_N, RATA_TUNGGU, MIRING, MIRING_N, MIRING_TUNGGU, KELUAR} tahap_t;
    tahap_t tahap;

    logic [15:0]        t_next;
    logic signed [15:0] last_ff;
    logic [59:0]        hilang;    // bit 0 = menit terbaru

    // ---------------- penjadwal baca + pipa tag (3 tahap: alamat -> data RAM -> data) ----------------
    logic [8:0] iss, n_iss;          // indeks yang diterbitkan / jumlah
    logic [7:0] dasar;               // alamat entri indeks 1 (jendela) atau 0 (konteks)
    logic       va, vm, vb;
    logic [8:0] ia, im, ib;
    logic       jsibuk;              // jendela: satu entri sedang dibaca/diproses, entri berikutnya ditahan
    logic       kjeda;               // konteks: siklus jeda sesudah tiap baca, alamat ditahan untuk mux keluaran DFFRAM
    // terbitkan baca: konteks satu per dua siklus; jendela satu entri per kali (tunggu entri selesai)
    wire        terbit = (tahap == JENDELA || tahap == KONTEKS) && iss < n_iss
                       && ((tahap == KONTEKS) ? !kjeda : !jsibuk);

    // ---------------- akumulator jendela ----------------
    logic signed [31:0]   s_sum   [NK];
    logic signed [47:0]   s_sq    [NK];
    logic signed [XW-1:0] s_min   [NK], s_max [NK], s_first [NK], s_last [NK];
    logic signed [15:0]   prev_t;
    logic [6:0]           rdur;

    // ---------------- pengali kuadrat bersama (B) ----------------
    logic                 sq_aktif;
    logic [3:0]           sq_c;      // kolom yang sedang dikuadratkan, 0..NK-1
    logic signed [XW-1:0] sq_x;
    logic [XW-1:0]        sq_abs;
    logic [2*XW-1:0]      sq_hasil;  // |x|^2 = x^2, muat 36 bit

    // ---------------- akumulator konteks ----------------
    logic [8:0]          m;
    logic signed [31:0]  s240;
    logic signed [47:0]  sxy;
    logic signed [15:0]  y_first, y_last;
    logic signed [FW-1:0] rata, miring;

    // ---------------- pembagi ----------------
    logic                bg_start, bg_busy, bg_done;
    logic signed [71:0]  bg_n;
    logic signed [71:0]  num_r;        // pembilang sebelum geser, register pemutus jalur
    /* verilator lint_off UNUSEDSIGNAL */
    logic signed [71:0]  bg_q;         // nilai fitur muat di FW bit; bit atas tidak dipakai
    /* verilator lint_on UNUSEDSIGNAL */
    logic [33:0]         bg_d;
    floor_div #(.NW(72), .DW(34)) u_bagi (
        .clk(clk), .rst_n(rst_n), .start(bg_start), .n(bg_n), .d(bg_d), .busy(bg_busy), .done(bg_done), .q(bg_q)
    );

    // ---------------- dekode data buffer + nilai kolom ----------------
    wire signed [15:0] d_temp  = rd_q[15:0];
    wire signed [15:0] d_amb   = rd_q[31:16];
    wire [6:0]         rdur_nx = rd_q[110] ? ((ib == 9'd1) ? 7'd1 : rdur + 7'd1) : 7'd0;
    logic signed [XW-1:0] x [NK];
    always_comb begin
        x[0]  = XW'(d_temp);
        x[1]  = XW'(d_temp) - XW'(prev_t);
        x[2]  = XW'(d_amb);
        x[3]  = XW'(d_temp) - XW'(d_amb);
        x[4]  = XW'({1'b0, rd_q[47:32]});
        x[5]  = XW'({1'b0, rd_q[63:48]});
        x[6]  = XW'(rd_q[109]);
        x[7]  = XW'(rd_q[110]);
        x[8]  = XW'(rdur_nx);
        x[9]  = XW'({1'b0, rd_q[79:64]});
        x[10] = XW'(rd_q[103:96]);
        x[11] = XW'(rd_q[108:104]);
        x[12] = XW'({1'b0, rd_q[95:80]});
    end

    // kuadrat kolom sq_c. x stabil selama 13 siklus kuadrat: alamat baca tidak berubah (rd_q tetap) dan prev_t/rdur
    // baru diperbarui setelah kolom terakhir.
    always_comb begin
        sq_x     = x[(sq_c < 4'(NK)) ? sq_c : 4'd0];
        sq_abs   = sq_x[XW-1] ? XW'(-sq_x) : XW'(sq_x);
        sq_hasil = (2*XW)'(sq_abs) * (2*XW)'(sq_abs);
    end

    // ---------------- keluaran fitur ----------------
    logic [6:0] o;
    logic [2:0] o_stat;
    logic [3:0] o_kol;
    logic signed [FW-1:0] nilai_o;
    logic [3:0]  kol;
    logic [2:0]  stat;
    always_comb begin
        kol  = (o >= 7'd76) ? 4'd12 : o_kol;
        stat = o_stat;
        case (stat)
            3'd0: nilai_o = FW'(s_sum[kol]);
            3'd1: nilai_o = FW'(60 * s_sq[kol] - FW'(s_sum[kol]) * FW'(s_sum[kol]));
            3'd2: nilai_o = FW'(s_min[kol]);
            3'd3: nilai_o = FW'(s_max[kol]);
            3'd4: nilai_o = FW'(s_last[kol]);
            default: nilai_o = FW'(s_last[kol]) - FW'(s_first[kol]);
        endcase
        if (o >= 7'd72 && o < 7'd76) begin
            case (o)
                7'd72:   nilai_o = FW'(menit);
                7'd73:   nilai_o = FW'(y_last) - FW'(y_first);
                7'd74:   nilai_o = rata;
                default: nilai_o = miring;
            endcase
        end
    end

    // ---------------- register port RAM ----------------
    // Empat makro berjauhan; tiap makro punya salinan register alamat/kontrolnya sendiri supaya kabel ke pinnya
    // pendek, ditulis sebagai sel sky130_fd_sc_hd__dfrtp_4 eksplisit: flip-flop hasil inferensi yang identik akan
    // digabung lagi oleh sintesis (opt_merge), sel library tidak. Kondisinya sama persis dengan cabang DIAM (tulis)
    // dan JENDELA/KONTEKS (baca, `terbit`) di always_ff utama; salinan 0 dipakai sebagai nilai sekarang.
    logic [7:0] rd_addr_nx, wr_addr_nx;
    logic       wr_en_nx;
    always_comb begin
        wr_en_nx   = (tahap == DIAM) && !trip_reset && sampel;
        wr_addr_nx = wr_en_nx ? t_next[7:0] : wr_addr[0];
        rd_addr_nx = rd_addr[0];
        if (terbit)
            rd_addr_nx = (tahap == JENDELA)
                       ? ((iss == 9'd0) ? ((menit >= 16'd60) ? dasar - 8'd1 : dasar) : dasar + 8'(iss - 9'd1))
                       : dasar + 8'(iss);
    end
    for (genvar k = 0; k < 4; k++) begin : g_port
        for (genvar b = 0; b < 8; b++) begin : g_bit
            sky130_fd_sc_hd__dfrtp_4 u_ra (.CLK(clk), .D(rd_addr_nx[b]), .RESET_B(rst_n), .Q(rd_addr[k][b]));
            sky130_fd_sc_hd__dfrtp_4 u_wa (.CLK(clk), .D(wr_addr_nx[b]), .RESET_B(rst_n), .Q(wr_addr[k][b]));
        end
        sky130_fd_sc_hd__dfrtp_4 u_we (.CLK(clk), .D(wr_en_nx), .RESET_B(rst_n), .Q(wr_en[k]));
    end

    assign busy = (tahap != DIAM);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= DIAM;
            t_next <= '0; last_ff <= '0; hilang <= '0; menit <= '0; siap <= 1'b0; lengkap <= 1'b0;
            done <= 1'b0; wr_data <= '0;
            iss <= '0; n_iss <= '0; dasar <= '0; va <= 1'b0; vm <= 1'b0; vb <= 1'b0; ia <= '0; im <= '0; ib <= '0;
            jsibuk <= 1'b0; kjeda <= 1'b0; sq_aktif <= 1'b0; sq_c <= '0;
            prev_t <= '0; rdur <= '0; m <= '0; s240 <= '0; sxy <= '0; y_first <= '0; y_last <= '0;
            rata <= '0; miring <= '0; bg_start <= 1'b0; bg_n <= '0; bg_d <= '0; num_r <= '0;
            o <= '0; o_stat <= '0; o_kol <= '0; fitur_we <= 1'b0; fitur_addr <= '0; fitur_data <= '0;
            for (int c = 0; c < NK; c++) begin
                s_sum[c] <= '0; s_sq[c] <= '0; s_min[c] <= '0; s_max[c] <= '0; s_first[c] <= '0; s_last[c] <= '0;
            end
        end else begin
            done     <= 1'b0;
            bg_start <= 1'b0;
            fitur_we <= 1'b0;
            vm <= va;
            im <= ia;
            vb <= vm;
            ib <= im;
            va <= 1'b0;
            kjeda <= terbit && (tahap == KONTEKS);

            case (tahap)
                DIAM: begin
                    if (trip_reset) begin
                        t_next <= '0; last_ff <= '0; hilang <= '0; siap <= 1'b0; lengkap <= 1'b0;
                    end else if (sampel) begin
                        logic signed [15:0] tff;
                        logic [60:0]        h;
                        tff = temp_ok ? temp : last_ff;
                        h   = {hilang[59:0], ~temp_ok};
                        wr_data <= {reefer, door, hour, harsh, duty, speed, rh, solar, amb, tff};
                        last_ff <= tff;
                        hilang  <= h[59:0];
                        menit   <= t_next;
                        t_next  <= t_next + 1'b1;
                        siap    <= (t_next >= 16'd59);
                        lengkap <= (h[59:0] == '0) && (t_next < 16'd60 || !h[60]);
                        if (t_next >= 16'd59) begin
                            // lintasan jendela: indeks 0 = menit sebelum jendela, 1..60 = jendela
                            dasar  <= 8'(t_next - 16'd59);
                            iss    <= '0;
                            n_iss  <= 9'd61;
                            jsibuk <= 1'b0;
                            tahap  <= JENDELA;
                        end else begin
                            done <= 1'b1;
                        end
                    end
                end

                JENDELA, KONTEKS: begin
                    if (terbit) begin
                        // alamat baca: rd_addr_nx (register port RAM di atas)
                        if (tahap == JENDELA) jsibuk <= 1'b1;
                        va  <= 1'b1;
                        ia  <= iss;
                        iss <= iss + 1'b1;
                    end
                    // jendela: data entri tiba
                    if (vb && tahap == JENDELA) begin
                        if (ib == 9'd0) begin
                            prev_t <= d_temp;
                            jsibuk <= 1'b0;
                        end else begin
                            // semua statistik kecuali kuadrat langsung; kuadrat lewat pengali bersama (sq_aktif)
                            for (int c = 0; c < NK; c++) begin
                                if (ib == 9'd1) begin
                                    s_sum[c] <= 32'(x[c]);
                                    s_min[c] <= x[c]; s_max[c] <= x[c]; s_first[c] <= x[c];
                                end else begin
                                    s_sum[c] <= s_sum[c] + 32'(x[c]);
                                    if (x[c] < s_min[c]) s_min[c] <= x[c];
                                    if (x[c] > s_max[c]) s_max[c] <= x[c];
                                end
                                s_last[c] <= x[c];
                            end
                            sq_aktif <= 1'b1;
                            sq_c     <= '0;
                        end
                    end
                    // jendela: kuadrat satu kolom per siklus; setelah kolom terakhir entri selesai
                    if (sq_aktif) begin
                        for (int c = 0; c < NK; c++)
                            if (sq_c == 4'(c))
                                s_sq[c] <= ((ib == 9'd1) ? 48'd0 : s_sq[c]) + 48'(sq_hasil);
                        if (sq_c == 4'(NK - 1)) begin
                            sq_aktif <= 1'b0;
                            prev_t   <= d_temp;
                            rdur     <= rdur_nx;
                            jsibuk   <= 1'b0;
                            if (ib == 9'd60) begin
                                // lintasan konteks: m = min(menit+1, 240) entri terakhir
                                logic [15:0] mm;
                                mm = (menit >= 16'd239) ? 16'd240 : menit + 16'd1;
                                m     <= 9'(mm);
                                dasar <= 8'(menit - mm + 16'd1);
                                iss   <= '0;
                                n_iss <= 9'(mm);
                                s240  <= '0;
                                sxy   <= '0;
                                tahap <= KONTEKS;
                            end
                        end else
                            sq_c <= sq_c + 4'd1;
                    end
                    if (vb && tahap == KONTEKS) begin
                        s240 <= s240 + 32'(d_temp);
                        sxy  <= sxy + 48'($signed({1'b0, ib}) * d_temp);
                        if (ib == 9'd0) y_first <= d_temp;
                        if (ib == m - 9'd1) begin
                            y_last <= d_temp;
                            tahap  <= RATA;
                        end
                    end
                end

                RATA: if (!bg_busy) begin
                    // floor(((60*S240 - m*S60) << 24) / (60*m)), S60 = jumlah suhu jendela
                    num_r <= 72'(60 * 72'(s240) - 72'($signed({1'b0, m})) * 72'(s_sum[0]));
                    bg_d  <= 34'(60 * m);
                    tahap <= RATA_N;
                end
                RATA_N: begin
                    bg_n     <= num_r <<< 24;
                    bg_start <= 1'b1;
                    tahap    <= RATA_TUNGGU;
                end
                RATA_TUNGGU: if (bg_done) begin
                    rata  <= FW'(bg_q);
                    tahap <= MIRING;
                end
                MIRING: if (!bg_busy) begin
                    if (m < 9'd2) begin
                        miring <= '0;
                        o <= '0; o_stat <= '0; o_kol <= '0;
                        tahap <= KELUAR;
                    end else begin
                        // floor((12*(m*Sxy - m(m-1)/2*S240) << 24) / (m^2 (m^2 - 1)))
                        logic signed [71:0] mm, num;
                        mm  = 72'($signed({1'b0, m}));
                        num = mm * 72'(sxy) - ((mm * (mm - 1)) >>> 1) * 72'(s240);
                        num_r <= num;
                        bg_d  <= 34'(m * m) * 34'(m * m - 1);
                        tahap <= MIRING_N;
                    end
                end
                MIRING_N: begin
                    bg_n     <= (12 * num_r) <<< 24;
                    bg_start <= 1'b1;
                    tahap    <= MIRING_TUNGGU;
                end
                MIRING_TUNGGU: if (bg_done) begin
                    miring <= FW'(bg_q);
                    o <= '0; o_stat <= '0; o_kol <= '0;
                    tahap <= KELUAR;
                end

                KELUAR: begin
                    fitur_we   <= 1'b1;
                    fitur_addr <= o;
                    fitur_data <= nilai_o;
                    o <= o + 1'b1;
                    // indeks 0..71: stat = o/12, kolom = o%12; 76..81: stat = o-76 (kolom duty)
                    if (o < 7'd72) begin
                        if (o_kol == 4'd11) begin
                            o_kol  <= '0;
                            o_stat <= (o == 7'd71) ? 3'd0 : o_stat + 1'b1;
                        end else begin
                            o_kol <= o_kol + 1'b1;
                        end
                    end else if (o >= 7'd75) begin
                        o_stat <= (o == 7'd75) ? 3'd0 : o_stat + 1'b1;
                    end
                    if (o == 7'(N_FITUR - 1)) begin
                        tahap <= DIAM;
                        done  <= 1'b1;
                    end
                end
                default: tahap <= DIAM;
            endcase
        end
    end
endmodule
