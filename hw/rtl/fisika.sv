// Mesin fisika ColdTrack (port bit-exact dari hw/golden/fisika.py, asal backend/app/core/engine.py).
// Per sampel menit: aturan sensor -> observer suhu muatan -> pencarian TTB T=0..60 -> status AMAN/WASPADA/KRITIS.
// Satuan suhu 0,01 C; Tc dan ts10 = 0,01 C x 2^16; k dan e^-k Q0.40 dari host sekali per trip.
// Riwayat <= 90 menit disimpan di register geser (aturan jendela = OR/mux kombinasional).
module fisika (
    input  logic               clk,
    input  logic               rst_n,
    // konfigurasi trip (host)
    input  logic signed [15:0] cfg_t_lo,
    input  logic signed [15:0] cfg_t_hi,
    input  logic signed [15:0] cfg_t_set,
    input  logic signed [15:0] cfg_batas_waspada,
    input  logic [40:0]        cfg_k,          // Q0.40
    input  logic [40:0]        cfg_ek,         // Q0.40, e^-k
    // sampel
    input  logic               trip_reset,
    input  logic               sampel,
    input  logic signed [15:0] ts_raw,
    input  logic signed [15:0] t_amb,
    input  logic               pintu,
    input  logic               bergerak,
    // hasil
    output logic               busy,
    output logic               done,
    output logic [1:0]         status,         // 0 AMAN, 1 WASPADA, 2 KRITIS
    output logic [2:0]         alasan,         // kode hw/golden/fisika.ALASAN
    output logic               ttb_valid,      // TTB <= 60 dan sensor tidak rusak
    output logic [5:0]         ttb,            // menit (ceil)
    output logic [1:0]         sensor,         // 0 ok, 1 curiga, 2 rusak
    output logic signed [39:0] tc,             // suhu muatan taksiran
    output logic signed [39:0] ts10,
    output logic               seri            // ada perbandingan tepat di ambang
);
    localparam int FRAK = 40;
    localparam int SH   = 16;
    localparam logic signed [15:0] SENSOR_MAX = 16'sd6000, SENSOR_MIN = -16'sd4000;

    // ---------------- riwayat (indeks 0 = menit sekarang) ----------------
    logic [59:0]        door_sr;
    logic [10:0]        mov_sr;
    logic [89:0]        bad_sr;
    logic signed [15:0] raw_sr   [90];
    logic signed [15:0] amb_sr   [31];
    logic signed [15:0] clean_sr [10];
    logic signed [19:0] s10_sr   [21];

    logic [15:0]        i;              // menit ke-
    logic               ada_tc;
    logic signed [15:0] last_clean;
    logic signed [15:0] prev, last_ok;
    logic               prev_ada, ok_ada;
    logic [6:0]         flat;

    typedef enum logic [2:0] {DIAM, SENSOR, OBSERVER, CARI, PUTUS} tahap_t;
    tahap_t tahap;

    // ---------------- tahap SENSOR (kombinasional atas riwayat) ----------------
    function automatic logic [59:0] topeng60(input logic [6:0] n);   // bit 0..n
        topeng60 = (n >= 7'd59) ? '1 : ((60'd1 << (n + 7'd1)) - 60'd1);
    endfunction

    wire        bad_now = bad_sr[0];
    wire signed [15:0] raw_now = raw_sr[0];
    wire [6:0]  w10     = (i >= 16'd10) ? 7'd10 : 7'(i);
    logic       sah, mov_beda;
    logic [6:0] flat_nx;
    logic [1:0] st;
    logic       ctx, bad_dlm;
    logic [6:0] f, wf;
    logic [4:0] la;
    logic signed [15:0] lompat;
    always_comb begin
        mov_beda = 1'b0;
        for (int j = 0; j <= 10; j++) if (7'(j) <= w10 && mov_sr[j] != mov_sr[0]) mov_beda = 1'b1;
        sah = |(door_sr & topeng60(w10)) | mov_beda;

        flat_nx = bad_now ? 7'd0 : ((prev_ada && raw_now == prev) ? ((flat == 7'd127) ? flat : flat + 7'd1) : 7'd0);
        f       = flat_nx;
        lompat  = raw_now - last_ok;
        st      = bad_now ? 2'd2 : 2'd0;
        ctx = 1'b0; bad_dlm = 1'b0; wf = '0; la = '0;
        if (!bad_now) begin
            if (ok_ada && (lompat > 16'sd500 || lompat < -16'sd500) && i != 0 && !sah) st = 2'd1;
            if (f >= 7'd60) st = 2'd2;
            else if (f >= 7'd15) begin
                wf  = (7'(i) < f && i < 16'd60) ? 7'(i) : f;
                la  = (i >= 16'd30) ? 5'd30 : 5'(i);
                ctx = |(door_sr & topeng60(wf)) || (amb_sr[0] - amb_sr[la] >= 16'sd300);
                for (int j = 0; j < 90; j++) if (7'(j) >= f && 7'(j) <= f + 7'd30 && bad_sr[j]) bad_dlm = 1'b1;
                if (!ctx && (i >= 16'(f) + 16'd30) && !bad_dlm)
                    ctx = (32'(raw_sr[f] - raw_sr[f + 7'd30]) * $signed({25'd0, f})) >= 32'sd900;
                if (ctx && st == 2'd0) st = 2'd1;
            end
        end
    end

    // ---------------- tahap OBSERVER: jumlah, rata-rata, hanyut ----------------
    logic [3:0]          n10, nj;
    logic signed [19:0]  s10;
    logic signed [31:0]  nj_s;         // pengali bertanda (hindari ekspresi unsigned)
    always_comb begin
        n10 = (i >= 16'd9) ? 4'd10 : 4'(i + 16'd1);
        s10 = '0;
        for (int j = 0; j < 10; j++) if (4'(j) < n10) s10 = s10 + 20'(clean_sr[j]);
        nj  = (i >= 16'd29) ? 4'd10 : 4'(i - 16'd19);
        nj_s = $signed({28'd0, nj});
    end
    function automatic logic [24:0] rec10(input logic [3:0] n);   // round(2^24 / n)
        case (n)
            4'd1: rec10 = 25'd16777216; 4'd2: rec10 = 25'd8388608; 4'd3: rec10 = 25'd5592405;
            4'd4: rec10 = 25'd4194304;  4'd5: rec10 = 25'd3355443; 4'd6: rec10 = 25'd2796203;
            4'd7: rec10 = 25'd2396745;  4'd8: rec10 = 25'd2097152; 4'd9: rec10 = 25'd1864135;
            default: rec10 = 25'd1677722;
        endcase
    endfunction

    // nilai tahap OBSERVER yang disimpan untuk CARI / PUTUS
    logic signed [39:0] thi, tlo, amb24, cab;
    logic               sudah, bisa, hanyut;
    logic signed [31:0] d20_num;
    logic signed [31:0] kiri_drift;     // 20*nj*(hi*n10 - s10)
    logic signed [19:0] s10_r;
    logic [3:0]         n10_r;
    logic signed [31:0] n10_s, s10_s, hi_s, bw_s;
    assign n10_s = $signed({28'd0, n10_r});
    assign s10_s = 32'(s10_r);
    assign hi_s  = 32'(cfg_t_hi);
    assign bw_s  = 32'(cfg_batas_waspada);

    // ---------------- tahap CARI: T = 0..60 ----------------
    logic [5:0]          t;
    logic [40:0]         p, p30;
    logic                ttb_ada;
    logic [5:0]          ttb_r;
    logic [81:0]         kanan_fisik;
    logic signed [81:0]  kiri_fisik;
    logic                fisik_t, drift_t, drift_eq;
    always_comb begin
        kiri_fisik  = 82'(cab - thi) <<< FRAK;
        kanan_fisik = 82'(p) * 82'(cab - tc);
        fisik_t  = sudah || (bisa && ($signed(kiri_fisik) >= $signed(kanan_fisik)));
        drift_t  = hanyut && (kiri_drift <= $signed({26'd0, t}) * d20_num);
        drift_eq = hanyut && (kiri_drift == $signed({26'd0, t}) * d20_num);
    end
    logic [40:0]  p_nx;
    logic [81:0]  p_kali;
    assign p_kali = 82'(p) * 82'(cfg_ek);
    assign p_nx   = 41'(p_kali >> FRAK);

    assign busy = (tahap != DIAM);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap <= DIAM; i <= '0; ada_tc <= 1'b0; last_clean <= '0; prev <= '0; last_ok <= '0;
            prev_ada <= 1'b0; ok_ada <= 1'b0; flat <= '0; door_sr <= '0; mov_sr <= '0; bad_sr <= '0;
            for (int j = 0; j < 90; j++) raw_sr[j] <= '0;
            for (int j = 0; j < 31; j++) amb_sr[j] <= '0;
            for (int j = 0; j < 10; j++) clean_sr[j] <= '0;
            for (int j = 0; j < 21; j++) s10_sr[j] <= '0;
            done <= 1'b0; status <= '0; alasan <= '0; ttb_valid <= 1'b0; ttb <= '0; sensor <= '0;
            tc <= '0; ts10 <= '0; seri <= 1'b0;
            thi <= '0; tlo <= '0; amb24 <= '0; cab <= '0; sudah <= 1'b0; bisa <= 1'b0;
            hanyut <= 1'b0; d20_num <= '0; kiri_drift <= '0; s10_r <= '0; n10_r <= '0;
            t <= '0; p <= '0; p30 <= '0; ttb_ada <= 1'b0; ttb_r <= '0;
        end else begin
            done <= 1'b0;
            case (tahap)
                DIAM: begin
                    if (trip_reset) begin
                        i <= '0; ada_tc <= 1'b0; last_clean <= cfg_t_set; prev_ada <= 1'b0; ok_ada <= 1'b0;
                        flat <= '0; door_sr <= '0; mov_sr <= '0; bad_sr <= '0;
                    end else if (sampel) begin
                        logic b;
                        logic signed [15:0] cl;
                        b  = (ts_raw > SENSOR_MAX) || (ts_raw < SENSOR_MIN);
                        cl = b ? last_clean : ts_raw;
                        last_clean <= cl;
                        door_sr <= {door_sr[58:0], pintu};
                        mov_sr  <= {mov_sr[9:0], bergerak};
                        bad_sr  <= {bad_sr[88:0], b};
                        for (int j = 89; j > 0; j--) raw_sr[j] <= raw_sr[j - 1];
                        raw_sr[0] <= ts_raw;
                        for (int j = 30; j > 0; j--) amb_sr[j] <= amb_sr[j - 1];
                        amb_sr[0] <= t_amb;
                        for (int j = 9; j > 0; j--) clean_sr[j] <= clean_sr[j - 1];
                        clean_sr[0] <= cl;
                        tahap <= SENSOR;
                    end
                end

                SENSOR: begin
                    sensor <= st;
                    flat   <= flat_nx;
                    if (bad_now) begin
                        prev_ada <= 1'b0;
                    end else begin
                        prev <= raw_now; prev_ada <= 1'b1;
                        last_ok <= raw_now; ok_ada <= 1'b1;
                    end
                    // observer: Tc[0] = clean[0]; Tc[i] = Tc[i-1] + k (clean[i-1] - Tc[i-1])
                    if (!ada_tc) begin
                        tc <= 40'(clean_sr[0]) <<< SH;
                        ada_tc <= 1'b1;
                    end else begin
                        logic signed [39:0] beda;
                        logic signed [81:0] kali;
                        beda = (40'(clean_sr[1]) <<< SH) - tc;
                        kali = 82'($signed({1'b0, cfg_k})) * 82'(beda);
                        tc <= tc + 40'(kali >>> FRAK);
                    end
                    for (int j = 20; j > 0; j--) s10_sr[j] <= s10_sr[j - 1];
                    s10_sr[0] <= s10;
                    s10_r <= s10;
                    n10_r <= n10;
                    ts10  <= 40'((60'(s10) * 60'($signed({1'b0, rec10(n10)}))) >>> 8);
                    tahap <= OBSERVER;
                end

                OBSERVER: begin
                    logic signed [39:0] hi24, a24;
                    logic               ts10_di_atas, pake_amb, naik5;
                    logic signed [31:0] dnum;
                    hi24 = 40'(cfg_t_hi) <<< SH;
                    a24  = 40'(amb_sr[0]) <<< SH;
                    thi   <= hi24;
                    tlo   <= 40'(cfg_t_lo) <<< SH;
                    amb24 <= a24;
                    naik5 = (i >= 16'd5) && ((clean_sr[0] - clean_sr[5]) > 16'sd75);
                    ts10_di_atas = s10_s > hi_s * n10_s;
                    pake_amb = (door_sr[0] || (!mov_sr[0] && naik5)) && (32'(amb_sr[0]) * n10_s > s10_s);
                    cab   <= pake_amb ? a24 : ts10;
                    sudah <= tc >= hi24;
                    bisa  <= !(tc >= hi24) && (pake_amb ? (amb_sr[0] > cfg_t_hi) : ts10_di_atas);
                    // hanyut: (ts10[i] - ts10[i-20]) / 20 >= 0,005
                    if (i >= 16'd20) begin
                        dnum   = nj_s * s10_s - n10_s * 32'(s10_sr[20]);
                        hanyut <= (dnum >= 32'sd10 * n10_s * nj_s) && !(|(door_sr & topeng60((i >= 16'd29) ? 7'd29 : 7'(i))))
                                  && (s10_s < hi_s * n10_s);
                        seri   <= (dnum == 32'sd10 * n10_s * nj_s);
                    end else begin
                        dnum   = '0;
                        hanyut <= 1'b0;
                        seri   <= 1'b0;
                    end
                    d20_num    <= dnum;
                    kiri_drift <= 32'sd20 * nj_s * (hi_s * n10_s - s10_s);
                    // seri lain: ts10 tepat di t_hi / batas waspada, atau kenaikan 5 menit tepat 0,75 C
                    if (s10_s == bw_s * n10_s || s10_s == hi_s * n10_s || ((i >= 16'd5) && (clean_sr[0] - clean_sr[5]) == 16'sd75))
                        seri <= 1'b1;
                    t <= '0;
                    p <= 41'd1 << FRAK;
                    ttb_ada <= 1'b0;
                    ttb_r   <= '0;
                    tahap <= CARI;
                end

                CARI: begin
                    if (!ttb_ada && (fisik_t || drift_t)) begin
                        ttb_ada <= 1'b1;
                        ttb_r   <= t;
                        if (!fisik_t && drift_eq && (t == 6'd30 || t == 6'd60)) seri <= 1'b1;
                    end
                    if (t == 6'd30) p30 <= p;
                    if (t == 6'd60) tahap <= PUTUS;
                    else begin
                        t <= t + 1'b1;
                        p <= p_nx;
                    end
                end

                PUTUS: begin
                    logic [1:0] s;
                    logic [2:0] al;
                    logic       pintu_bahaya;
                    s = 2'd0; al = 3'd0;
                    if (!door_sr[0]) pintu_bahaya = 1'b0;
                    else if (tc >= thi) pintu_bahaya = 1'b1;
                    else if (amb24 <= thi) pintu_bahaya = 1'b0;
                    else pintu_bahaya = $signed(82'(amb24 - thi) <<< FRAK) >= $signed(82'(p30) * 82'(amb24 - tc));
                    if (tc >= thi || tc < tlo) begin s = 2'd2; al = 3'd1; end
                    if (ttb_ada && ttb_r <= 6'd30 && s < 2'd2) begin s = 2'd2; al = 3'd2; end
                    if (ttb_ada && s < 2'd1) begin s = 2'd1; al = 3'd2; end
                    if ((tc > (40'(cfg_batas_waspada) <<< SH) || s10_s > bw_s * n10_s) && s < 2'd1) begin
                        s = 2'd1; al = 3'd3;
                    end
                    if (pintu_bahaya && s < 2'd1) begin s = 2'd1; al = 3'd4; end
                    if (sensor == 2'd2) begin s = 2'd1; al = 3'd5; end
                    else if (sensor == 2'd1 && s < 2'd1) begin s = 2'd1; al = 3'd6; end
                    status    <= s;
                    alasan    <= al;
                    ttb       <= ttb_r;
                    ttb_valid <= ttb_ada && (sensor != 2'd2);
                    i         <= i + 1'b1;
                    done      <= 1'b1;
                    tahap     <= DIAM;
                end
                default: tahap <= DIAM;
            endcase
        end
    end

endmodule
