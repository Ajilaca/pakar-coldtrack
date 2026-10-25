// SHA-256: kompresi satu blok 512 bit (FIPS 180-4), iteratif satu ronde per siklus.
// Latensi: start -> done = 65 siklus (64 ronde + 1 siklus penjumlahan state).
// Padding dan rantai antar-blok diatur modul pemanggil (sha256_seal, hmac_sha256).
module sha256_core (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         start,    // pulsa 1 siklus; h_in dan block dibaca saat ini
    input  logic         use_iv,   // 1 = state awal IV standar, 0 = h_in (blok lanjutan / midstate)
    input  logic [255:0] h_in,     // big-endian: H0 di [255:224]
    input  logic [511:0] block,    // big-endian: W0 di [511:480]
    output logic         busy,
    output logic         done,     // pulsa 1 siklus; h_out tetap valid sampai start berikutnya
    output logic [255:0] h_out
);
    localparam logic [255:0] IV = {
        32'h6a09e667, 32'hbb67ae85, 32'h3c6ef372, 32'ha54ff53a,
        32'h510e527f, 32'h9b05688c, 32'h1f83d9ab, 32'h5be0cd19
    };

    function automatic logic [31:0] k_ronde(input logic [5:0] t);
        case (t)
            6'd0:  k_ronde = 32'h428a2f98;  6'd1:  k_ronde = 32'h71374491;
            6'd2:  k_ronde = 32'hb5c0fbcf;  6'd3:  k_ronde = 32'he9b5dba5;
            6'd4:  k_ronde = 32'h3956c25b;  6'd5:  k_ronde = 32'h59f111f1;
            6'd6:  k_ronde = 32'h923f82a4;  6'd7:  k_ronde = 32'hab1c5ed5;
            6'd8:  k_ronde = 32'hd807aa98;  6'd9:  k_ronde = 32'h12835b01;
            6'd10: k_ronde = 32'h243185be;  6'd11: k_ronde = 32'h550c7dc3;
            6'd12: k_ronde = 32'h72be5d74;  6'd13: k_ronde = 32'h80deb1fe;
            6'd14: k_ronde = 32'h9bdc06a7;  6'd15: k_ronde = 32'hc19bf174;
            6'd16: k_ronde = 32'he49b69c1;  6'd17: k_ronde = 32'hefbe4786;
            6'd18: k_ronde = 32'h0fc19dc6;  6'd19: k_ronde = 32'h240ca1cc;
            6'd20: k_ronde = 32'h2de92c6f;  6'd21: k_ronde = 32'h4a7484aa;
            6'd22: k_ronde = 32'h5cb0a9dc;  6'd23: k_ronde = 32'h76f988da;
            6'd24: k_ronde = 32'h983e5152;  6'd25: k_ronde = 32'ha831c66d;
            6'd26: k_ronde = 32'hb00327c8;  6'd27: k_ronde = 32'hbf597fc7;
            6'd28: k_ronde = 32'hc6e00bf3;  6'd29: k_ronde = 32'hd5a79147;
            6'd30: k_ronde = 32'h06ca6351;  6'd31: k_ronde = 32'h14292967;
            6'd32: k_ronde = 32'h27b70a85;  6'd33: k_ronde = 32'h2e1b2138;
            6'd34: k_ronde = 32'h4d2c6dfc;  6'd35: k_ronde = 32'h53380d13;
            6'd36: k_ronde = 32'h650a7354;  6'd37: k_ronde = 32'h766a0abb;
            6'd38: k_ronde = 32'h81c2c92e;  6'd39: k_ronde = 32'h92722c85;
            6'd40: k_ronde = 32'ha2bfe8a1;  6'd41: k_ronde = 32'ha81a664b;
            6'd42: k_ronde = 32'hc24b8b70;  6'd43: k_ronde = 32'hc76c51a3;
            6'd44: k_ronde = 32'hd192e819;  6'd45: k_ronde = 32'hd6990624;
            6'd46: k_ronde = 32'hf40e3585;  6'd47: k_ronde = 32'h106aa070;
            6'd48: k_ronde = 32'h19a4c116;  6'd49: k_ronde = 32'h1e376c08;
            6'd50: k_ronde = 32'h2748774c;  6'd51: k_ronde = 32'h34b0bcb5;
            6'd52: k_ronde = 32'h391c0cb3;  6'd53: k_ronde = 32'h4ed8aa4a;
            6'd54: k_ronde = 32'h5b9cca4f;  6'd55: k_ronde = 32'h682e6ff3;
            6'd56: k_ronde = 32'h748f82ee;  6'd57: k_ronde = 32'h78a5636f;
            6'd58: k_ronde = 32'h84c87814;  6'd59: k_ronde = 32'h8cc70208;
            6'd60: k_ronde = 32'h90befffa;  6'd61: k_ronde = 32'ha4506ceb;
            6'd62: k_ronde = 32'hbef9a3f7;  default: k_ronde = 32'hc67178f2;
        endcase
    endfunction

    function automatic logic [31:0] rotr(input logic [31:0] x, input int n);
        rotr = (x >> n) | (x << (32 - n));
    endfunction

    logic [31:0] a, b, c, d, e, f, g, h;
    logic [31:0] w [16];           // jendela jadwal pesan: w[0] = W_t
    logic [255:0] h_awal;
    logic [5:0]  t;
    logic        jalan, tambah;

    logic [31:0] s1_e, ch, s0_a, maj, t1, t2, w_baru;
    logic [255:0] state;
    assign state = {a, b, c, d, e, f, g, h};
    always_comb begin
        s1_e   = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        ch     = (e & f) ^ (~e & g);
        s0_a   = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        maj    = (a & b) ^ (a & c) ^ (b & c);
        t1     = h + s1_e + ch + k_ronde(t) + w[0];
        t2     = s0_a + maj;
        w_baru = (rotr(w[14], 17) ^ rotr(w[14], 19) ^ (w[14] >> 10)) + w[9]
               + (rotr(w[1], 7) ^ rotr(w[1], 18) ^ (w[1] >> 3)) + w[0];
    end

    assign busy = jalan | tambah;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            jalan  <= 1'b0;
            tambah <= 1'b0;
            done   <= 1'b0;
            t      <= '0;
            h_out  <= '0;
            h_awal <= '0;
            {a, b, c, d, e, f, g, h} <= '0;
            for (int i = 0; i < 16; i++) w[i] <= '0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                h_awal <= use_iv ? IV : h_in;
                {a, b, c, d, e, f, g, h} <= use_iv ? IV : h_in;
                for (int i = 0; i < 16; i++) w[i] <= block[511 - 32 * i -: 32];
                t     <= '0;
                jalan <= 1'b1;
            end else if (jalan) begin
                {a, b, c, d, e, f, g, h} <= {t1 + t2, a, b, c, d + t1, e, f, g};
                for (int i = 0; i < 15; i++) w[i] <= w[i + 1];
                w[15] <= w_baru;
                t <= t + 6'd1;
                if (t == 6'd63) begin
                    jalan  <= 1'b0;
                    tambah <= 1'b1;
                end
            end else if (tambah) begin
                for (int i = 0; i < 8; i++)
                    h_out[255 - 32 * i -: 32] <= h_awal[255 - 32 * i -: 32] + state[255 - 32 * i -: 32];
                tambah <= 1'b0;
                done   <= 1'b1;
            end
        end
    end
endmodule
