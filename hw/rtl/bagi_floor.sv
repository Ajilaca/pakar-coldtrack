// Pembagian floor bertanda: q = floor(n / d), d > 0. Restoring iteratif: NW siklus + 1 siklus koreksi.
module bagi_floor #(
    parameter int NW = 72,      // lebar pembilang (bertanda)
    parameter int DW = 34       // lebar penyebut (positif)
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 start,
    input  logic signed [NW-1:0] n,
    input  logic [DW-1:0]        d,
    output logic                 busy,
    output logic                 done,
    output logic signed [NW-1:0] q
);
    localparam int CW = $clog2(NW + 1);

    logic [NW-1:0] a, hasil;
    logic [DW:0]   r;
    logic [DW-1:0] pembagi;
    logic          negatif, akhir;
    logic [CW-1:0] sisa_iter;

    logic [DW:0] r_geser;
    logic        cukup;
    assign r_geser = {r[DW-1:0], a[NW-1]};
    assign cukup   = r_geser >= {1'b0, pembagi};

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0; done <= 1'b0; q <= '0; akhir <= 1'b0;
            a <= '0; hasil <= '0; r <= '0; pembagi <= '0; negatif <= 1'b0; sisa_iter <= '0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                negatif   <= n[NW-1];
                a         <= n[NW-1] ? -n : n;
                pembagi   <= d;
                r         <= '0;
                hasil     <= '0;
                sisa_iter <= CW'(NW);
                busy      <= 1'b1;
            end else if (busy && !akhir) begin
                r     <= cukup ? r_geser - {1'b0, pembagi} : r_geser;
                hasil <= {hasil[NW-2:0], cukup};
                a     <= {a[NW-2:0], 1'b0};
                sisa_iter <= sisa_iter - 1'b1;
                if (sisa_iter == CW'(1)) akhir <= 1'b1;
            end else if (akhir) begin
                q     <= negatif ? -$signed(hasil) - NW'(r != '0) : $signed(hasil);
                akhir <= 1'b0;
                busy  <= 1'b0;
                done  <= 1'b1;
            end
        end
    end
endmodule
