// Model simulasi makro sky130_sram_1kbyte_1rw1r_32x256_8 (OpenRAM, 32 bit x 256, port 0 RW + port 1 R).
// HANYA untuk simulasi: perilaku dan pin sama dengan model PDK
// (libs.ref/sky130_sram_macros/verilog/sky130_sram_1kbyte_1rw1r_32x256_8.v), tetapi tanpa $display
// per akses dan tanpa penundaan #(DELAY)/#(T_HOLD), supaya log tes bersih dan tidak ada nilai X.
// Di layout, modul ini TIDAK dipakai: LibreLane memakai makro asli (LEF/GDS/lib dari PDK).
//
// Perilaku (sama dengan model PDK): semua masukan dicuplik pada tepi naik clock; tulis port 0 terjadi pada
// tepi turun berikutnya; keluaran baca (dout0/dout1) berubah pada tepi turun berikutnya. Jadi keluaran baca
// sudah stabil sebelum tepi naik berikutnya, dan alamat yang dikirim sebelum tepi naik N terbaca oleh
// logika pengguna pada tepi naik N+1 (setara register baca BRAM).
module sky130_sram_1kbyte_1rw1r_32x256_8 (
    // port 0: RW
    input  wire        clk0,
    input  wire        csb0,        // aktif rendah
    input  wire        web0,        // aktif rendah: 0 = tulis
    input  wire [3:0]  wmask0,
    input  wire [7:0]  addr0,
    input  wire [31:0] din0,
    output reg  [31:0] dout0,
    // port 1: R
    input  wire        clk1,
    input  wire        csb1,        // aktif rendah
    input  wire [7:0]  addr1,
    output reg  [31:0] dout1
);
    reg [31:0] mem [0:255];

    reg        csb0_reg, web0_reg;
    reg [3:0]  wmask0_reg;
    reg [7:0]  addr0_reg;
    reg [31:0] din0_reg;
    reg        csb1_reg;
    reg [7:0]  addr1_reg;

    initial begin
        dout0 = 32'd0;
        dout1 = 32'd0;
    end

    always @(posedge clk0) begin
        csb0_reg   <= csb0;
        web0_reg   <= web0;
        wmask0_reg <= wmask0;
        addr0_reg  <= addr0;
        din0_reg   <= din0;
    end

    always @(posedge clk1) begin
        csb1_reg  <= csb1;
        addr1_reg <= addr1;
    end

    always @(negedge clk0) begin
        if (!csb0_reg && !web0_reg) begin
            if (wmask0_reg[0]) mem[addr0_reg][7:0]   <= din0_reg[7:0];
            if (wmask0_reg[1]) mem[addr0_reg][15:8]  <= din0_reg[15:8];
            if (wmask0_reg[2]) mem[addr0_reg][23:16] <= din0_reg[23:16];
            if (wmask0_reg[3]) mem[addr0_reg][31:24] <= din0_reg[31:24];
        end
        if (!csb0_reg && web0_reg) dout0 <= mem[addr0_reg];
    end

    always @(negedge clk1) begin
        if (!csb1_reg) dout1 <= mem[addr1_reg];
    end
endmodule
