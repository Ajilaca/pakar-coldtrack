// Mesin inferensi GRU dengan bobot dari aliran byte (flash), golden: hw/asic/GRU/golden/gru_golden.py.
// Satu MAC int8 x int16 per byte bobot; bobot satu langkah waktu dibaca ulang dari WBASE di tiap langkah, jadi di chip
// hanya hidden state (LMAX x HMAX x 16 bit) dan statistik jendela yang disimpan. Dimensi model (L, H, NI, NC, T, NO),
// normalisasi masukan, dan konstanta statistik dibaca dari header image, sehingga model baru dalam batas parameter
// cukup ditulis ulang ke flash. Semua aritmetika identik bit dengan gru_golden.Fx (Q5.10, rq = (x*M + 2^(S-1)) >>> S).
//
// Aliran bobot: ws_start (satu siklus) memulai baca berurutan dari ws_addr; byte diterima saat ws_valid && ws_ready.
// Memori masukan: xin_addr dibaca dengan latensi satu siklus (x[t][f] di t*NI + f, konteks di T*NI + c).
// Keluaran out[i] (int32 Q5.10) dibaca lewat out_idx setelah done. err = header tidak sah (done tetap muncul).
module gru_engine #(
    parameter int HMAX  = 128,
    parameter int LMAX  = 3,
    parameter int NIMAX = 16,
    parameter int NCMAX = 8,
    parameter int NOMAX = 16
) (
    input  logic               clk,
    input  logic               rst_n,
    input  logic               start,
    output logic               busy,
    output logic               done,
    output logic               err,
    output logic               ws_start,
    output logic [23:0]        ws_addr,
    input  logic               ws_valid,
    input  logic [7:0]         ws_data,
    output logic               ws_ready,
    output logic [11:0]        xin_addr,
    input  logic signed [31:0] xin_data,
    input  logic [3:0]         out_idx,
    output logic signed [31:0] out_data
);
    localparam int FA  = 10;
    localparam int NN  = NIMAX + NCMAX;
    localparam logic signed [31:0] HALF = 32'sd512;

    `include "gru_lut.svh"

    typedef enum logic [5:0] {
        S_IDLE, S_HDR, S_XRD, S_XW, S_XNORM, S_XSTAT, S_WGO, S_ROW, S_ZACT, S_RACT, S_N1, S_N2, S_N3, S_COPY,
        S_CRD, S_CW, S_CNORM, S_ST1, S_ST2, S_ST3, S_ST4, S_SQ, S_HGO, S_HROW, S_DONE
    } st_t;
    // fase dalam satu baris: W baris, M lo/hi, S, bias lo/hi, lalu R baris dst.
    typedef enum logic [3:0] {P_W, P_WM0, P_WM1, P_WS, P_WB0, P_WB1, P_R, P_RM0, P_RM1, P_RS, P_RB0, P_RB1} ph_t;

    st_t st;
    ph_t ph;

    // header
    logic [7:0]  hb;          // indeks byte header
    logic [7:0]  hL, hNI, hNC, hT, hNO;
    logic [15:0] hH;
    logic [23:0] wbase, hbase;
    logic [15:0] rn, rv;
    logic [5:0]  sn, sv;
    logic signed [31:0] n_off [NN];
    logic [15:0] n_m [NN];
    logic [5:0]  n_s [NN];
    logic [4:0]  nf;          // entri normalisasi saat membaca header
    logic [2:0]  nb;          // byte dalam entri (0..6)
    logic [7:0]  hbuf [3];

    // data
    logic signed [15:0] xn [NIMAX];
    logic signed [15:0] cn [NCMAX];
    logic signed [15:0] h [LMAX][HMAX];
    logic signed [15:0] tmp [HMAX];
    logic signed [23:0] s1 [NIMAX];
    logic [39:0]        s2 [NIMAX];
    logic signed [15:0] mn [NIMAX], mx [NIMAX], fst [NIMAX], lst [NIMAX];
    logic signed [15:0] mean_r [NIMAX], std_r [NIMAX];
    logic signed [31:0] outr [NOMAX];

    // penghitung
    logic [7:0]  t;
    logic [1:0]  l;
    logic [7:0]  j;
    logic [1:0]  g;
    logic [9:0]  k;
    logic [4:0]  f;
    logic [4:0]  o;
    logic [2:0]  zg;          // kelompok fitur kepala: 0 h, 1 mean, 2 std, 3 min, 4 max, 5 last, 6 last-first, 7 konteks
    logic [4:0]  zf;

    // akumulator dan register gerbang
    logic signed [31:0] acc, gx, gxn, ghn, zpre, rpre, t1;
    logic signed [15:0] zg_r, rg_r, ng_r;
    logic [15:0]        mreg;
    logic [5:0]         sreg;
    logic [7:0]         blo;
    logic signed [47:0] vnum;
    logic [33:0]        sq_rem, sq_res, sq_bit;

    // ------------------------------------------------------------ pengali bersama 48 x 24 bertanda
    logic signed [47:0] mul_a;
    logic signed [23:0] mul_b;
    wire  signed [71:0] mul_p = mul_a * mul_b;

    function automatic logic signed [71:0] geser_bulat(input logic signed [71:0] p, input logic [5:0] s);
        logic signed [71:0] r;
        r = p + (72'sd1 <<< (s - 6'd1));
        return r >>> s;
    endfunction

    function automatic logic signed [15:0] sat16(input logic signed [71:0] v);
        if (v > 72'sd32767) return 16'sd32767;
        if (v < -72'sd32768) return -16'sd32768;
        return v[15:0];
    endfunction

    // LUT + interpolasi linear. sig: domain [-8,8) = [-8192, 8191], langkah 2^6. tanh: [-4,4) = [-4096, 4095], 2^5.
    function automatic logic signed [15:0] act(input logic signed [31:0] v, input logic is_tanh);
        logic signed [31:0] lo, vc;
        logic [14:0] u;
        logic [8:0]  idx;
        logic [5:0]  fr;
        logic [2:0]  kk;
        logic signed [11:0] a, b;
        logic signed [19:0] d;
        lo = is_tanh ? 32'sd4096 : 32'sd8192;
        kk = is_tanh ? 3'd5 : 3'd6;
        vc = (v < -lo) ? -lo : (v > lo - 1) ? lo - 1 : v;
        u  = 15'(vc + lo);
        idx = 9'(u >> kk);
        fr  = is_tanh ? {1'b0, u[4:0]} : u[5:0];
        a = is_tanh ? lut_tanh(idx) : lut_sig(idx);
        b = is_tanh ? lut_tanh(idx + 9'd1) : lut_sig(idx + 9'd1);
        d = (20'(b) - 20'(a)) * $signed({14'd0, fr}) + (20'sd1 <<< (kk - 3'd1));
        return 16'(a) + 16'(d >>> kk);
    endfunction

    // masukan MAC: lapis 0 dari xn, lapis lain dari h lapis bawah (sudah diperbarui untuk langkah ini)
    logic signed [15:0] a_in;
    always_comb begin
        if (ph == P_W) a_in = (l == 2'd0) ? xn[k[$clog2(NIMAX)-1:0]] : h[l - 2'd1][k[$clog2(HMAX)-1:0]];
        else           a_in = h[l][k[$clog2(HMAX)-1:0]];
    end

    // nilai vektor fitur kepala
    logic signed [15:0] zval;
    always_comb begin
        case (zg)
            3'd0: zval = h[hL[1:0] - 2'd1][k[$clog2(HMAX)-1:0]];
            3'd1: zval = mean_r[zf];
            3'd2: zval = std_r[zf];
            3'd3: zval = mn[zf];
            3'd4: zval = mx[zf];
            3'd5: zval = lst[zf];
            3'd6: zval = sat16(72'(lst[zf]) - 72'(fst[zf]));
            default: zval = cn[zf[$clog2(NCMAX)-1:0]];
        endcase
    end

    wire signed [7:0]  wb    = ws_data;
    wire signed [23:0] mac_p = wb * (st == S_HROW ? zval : a_in);
    wire [15:0] in_len  = (l == 2'd0) ? {8'd0, hNI} : hH;
    wire [15:0] nz_len  = hH + 16'(hNI) * 16'd6 + 16'(hNC);
    wire        is_row  = (st == S_ROW) || (st == S_HROW);
    assign ws_ready = ((st == S_HDR) || is_row) && !ws_start;   // byte aliran lama tidak diterima saat restart
    wire        take    = ws_valid && ws_ready;

    // pemilihan operand pengali bersama
    always_comb begin
        mul_a = '0; mul_b = '0;
        case (st)
            S_ROW, S_HROW: begin mul_a = 48'(acc); mul_b = 24'(signed'({1'b0, mreg})); end  // rq di akhir baris
            S_XNORM: begin mul_a = 48'(64'(xin_data) - 64'(n_off[f])); mul_b = 24'(signed'({1'b0, n_m[f]})); end
            S_CNORM: begin mul_a = 48'(64'(xin_data) - 64'(n_off[5'(hNI) + f])); mul_b = 24'(signed'({1'b0, n_m[5'(hNI) + f]})); end
            S_XSTAT: begin mul_a = 48'(xn[f]); mul_b = 24'(xn[f]); end
            S_N1:    begin mul_a = 48'(ghn); mul_b = 24'(rg_r); end
            S_N3:    begin mul_a = 48'(32'(h[l][j[$clog2(HMAX)-1:0]]) - 32'(ng_r)); mul_b = 24'(zg_r); end
            S_ST1:   begin mul_a = 48'(s1[f]); mul_b = 24'(signed'({1'b0, rn})); end
            S_ST2:   begin mul_a = 48'(signed'({1'b0, s2[f]})); mul_b = 24'(signed'({1'b0, hT})); end
            S_ST3:   begin mul_a = 48'(s1[f]); mul_b = s1[f]; end
            S_ST4:   begin mul_a = vnum; mul_b = 24'(signed'({1'b0, rv})); end
            default: ;
        endcase
    end

    wire signed [31:0] bias16 = 32'(signed'({ws_data, blo}));
    wire signed [31:0] rq_row = 32'(geser_bulat(mul_p, sreg)) + bias16;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_IDLE; ph <= P_W; done <= 1'b0; err <= 1'b0; ws_start <= 1'b0; ws_addr <= '0; xin_addr <= '0;
            hb <= '0; nf <= '0; nb <= '0; t <= '0; l <= '0; j <= '0; g <= '0; k <= '0; f <= '0; o <= '0;
            acc <= '0;
        end else begin
            ws_start <= 1'b0;
            case (st)
                S_IDLE: if (start) begin
                    done <= 1'b0; err <= 1'b0; hb <= '0; nf <= '0; nb <= '0;
                    ws_addr <= '0; ws_start <= 1'b1; st <= S_HDR;
                end
                // ---------------------------------------------------- header
                S_HDR: if (take) begin
                    hb <= (hb == 8'd255) ? hb : hb + 8'd1;
                    if (hb < 8'd22) begin
                        case (hb)
                            8'd0: if (ws_data != 8'h47) err <= 1'b1;
                            8'd1: if (ws_data != 8'h52) err <= 1'b1;
                            8'd2: if (ws_data != 8'd1) err <= 1'b1;
                            8'd3: hL <= ws_data;
                            8'd4: hH[7:0] <= ws_data;
                            8'd5: hH[15:8] <= ws_data;
                            8'd6: hNI <= ws_data;
                            8'd7: hNC <= ws_data;
                            8'd8: hT <= ws_data;
                            8'd9: hNO <= ws_data;
                            8'd10, 8'd11, 8'd13, 8'd14: hbuf[hb == 8'd10 || hb == 8'd13 ? 0 : 1] <= ws_data;
                            8'd12: wbase <= {ws_data, hbuf[1], hbuf[0]};
                            8'd15: hbase <= {ws_data, hbuf[1], hbuf[0]};
                            8'd16: rn[7:0] <= ws_data;
                            8'd17: rn[15:8] <= ws_data;
                            8'd18: sn <= ws_data[5:0];
                            8'd19: rv[7:0] <= ws_data;
                            8'd20: rv[15:8] <= ws_data;
                            8'd21: begin
                                sv <= ws_data[5:0];
                                if (err || hL == 8'd0 || hL > 8'(LMAX) || hH == 16'd0 || hH > 16'(HMAX) || hNI == 8'd0 ||
                                    hNI > 8'(NIMAX) || hNC > 8'(NCMAX) || hT < 8'd2 || hNO == 8'd0 || hNO > 8'(NOMAX)) begin
                                    err <= 1'b1;
                                    st  <= S_DONE;
                                end
                            end
                            default: ;
                        endcase
                    end else begin
                        // entri normalisasi: off s32, M u16, S u8
                        case (nb)
                            3'd0: n_off[nf][7:0]   <= ws_data;
                            3'd1: n_off[nf][15:8]  <= ws_data;
                            3'd2: n_off[nf][23:16] <= ws_data;
                            3'd3: n_off[nf][31:24] <= ws_data;
                            3'd4: n_m[nf][7:0]     <= ws_data;
                            3'd5: n_m[nf][15:8]    <= ws_data;
                            default: n_s[nf]       <= ws_data[5:0];
                        endcase
                        nb <= (nb == 3'd6) ? 3'd0 : nb + 3'd1;
                        if (nb == 3'd6) begin
                            nf <= nf + 5'd1;
                            if (5'(nf + 5'd1) == 5'(hNI + hNC)) begin
                                // mulai: kosongkan state dan statistik
                                for (int a = 0; a < LMAX; a++) for (int b = 0; b < HMAX; b++) h[a][b] <= '0;
                                for (int a = 0; a < NIMAX; a++) begin s1[a] <= '0; s2[a] <= '0; end
                                t <= '0; f <= '0; st <= S_XRD;
                            end
                        end
                    end
                end
                // ---------------------------------------------------- masukan langkah t
                S_XRD: begin xin_addr <= 12'(16'(t) * 16'(hNI) + 16'(f)); st <= S_XW; end
                S_XW:  st <= S_XNORM;   // memori masukan boleh baca sinkron (data satu siklus sesudah alamat)
                S_XNORM: begin
                    xn[f] <= sat16(geser_bulat(mul_p, n_s[f]));
                    st <= S_XSTAT;
                end
                S_XSTAT: begin
                    s1[f] <= s1[f] + 24'(xn[f]);
                    s2[f] <= s2[f] + 40'(mul_p);
                    if (t == 8'd0) begin fst[f] <= xn[f]; mn[f] <= xn[f]; mx[f] <= xn[f]; end
                    else begin
                        if (xn[f] < mn[f]) mn[f] <= xn[f];
                        if (xn[f] > mx[f]) mx[f] <= xn[f];
                    end
                    lst[f] <= xn[f];
                    if (5'(f + 5'd1) == 5'(hNI)) begin f <= '0; st <= S_WGO; end
                    else begin f <= f + 5'd1; st <= S_XRD; end
                end
                S_WGO: begin
                    ws_addr <= wbase; ws_start <= 1'b1;
                    l <= '0; j <= '0; g <= '0; k <= '0; ph <= P_W; acc <= '0; st <= S_ROW;
                end
                // ---------------------------------------------------- satu baris gerbang
                S_ROW: if (take) begin
                    case (ph)
                        P_W: begin
                            acc <= acc + 32'(mac_p);
                            if (16'(k) + 16'd1 == in_len) begin k <= '0; ph <= P_WM0; end else k <= k + 10'd1;
                        end
                        P_WM0, P_RM0: begin mreg[7:0] <= ws_data; ph <= ph_t'(ph + 1); end
                        P_WM1, P_RM1: begin mreg[15:8] <= ws_data; ph <= ph_t'(ph + 1); end
                        P_WS, P_RS:   begin sreg <= ws_data[5:0]; ph <= ph_t'(ph + 1); end
                        P_WB0, P_RB0: begin blo <= ws_data; ph <= ph_t'(ph + 1); end
                        P_WB1: begin
                            if (g == 2'd2) gxn <= rq_row; else gx <= rq_row;
                            acc <= '0; ph <= P_R;
                        end
                        P_R: begin
                            acc <= acc + 32'(mac_p);
                            if (16'(k) + 16'd1 == hH) begin k <= '0; ph <= P_RM0; end else k <= k + 10'd1;
                        end
                        P_RB1: begin
                            acc <= '0; ph <= P_W;
                            case (g)
                                2'd0: begin zpre <= gx + rq_row; st <= S_ZACT; end
                                2'd1: begin rpre <= gx + rq_row; st <= S_RACT; end
                                default: begin ghn <= rq_row; st <= S_N1; end
                            endcase
                        end
                        default: ;
                    endcase
                end
                S_ZACT: begin zg_r <= act(zpre, 1'b0); g <= 2'd1; st <= S_ROW; end
                S_RACT: begin rg_r <= act(rpre, 1'b0); g <= 2'd2; st <= S_ROW; end
                S_N1: begin t1 <= 32'(geser_bulat(mul_p, 6'(FA))); st <= S_N2; end
                S_N2: begin ng_r <= act(gxn + t1, 1'b1); st <= S_N3; end
                S_N3: begin
                    tmp[j[$clog2(HMAX)-1:0]] <= 16'(32'(ng_r) + 32'(geser_bulat(mul_p, 6'(FA))));
                    g <= 2'd0;
                    if (16'(j) + 16'd1 == hH) begin j <= '0; k <= '0; st <= S_COPY; end
                    else begin j <= j + 8'd1; st <= S_ROW; end
                end
                S_COPY: begin
                    h[l][k[$clog2(HMAX)-1:0]] <= tmp[k[$clog2(HMAX)-1:0]];
                    if (16'(k) + 16'd1 == hH) begin
                        k <= '0;
                        if (8'(l) + 8'd1 == hL) begin
                            l <= '0;
                            if (t + 8'd1 == hT) begin f <= '0; st <= (hNC == 8'd0) ? S_ST1 : S_CRD; end
                            else begin t <= t + 8'd1; f <= '0; st <= S_XRD; end
                        end else begin l <= l + 2'd1; st <= S_ROW; end
                    end else k <= k + 10'd1;
                end
                // ---------------------------------------------------- konteks
                S_CRD: begin xin_addr <= 12'(16'(hT) * 16'(hNI) + 16'(f)); st <= S_CW; end
                S_CW:  st <= S_CNORM;
                S_CNORM: begin
                    cn[f[$clog2(NCMAX)-1:0]] <= sat16(geser_bulat(mul_p, n_s[5'(hNI) + f]));
                    if (5'(f + 5'd1) == 5'(hNC)) begin f <= '0; st <= S_ST1; end
                    else begin f <= f + 5'd1; st <= S_CRD; end
                end
                // ---------------------------------------------------- statistik per fitur
                S_ST1: begin mean_r[f] <= sat16(geser_bulat(mul_p, sn)); st <= S_ST2; end
                S_ST2: begin vnum <= 48'(mul_p); st <= S_ST3; end
                S_ST3: begin vnum <= vnum - 48'(mul_p); st <= S_ST4; end
                S_ST4: begin
                    sq_rem <= 34'(geser_bulat(mul_p, sv)); sq_res <= '0; sq_bit <= 34'd1 << 32;
                    st <= S_SQ;
                end
                // akar integer bit demi bit (17 iterasi, sq_bit 2^32 .. 2^0), hasil floor(sqrt)
                S_SQ: begin
                    if (sq_bit == 34'd0) begin
                        std_r[f] <= (sq_res > 34'd32767) ? 16'sd32767 : 16'(sq_res);
                        if (5'(f + 5'd1) == 5'(hNI)) begin f <= '0; st <= S_HGO; end
                        else begin f <= f + 5'd1; st <= S_ST1; end
                    end else begin
                        if (sq_rem >= sq_res + sq_bit) begin
                            sq_rem <= sq_rem - (sq_res + sq_bit);
                            sq_res <= (sq_res >> 1) + sq_bit;
                        end else sq_res <= sq_res >> 1;
                        sq_bit <= sq_bit >> 2;
                    end
                end
                // ---------------------------------------------------- kepala keluaran
                S_HGO: begin
                    ws_addr <= hbase; ws_start <= 1'b1; o <= '0; k <= '0; zg <= '0; zf <= '0; ph <= P_W; acc <= '0;
                    st <= S_HROW;
                end
                S_HROW: if (take) begin
                    case (ph)
                        P_W: begin
                            acc <= acc + 32'(mac_p);
                            k <= k + 10'd1;
                            // maju ke fitur berikutnya: h (H), 6 kelompok x NI, lalu NC konteks
                            if (zg == 3'd0) begin
                                if (16'(k) + 16'd1 == hH) begin zg <= 3'd1; zf <= '0; end
                            end else if (zg == 3'd7) zf <= zf + 5'd1;
                            else if (5'(zf + 5'd1) == 5'(hNI)) begin zf <= '0; zg <= (zg == 3'd6 && hNC == 8'd0) ? 3'd0 : zg + 3'd1; end
                            else zf <= zf + 5'd1;
                            if (16'(k) + 16'd1 == nz_len) ph <= P_WM0;
                        end
                        P_WM0: begin mreg[7:0] <= ws_data; ph <= P_WM1; end
                        P_WM1: begin mreg[15:8] <= ws_data; ph <= P_WS; end
                        P_WS:  begin sreg <= ws_data[5:0]; ph <= P_WB0; end
                        P_WB0: begin blo <= ws_data; ph <= P_WB1; end
                        P_WB1: begin
                            outr[o[$clog2(NOMAX)-1:0]] <= rq_row;
                            acc <= '0; k <= '0; zg <= '0; zf <= '0; ph <= P_W;
                            if (8'(o) + 8'd1 == hNO) st <= S_DONE; else o <= o + 5'd1;
                        end
                        default: ;
                    endcase
                end
                S_DONE: begin done <= 1'b1; st <= S_IDLE; end
                default: st <= S_IDLE;
            endcase
        end
    end

    assign busy     = (st != S_IDLE);
    assign out_data = outr[out_idx[$clog2(NOMAX)-1:0]];

endmodule
