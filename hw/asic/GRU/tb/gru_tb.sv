// Testbench gru_engine: clock internal (Verilator --timing), model flash sebagai aliran byte dengan jeda acak
// (+STALL=<persen>), memori masukan baca sinkron. Berkas dari plusarg +IMG=<hex byte> +XIN=<hex 32 bit>.
// Tes cocotb (test_gru.py) hanya menunggu done lalu membaca keluaran lewat out_idx.
`timescale 1ns / 1ps
module gru_tb;
    logic clk = 1'b0, rst_n = 1'b0, start = 1'b0;
    always #5 clk = ~clk;

    logic        busy, done, err, ws_start, ws_ready, ws_valid;
    logic [23:0] ws_addr;
    logic [7:0]  ws_data;
    logic [11:0] xin_addr;
    logic signed [31:0] xin_data, out_data;
    logic [3:0]  out_idx = '0;
    logic [63:0] cyc = '0, cyc_mulai = '0, cyc_selesai = '0;

    gru_engine u_eng (.*);

    localparam int ROM_N = 1 << 20;
    logic [7:0]         rom [ROM_N];
    logic signed [31:0] xmem [4096];
    int stall = 0;
    string img, xin;

    initial begin
        if (!$value$plusargs("IMG=%s", img)) $fatal(1, "butuh +IMG=");
        if (!$value$plusargs("XIN=%s", xin)) $fatal(1, "butuh +XIN=");
        void'($value$plusargs("STALL=%d", stall));
        $readmemh(img, rom);
        $readmemh(xin, xmem);
        repeat (4) @(posedge clk);
        rst_n <= 1'b1;
        repeat (3) @(posedge clk);
        start <= 1'b1;
        @(posedge clk);
        start <= 1'b0;
    end

    always_ff @(posedge clk) begin
        cyc <= cyc + 64'd1;
        if (start) cyc_mulai <= cyc;
        if (done && cyc_selesai == 64'd0) cyc_selesai <= cyc;
    end

    // model flash: ptr = alamat byte yang sedang ditawarkan di ws_data
    logic [23:0] ptr;
    function automatic logic jeda();
        return (stall > 0) && (($urandom % 100) < stall);
    endfunction
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ws_valid <= 1'b0; ptr <= '0; ws_data <= '0;
        end else if (ws_start) begin
            ptr <= ws_addr; ws_data <= rom[ws_addr[19:0]]; ws_valid <= !jeda();
        end else if (!ws_valid) begin
            ws_valid <= !jeda();
        end else if (ws_ready) begin
            ptr <= ptr + 24'd1; ws_data <= rom[20'(ptr + 24'd1)]; ws_valid <= !jeda();
        end
    end

    always_ff @(posedge clk) xin_data <= xmem[xin_addr];
endmodule
