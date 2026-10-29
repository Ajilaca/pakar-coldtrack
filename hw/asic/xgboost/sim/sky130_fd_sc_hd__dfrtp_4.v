// Model simulasi sel sky130_fd_sc_hd__dfrtp_4 (flip-flop D, reset asinkron aktif rendah), pin sama dengan model PDK
// tanpa pin daya. Hanya untuk tes cocotb; sintesis/layout memakai sel dari PDK.
module sky130_fd_sc_hd__dfrtp_4 (
    input  CLK,
    input  D,
    input  RESET_B,
    output reg Q
);
    always @(posedge CLK or negedge RESET_B)
        if (!RESET_B) Q <= 1'b0;
        else          Q <= D;
endmodule
