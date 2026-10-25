// Inferensi tree ensemble (XGBoost multikelas) atas fitur bilangan bulat.
// Model dimuat dari berkas hw/model/<nama>/{simpul,pohon,base}.mem (hw/scripts/export_trees.py) atau
// ditulis ulang host lewat port simpul_*/pohon_*/base_* (ganti model tanpa sintesis ulang).
// Format simpul 72 bit: cabang [71]=0 | [70:64] fitur | [63:16] ambang s48 | [15:0] anak kiri (kanan = kiri+1);
//                       daun   [71]=1 | [31:0] nilai s32 Q8.16.
// Per simpul 2 siklus (baca BRAM sinkron + bandingkan); skor kelas = base + jumlah daun; kelas = argmax
// (seri -> indeks terkecil, sama dengan hw/golden/trees.py).
module tree_engine #(
    parameter int    N_FITUR  = 82,
    parameter int    N_KELAS  = 7,
    parameter int    N_POHON  = 420,
    parameter int    N_SIMPUL = 8704,
    parameter int    FW       = 48,
    parameter int    SW       = 32,
    parameter        BERKAS_SIMPUL = "",
    parameter        BERKAS_POHON  = "",
    parameter        BERKAS_BASE   = ""
) (
    input  logic                         clk,
    input  logic                         rst_n,
    // fitur
    input  logic                         fitur_we,
    input  logic [6:0]                   fitur_addr,
    input  logic signed [FW-1:0]         fitur_data,
    // pemuatan model oleh host
    input  logic                         simpul_we,
    input  logic [$clog2(N_SIMPUL)-1:0]  simpul_addr,
    input  logic [71:0]                  simpul_data,
    input  logic                         pohon_we,
    input  logic [$clog2(N_POHON)-1:0]   pohon_addr,
    input  logic [18:0]                  pohon_data,
    input  logic                         base_we,
    input  logic [2:0]                   base_addr,
    input  logic signed [SW-1:0]         base_data,
    // jalankan
    input  logic                         start,
    output logic                         busy,
    output logic                         done,
    output logic [N_KELAS*SW-1:0]        skor,     // kelas k di [k*SW +: SW]
    output logic [2:0]                   kelas
);
    localparam int PW = $clog2(N_POHON);
    localparam int AW = $clog2(N_SIMPUL);      // field alamat di memori 16 bit; bit atas tidak dipakai

    (* ram_style = "block" *) logic [71:0] mem_simpul [N_SIMPUL];
    logic [18:0]          mem_pohon  [N_POHON];
    logic signed [SW-1:0] mem_base   [N_KELAS];
    logic signed [FW-1:0] fitur      [N_FITUR];

    initial begin
        if (BERKAS_SIMPUL != "") $readmemh(BERKAS_SIMPUL, mem_simpul);
        if (BERKAS_POHON  != "") $readmemh(BERKAS_POHON, mem_pohon);
        if (BERKAS_BASE   != "") $readmemh(BERKAS_BASE, mem_base);
    end

    // memori simpul: BRAM, tulis + baca sinkron
    logic [AW-1:0] alamat;
    logic [71:0]   simpul_q;
    always_ff @(posedge clk) begin
        if (simpul_we) mem_simpul[simpul_addr] <= simpul_data;
        simpul_q <= mem_simpul[alamat];
    end
    always_ff @(posedge clk) begin
        if (pohon_we) mem_pohon[pohon_addr] <= pohon_data;
        if (base_we) mem_base[base_addr] <= base_data;
        if (fitur_we) fitur[fitur_addr] <= fitur_data;
    end

    typedef enum logic [1:0] {DIAM, BACA, NILAI} tahap_t;
    tahap_t tahap;
    logic [PW-1:0]        p;
    logic [2:0]           kelas_p;
    logic signed [SW-1:0] acc [N_KELAS];

    wire                  daun      = simpul_q[71];
    wire [6:0]            fi        = simpul_q[70:64];
    wire signed [FW-1:0]  ambang    = simpul_q[63:16];
    wire [AW-1:0]         kiri      = simpul_q[AW-1:0];
    /* verilator lint_off UNUSEDSIGNAL */
    wire [15-AW:0]        _sisa     = {simpul_q[15:AW] ^ mem_pohon[p][15:AW]};
    /* verilator lint_on UNUSEDSIGNAL */
    wire signed [SW-1:0]  nilai     = simpul_q[SW-1:0];
    wire                  ke_kiri   = fitur[fi] < ambang;
    wire                  terakhir  = (p == PW'(N_POHON - 1));

    assign busy = (tahap != DIAM);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tahap   <= DIAM;
            p       <= '0;
            kelas_p <= '0;
            alamat  <= '0;
            done    <= 1'b0;
            for (int k = 0; k < N_KELAS; k++) acc[k] <= '0;
        end else begin
            done <= 1'b0;
            case (tahap)
                DIAM: if (start) begin
                    for (int k = 0; k < N_KELAS; k++) acc[k] <= mem_base[k];
                    p       <= '0;
                    kelas_p <= mem_pohon[0][18:16];
                    alamat  <= mem_pohon[0][AW-1:0];
                    tahap   <= BACA;
                end
                BACA: tahap <= NILAI;                       // tunggu data BRAM
                NILAI: begin
                    if (daun) begin
                        acc[kelas_p] <= acc[kelas_p] + nilai;
                        if (terakhir) begin
                            tahap <= DIAM;
                            done  <= 1'b1;
                        end else begin
                            p       <= p + 1'b1;
                            kelas_p <= mem_pohon[p + 1'b1][18:16];
                            alamat  <= mem_pohon[p + 1'b1][AW-1:0];
                            tahap   <= BACA;
                        end
                    end else begin
                        alamat <= ke_kiri ? kiri : kiri + 1'b1;
                        tahap  <= BACA;
                    end
                end
                default: tahap <= DIAM;
            endcase
        end
    end

    // skor dan argmax (seri -> indeks terkecil)
    always_comb begin
        logic signed [SW-1:0] terbaik;
        terbaik = acc[0];
        kelas   = 3'd0;
        for (int k = 0; k < N_KELAS; k++) begin
            skor[k*SW +: SW] = acc[k];
            if (acc[k] > terbaik) begin
                terbaik = acc[k];
                kelas   = 3'(k);
            end
        end
    end
endmodule
