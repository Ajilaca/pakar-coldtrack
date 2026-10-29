// Model perilaku makro DFFRAM RAM256 (AUCOHL/DFFRAM, sky130A, latch, 1RW, 256 x 32 bit) untuk simulasi saja.
// Meniru struktur makro asli (models/ram/model.v + block_definitions.v), bukan sekadar RAM ideal:
// - tulis: byte i ditulis bila EN0 && WE0[i]; nilai Di0/A0 selama siklus tersimpan pada tepi naik berikutnya;
// - baca: tiap blok 16 word (RAM16, dipilih A0[7:4]) punya register keluaran (OUTREG) yang mencuplik word terpilih
//   pada tepi naik; blok yang tidak dipilih mencuplik 0;
// - mux keluaran antar-blok (RAM32/RAM128/RAM256) memakai A0[7:4] SAAT INI, tidak diregister. Akibatnya data alamat
//   yang diberikan di siklus N hanya benar di siklus N+1 bila A0[7:4] tidak berubah di siklus N+1.
module RAM256 (
`ifdef USE_POWER_PINS
    inout VPWR,
    inout VGND,
`endif
    input  wire        CLK,
    input  wire [3:0]  WE0,
    input  wire        EN0,
    input  wire [7:0]  A0,
    input  wire [31:0] Di0,
    output wire [31:0] Do0
);
    reg [31:0] mem [0:255];
    reg [31:0] blok_q [0:15];
    integer b, i;

    always @(posedge CLK) begin
        for (b = 0; b < 16; b = b + 1)
            blok_q[b] <= (EN0 && A0[7:4] == b[3:0]) ? mem[A0] : 32'd0;
        if (EN0)
            for (i = 0; i < 4; i = i + 1)
                if (WE0[i]) mem[A0][8 * i +: 8] <= Di0[8 * i +: 8];
    end

    assign Do0 = blok_q[A0[7:4]];
endmodule
