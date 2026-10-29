// Pengali berurutan digit-serial: p = a * b mod 2^PW, memproses DW bit pengali a per siklus (LSB dulu).
// a : AW bit tak bertanda (yang dipecah per digit)
// b : PW bit pola bit; untuk operan bertanda, pemanggil memperluas tanda sampai PW bit (hasil modulo 2^PW sama
//     dengan hasil bertanda bila nilai sebenarnya muat di PW bit)
// Latensi: start (siklus 0) -> done pada siklus NI + 1, NI = ceil(AW / DW); p valid saat done sampai start berikutnya.
// Menggantikan pengali larik lebar (AW x PW bit), yang di ASIC menjadi ribuan full-adder kombinasional dalam satu siklus.
// Hanya dipakai di ASIC (hw/asic); RTL FPGA di hw/rtl tidak berubah.
module serial_mul #(
    parameter int AW = 41,
    parameter int PW = 82,
    parameter int DW = 8
) (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          start,
    input  logic [AW-1:0] a,
    input  logic [PW-1:0] b,
    output logic          busy,
    output logic          done,
    output logic [PW-1:0] p
);
    localparam int NI = (AW + DW - 1) / DW;
    localparam int CW = $clog2(NI + 1);

    logic [NI*DW-1:0] a_sr;
    logic [PW-1:0]    b_sh;
    logic [CW-1:0]    n;

    // kontrol (dengan reset)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0;
            done <= 1'b0;
            n    <= '0;
        end else begin
            done <= 1'b0;
            if (start && !busy) begin
                busy <= 1'b1;
                n    <= CW'(NI);
            end else if (busy) begin
                n <= n - 1'b1;
                if (n == CW'(1)) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
            end
        end
    end

    // datapath (tanpa reset: dimuat pada start, hasil hanya dibaca setelah done)
    always_ff @(posedge clk) begin
        if (start && !busy) begin
            a_sr <= (NI*DW)'(a);
            b_sh <= b;
            p    <= '0;
        end else if (busy) begin
            p    <= p + PW'(a_sr[DW-1:0]) * b_sh;
            a_sr <= a_sr >> DW;
            b_sh <= b_sh << DW;
        end
    end
endmodule
