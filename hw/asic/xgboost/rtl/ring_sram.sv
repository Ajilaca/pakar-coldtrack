// Ring buffer 256 x 111 bit dari 4 makro DFFRAM RAM256 (AUCOHL/DFFRAM, latch, 1RW, 32 bit x 256).
// Pembungkus ini menggantikan array `mem` di features.sv (versi FPGA, yang menjadi BRAM). Hanya dipakai di ASIC.
// DFFRAM dibangun dari sel standar, jadi timing tersedia di semua corner dan tidak ada aturan DRC khusus makro.
//
// Pemetaan: 111 bit data dipadatkan ke 128 bit (17 bit atas selalu 0), tiap makro menyimpan 32 bit:
//   makro 0 = bit [31:0], makro 1 = [63:32], makro 2 = [95:64], makro 3 = [127:96].
// Satu port: alamat = alamat tulis saat wr_en, selain itu alamat baca (features tidak pernah menulis dan membaca pada
// siklus yang sama; tulis hanya di tahap DIAM). Alamat dan kontrol datang sebagai empat salinan identik (indeks =
// nomor makro) dari register di features.sv, supaya tiap makro digerakkan register terdekatnya.
//
// Pewaktuan baca = register `rd_r` di features.sv versi FPGA: alamat diberikan sebelum tepi naik N, dan `rd_data`
// valid setelah tepi naik N sehingga logika pemakai mencuplik data itu pada tepi naik N+1. Syarat DFFRAM: mux
// keluaran antar-blok 16 word memakai alamat saat ini, jadi alamat harus tetap sampai tepi naik N+1. features.sv
// menahan alamat baca minimal dua siklus (jendela menunggu entri selesai, konteks memberi satu siklus jeda).
module ring_sram (
    input  logic            clk,
    input  logic [3:0]      wr_en,
    input  logic [3:0][7:0] wr_addr,
    input  logic [110:0]    wr_data,
    input  logic [3:0][7:0] rd_addr,
    output logic [110:0]    rd_data
);
    logic [127:0]    din, dout;
    logic [3:0][7:0] a;
    assign din     = {17'd0, wr_data};
    assign rd_data = dout[110:0];
    for (genvar k = 0; k < 4; k++) begin : g_a
        assign a[k] = wr_en[k] ? wr_addr[k] : rd_addr[k];
    end

    // empat instansi eksplisit (bukan generate) agar nama instansi di netlist sederhana untuk penempatan makro:
    // u_chip.u_ct.u_fitur.u_ring.u_ram0 .. u_ram3
    RAM256 u_ram0 (.CLK(clk), .WE0({4{wr_en[0]}}), .EN0(1'b1), .A0(a[0]), .Di0(din[31:0]),   .Do0(dout[31:0]));
    RAM256 u_ram1 (.CLK(clk), .WE0({4{wr_en[1]}}), .EN0(1'b1), .A0(a[1]), .Di0(din[63:32]),  .Do0(dout[63:32]));
    RAM256 u_ram2 (.CLK(clk), .WE0({4{wr_en[2]}}), .EN0(1'b1), .A0(a[2]), .Di0(din[95:64]),  .Do0(dout[95:64]));
    RAM256 u_ram3 (.CLK(clk), .WE0({4{wr_en[3]}}), .EN0(1'b1), .A0(a[3]), .Di0(din[127:96]), .Do0(dout[127:96]));

    // 17 bit atas dout tidak dipakai (data padding)
    /* verilator lint_off UNUSEDSIGNAL */
    wire _tak_dipakai = &{1'b0, dout[127:111]};
    /* verilator lint_on UNUSEDSIGNAL */
endmodule
