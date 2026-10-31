// Sinkroniser reset: aktif (turun) seketika secara asinkron, dilepas sinkron dengan clk setelah 2 tepi naik.
// Mencegah pelepasan reset yang tidak sinkron dengan clk (metastabil di silikon) pada reset asinkron di seluruh chip.
module rst_sync (
    input  logic clk,
    input  logic rst_n_in,
    output logic rst_n_out
);
    logic [1:0] ff;
    always_ff @(posedge clk or negedge rst_n_in) begin
        if (!rst_n_in) ff <= 2'b00;
        else           ff <= {ff[0], 1'b1};
    end
    assign rst_n_out = ff[1];
endmodule
