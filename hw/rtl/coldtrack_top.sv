// Chip ColdTrack: segel + mesin fisika + fitur + tree ensemble di belakang slave AXI4-Lite (ARM KV260).
// Peta register (alamat byte, data 32 bit) di hw/golden/regmap.py; urutan per menit:
//   host tulis S_* lalu CTRL.sampel_go -> segel rekaman, fisika, fitur paralel -> tree_engine (bila siap)
//   -> STATUS.hasil_valid. CTRL.mac_go -> HMAC atas {rantai, paket hasil} -> STATUS.mac_valid.
module coldtrack_top #(
    parameter        BERKAS_SIMPUL = "",
    parameter        BERKAS_POHON  = "",
    parameter        BERKAS_BASE   = ""
) (
    input  logic        clk,
    input  logic        rst_n,
    // AXI4-Lite slave
    input  logic [11:0] s_axil_awaddr,
    input  logic        s_axil_awvalid,
    output logic        s_axil_awready,
    input  logic [31:0] s_axil_wdata,
    /* verilator lint_off UNUSEDSIGNAL */
    input  logic [3:0]  s_axil_wstrb,       // semua register ditulis utuh 32 bit
    /* verilator lint_on UNUSEDSIGNAL */
    input  logic        s_axil_wvalid,
    output logic        s_axil_wready,
    output logic [1:0]  s_axil_bresp,
    output logic        s_axil_bvalid,
    input  logic        s_axil_bready,
    input  logic [11:0] s_axil_araddr,
    input  logic        s_axil_arvalid,
    output logic        s_axil_arready,
    output logic [31:0] s_axil_rdata,
    output logic [1:0]  s_axil_rresp,
    output logic        s_axil_rvalid,
    input  logic        s_axil_rready,
    // alarm sopir (LED / buzzer)
    output logic        alarm_waspada,
    output logic        alarm_kritis,
    output logic        alarm_sensor
);
    localparam logic [31:0] ID = 32'h43540001;      // "CT" v1

    // ---------------- register host ----------------
    logic signed [15:0] cfg_t_lo, cfg_t_hi, cfg_t_set, cfg_batas;
    logic [40:0]        cfg_k, cfg_ek;
    logic [31:0]        s_seq, s_ts;
    logic signed [15:0] s_temp, s_amb;
    logic [15:0]        s_rh, s_solar, s_speed, s_duty;
    logic [3:0]         s_flags;                     // [0] pintu [1] reefer [2] kopling [3] temp_ok
    logic [7:0]         s_harsh, s_batt;
    logic [4:0]         s_hour;
    logic [255:0]       kunci_stage;
    logic [13:0]        m_simpul_addr;
    logic [71:0]        m_simpul_data;
    logic [8:0]         m_pohon_addr;
    logic [18:0]        m_pohon_data;
    logic [2:0]         m_base_addr;
    logic [31:0]        m_base_data;

    logic c_trip_reset, c_sampel, c_mac, c_kunci_kunci, c_kunci_tulis, c_simpul_we, c_pohon_we, c_base_we;

    // ---------------- blok ----------------
    logic         sg_busy, sg_done, sg_terkunci;
    logic [255:0] sg_rantai, sg_mac;
    logic [183:0] rekaman;
    logic [127:0] paket_hasil;
    logic         sg_segel_start, sg_mac_start;

    /* verilator lint_off UNUSEDSIGNAL */
    logic         fs_busy, ft_busy, tr_busy;   // sequencer memakai pulsa done
    /* verilator lint_on UNUSEDSIGNAL */
    logic         fs_done, fs_ttb_valid, fs_seri;
    logic [1:0]   fs_status, fs_sensor;
    logic [2:0]   fs_alasan;
    logic [5:0]   fs_ttb;
    logic signed [39:0] fs_tc, fs_ts10;

    logic         ft_done, ft_siap, ft_lengkap, ft_we;
    logic [15:0]  ft_menit;
    logic [6:0]   ft_addr;
    logic signed [47:0] ft_data;

    logic         tr_start, tr_done;
    logic [7*32-1:0] tr_skor;
    logic [2:0]   tr_kelas;

    assign rekaman = {s_seq, s_ts, s_temp, s_rh, s_amb, s_solar, s_speed, 4'd0, s_flags, s_duty, s_harsh, s_batt};

    segel u_segel (
        .clk(clk), .rst_n(rst_n),
        .kunci_tulis(c_kunci_tulis), .kunci_data(kunci_stage), .kunci_kunci(c_kunci_kunci), .kunci_terkunci(sg_terkunci),
        .rantai_reset(c_trip_reset && !sg_busy), .segel_start(sg_segel_start), .rekaman(rekaman), .rantai(sg_rantai),
        .mac_start(sg_mac_start), .hasil(paket_hasil), .mac(sg_mac), .busy(sg_busy), .done(sg_done)
    );

    fisika u_fisika (
        .clk(clk), .rst_n(rst_n),
        .cfg_t_lo(cfg_t_lo), .cfg_t_hi(cfg_t_hi), .cfg_t_set(cfg_t_set), .cfg_batas_waspada(cfg_batas),
        .cfg_k(cfg_k), .cfg_ek(cfg_ek),
        .trip_reset(c_trip_reset), .sampel(c_sampel && !busy),
        .ts_raw(s_flags[3] ? s_temp : 16'sh8000),          // bacaan gagal -> nilai mustahil -> sensor rusak
        .t_amb(s_amb), .pintu(s_flags[0]), .bergerak(s_speed >= 16'd100),
        .busy(fs_busy), .done(fs_done), .status(fs_status), .alasan(fs_alasan), .ttb_valid(fs_ttb_valid),
        .ttb(fs_ttb), .sensor(fs_sensor), .tc(fs_tc), .ts10(fs_ts10), .seri(fs_seri)
    );

    fitur #(.FW(48), .N_FITUR(82)) u_fitur (
        .clk(clk), .rst_n(rst_n), .trip_reset(c_trip_reset), .sampel(c_sampel && !busy), .temp_ok(s_flags[3]),
        .temp(s_temp), .amb(s_amb), .solar(s_solar), .rh(s_rh), .speed(s_speed), .duty(s_duty),
        .door(s_flags[0]), .reefer(s_flags[1]), .harsh(s_harsh), .hour(s_hour),
        .busy(ft_busy), .done(ft_done), .menit(ft_menit), .siap(ft_siap), .lengkap(ft_lengkap),
        .fitur_we(ft_we), .fitur_addr(ft_addr), .fitur_data(ft_data)
    );

    tree_engine #(.N_FITUR(82), .BERKAS_SIMPUL(BERKAS_SIMPUL), .BERKAS_POHON(BERKAS_POHON), .BERKAS_BASE(BERKAS_BASE)) u_tree (
        .clk(clk), .rst_n(rst_n),
        .fitur_we(ft_we), .fitur_addr(ft_addr), .fitur_data(ft_data),
        .simpul_we(c_simpul_we), .simpul_addr(m_simpul_addr), .simpul_data(m_simpul_data),
        .pohon_we(c_pohon_we), .pohon_addr(m_pohon_addr), .pohon_data(m_pohon_data),
        .base_we(c_base_we), .base_addr(m_base_addr), .base_data(m_base_data),
        .start(tr_start), .busy(tr_busy), .done(tr_done), .skor(tr_skor), .kelas(tr_kelas)
    );

    // ---------------- sequencer per menit ----------------
    logic busy, tunggu_segel, tunggu_fisika, tunggu_fitur, tunggu_tree, mode_mac, jalan;
    logic hasil_valid, mac_valid, diag_valid;
    logic [1:0]  r_status, r_sensor;
    logic [2:0]  r_alasan, r_kelas;
    logic        r_ttb_valid, r_seri;
    logic [5:0]  r_ttb;
    logic signed [39:0] r_tc, r_ts10;
    logic [15:0] r_menit;
    logic [7*32-1:0] r_skor;
    logic [31:0] r_seq;

    assign busy = tunggu_segel | tunggu_fisika | tunggu_fitur | tunggu_tree | sg_busy;

    wire [7:0] b_fisika = {r_ttb_valid, r_sensor, r_alasan, r_status};
    /* verilator lint_off UNUSEDSIGNAL */
    wire [31:0] skor_pilih = r_skor[r_kelas*32 +: 32];   // paket memuat bit [23:8]
    /* verilator lint_on UNUSEDSIGNAL */
    assign paket_hasil = {r_seq, r_menit, b_fisika, {2'b0, r_ttb}, {4'b0, diag_valid, r_kelas}, 8'h00,
                          r_tc[39:8], skor_pilih[23:8]};

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tunggu_segel <= 1'b0; tunggu_fisika <= 1'b0; tunggu_fitur <= 1'b0; tunggu_tree <= 1'b0; mode_mac <= 1'b0; jalan <= 1'b0;
            hasil_valid <= 1'b0; mac_valid <= 1'b0; diag_valid <= 1'b0;
            sg_segel_start <= 1'b0; sg_mac_start <= 1'b0; tr_start <= 1'b0;
            r_status <= '0; r_sensor <= '0; r_alasan <= '0; r_kelas <= '0; r_ttb_valid <= 1'b0; r_seri <= 1'b0;
            r_ttb <= '0; r_tc <= '0; r_ts10 <= '0; r_menit <= '0; r_skor <= '0; r_seq <= '0;
        end else begin
            sg_segel_start <= 1'b0;
            sg_mac_start   <= 1'b0;
            tr_start       <= 1'b0;

            if (c_sampel && !busy) begin
                sg_segel_start <= 1'b1;
                tunggu_segel   <= 1'b1;
                tunggu_fisika  <= 1'b1;
                tunggu_fitur   <= 1'b1;
                mode_mac       <= 1'b0;
                jalan          <= 1'b1;
                hasil_valid    <= 1'b0;
                mac_valid      <= 1'b0;
                diag_valid     <= 1'b0;
                r_kelas        <= '0;
                r_skor         <= '0;
                r_seq          <= s_seq;
            end else if (c_mac && !busy && hasil_valid) begin
                sg_mac_start <= 1'b1;
                tunggu_segel <= 1'b1;
                mode_mac     <= 1'b1;
                mac_valid    <= 1'b0;
            end

            if (sg_done) begin
                tunggu_segel <= 1'b0;
                if (mode_mac) mac_valid <= 1'b1;
            end
            if (fs_done) begin
                tunggu_fisika <= 1'b0;
                r_status <= fs_status; r_sensor <= fs_sensor; r_alasan <= fs_alasan;
                r_ttb_valid <= fs_ttb_valid; r_ttb <= fs_ttb; r_seri <= fs_seri; r_tc <= fs_tc; r_ts10 <= fs_ts10;
            end
            if (ft_done) begin
                tunggu_fitur <= 1'b0;
                r_menit      <= ft_menit;
                if (ft_siap) begin
                    tr_start    <= 1'b1;
                    tunggu_tree <= 1'b1;
                end
            end
            if (tr_done) begin
                tunggu_tree <= 1'b0;
                r_kelas     <= tr_kelas;
                r_skor      <= tr_skor;
                diag_valid  <= ft_lengkap;
            end
            // semua blok selesai -> hasil menit ini sah
            if (jalan && !(tunggu_segel | tunggu_fisika | tunggu_fitur | tunggu_tree)) begin
                jalan       <= 1'b0;
                hasil_valid <= 1'b1;
            end
        end
    end

    assign alarm_waspada = hasil_valid && (r_status == 2'd1);
    assign alarm_kritis  = hasil_valid && (r_status == 2'd2);
    assign alarm_sensor  = hasil_valid && (r_sensor != 2'd0);

    // ---------------- AXI4-Lite ----------------
    logic [11:0] aw_addr;
    logic        aw_ada, w_ada;
    logic [31:0] w_data;

    assign s_axil_awready = !aw_ada && !s_axil_bvalid;
    assign s_axil_wready  = !w_ada && !s_axil_bvalid;
    assign s_axil_bresp   = 2'b00;
    assign s_axil_rresp   = 2'b00;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            aw_ada <= 1'b0; w_ada <= 1'b0; aw_addr <= '0; w_data <= '0; s_axil_bvalid <= 1'b0;
            {c_trip_reset, c_sampel, c_mac, c_kunci_kunci, c_kunci_tulis, c_simpul_we, c_pohon_we, c_base_we} <= '0;
            cfg_t_lo <= '0; cfg_t_hi <= '0; cfg_t_set <= '0; cfg_batas <= '0; cfg_k <= '0; cfg_ek <= '0;
            s_seq <= '0; s_ts <= '0; s_temp <= '0; s_amb <= '0; s_rh <= '0; s_solar <= '0; s_speed <= '0;
            s_duty <= '0; s_flags <= '0; s_harsh <= '0; s_batt <= '0; s_hour <= '0; kunci_stage <= '0;
            m_simpul_addr <= '0; m_simpul_data <= '0; m_pohon_addr <= '0; m_pohon_data <= '0;
            m_base_addr <= '0; m_base_data <= '0;
        end else begin
            {c_trip_reset, c_sampel, c_mac, c_kunci_kunci, c_kunci_tulis, c_simpul_we, c_pohon_we, c_base_we} <= '0;
            if (s_axil_awvalid && s_axil_awready) begin aw_addr <= s_axil_awaddr; aw_ada <= 1'b1; end
            if (s_axil_wvalid && s_axil_wready) begin w_data <= s_axil_wdata; w_ada <= 1'b1; end
            if (s_axil_bvalid && s_axil_bready) s_axil_bvalid <= 1'b0;
            if (aw_ada && w_ada) begin
                aw_ada <= 1'b0; w_ada <= 1'b0; s_axil_bvalid <= 1'b1;
                case (aw_addr)
                    12'h004: {c_base_we, c_pohon_we, c_simpul_we, c_kunci_tulis, c_kunci_kunci, c_mac, c_sampel, c_trip_reset} <= w_data[7:0];
                    12'h010: cfg_t_lo  <= w_data[15:0];
                    12'h014: cfg_t_hi  <= w_data[15:0];
                    12'h018: cfg_t_set <= w_data[15:0];
                    12'h01C: cfg_batas <= w_data[15:0];
                    12'h020: cfg_k[31:0]   <= w_data;
                    12'h024: cfg_k[40:32]  <= w_data[8:0];
                    12'h028: cfg_ek[31:0]  <= w_data;
                    12'h02C: cfg_ek[40:32] <= w_data[8:0];
                    12'h040: s_seq   <= w_data;
                    12'h044: s_ts    <= w_data;
                    12'h048: s_temp  <= w_data[15:0];
                    12'h04C: s_rh    <= w_data[15:0];
                    12'h050: s_amb   <= w_data[15:0];
                    12'h054: s_solar <= w_data[15:0];
                    12'h058: s_speed <= w_data[15:0];
                    12'h05C: s_flags <= w_data[3:0];
                    12'h060: s_duty  <= w_data[15:0];
                    12'h064: s_harsh <= w_data[7:0];
                    12'h068: s_batt  <= w_data[7:0];
                    12'h06C: s_hour  <= w_data[4:0];
                    12'h180: m_simpul_addr <= w_data[13:0];
                    12'h184: m_simpul_data[31:0]  <= w_data;
                    12'h188: m_simpul_data[63:32] <= w_data;
                    12'h18C: m_simpul_data[71:64] <= w_data[7:0];
                    12'h190: m_pohon_addr <= w_data[8:0];
                    12'h194: m_pohon_data <= w_data[18:0];
                    12'h198: m_base_addr  <= w_data[2:0];
                    12'h19C: m_base_data  <= w_data;
                    default: if (aw_addr[11:5] == 7'h08)            // 0x100..0x11C kunci, kata 0 = bit atas
                                 kunci_stage[255 - 32 * aw_addr[4:2] -: 32] <= w_data;
                endcase
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            s_axil_arready <= 1'b0; s_axil_rvalid <= 1'b0; s_axil_rdata <= '0;
        end else begin
            s_axil_arready <= 1'b0;
            if (s_axil_rvalid && s_axil_rready) s_axil_rvalid <= 1'b0;
            if (s_axil_arvalid && !s_axil_arready && !s_axil_rvalid) begin
                s_axil_arready <= 1'b1;
                s_axil_rvalid  <= 1'b1;
                case (s_axil_araddr)
                    12'h000: s_axil_rdata <= ID;
                    12'h008: s_axil_rdata <= {25'd0, diag_valid, ft_lengkap, ft_siap, sg_terkunci, mac_valid, hasil_valid, busy};
                    12'h080: s_axil_rdata <= {15'd0, r_seri, 2'b0, r_ttb, b_fisika};
                    12'h084: s_axil_rdata <= r_tc[31:0];
                    12'h088: s_axil_rdata <= {{24{r_tc[39]}}, r_tc[39:32]};
                    12'h08C: s_axil_rdata <= {28'd0, diag_valid, r_kelas};
                    12'h090: s_axil_rdata <= {16'd0, r_menit};
                    12'h094: s_axil_rdata <= r_ts10[31:0];
                    12'h098: s_axil_rdata <= {{24{r_ts10[39]}}, r_ts10[39:32]};
                    default: begin
                        s_axil_rdata <= 32'hDEAD_BEEF;
                        if (s_axil_araddr >= 12'h0A0 && s_axil_araddr <= 12'h0B8)
                            s_axil_rdata <= r_skor[(s_axil_araddr - 12'h0A0) * 8 +: 32];
                        else if (s_axil_araddr[11:5] == 7'h06)          // 0x0C0..0x0DC rantai
                            s_axil_rdata <= sg_rantai[255 - 32 * s_axil_araddr[4:2] -: 32];
                        else if (s_axil_araddr[11:5] == 7'h07)          // 0x0E0..0x0FC mac
                            s_axil_rdata <= sg_mac[255 - 32 * s_axil_araddr[4:2] -: 32];
                    end
                endcase
            end
        end
    end
endmodule
