// SPI slave -> master AXI4-Lite: akses register coldtrack_top dari mikrokontroler lewat 4 pin (chip ASIC).
// SPI mode 0, MSB dulu, satu transaksi per frame CS rendah:
//   tulis: MOSI {1, 3'b0, alamat[11:0]} + data[31:0]                     48 bit
//   baca : MOSI {0, 3'b0, alamat[11:0]} + 8 bit dummy, MISO data[31:0]  56 bit
// Format frame di hw/golden/spi_frame.py. SCK, CS, MOSI dicuplik clk lewat sinkroniser 2 FF, jadi SCK <= clk/8.
// MISO diganti sesudah tepi naik SCK terdeteksi (master sudah mencuplik bit itu), sehingga bit berikutnya stabil
// hampir satu periode SCK penuh sebelum tepi naik berikutnya.
module spi_axil_bridge (
    input  logic        clk,
    input  logic        rst_n,
    // SPI slave
    input  logic        spi_sck,
    input  logic        spi_cs_n,
    input  logic        spi_mosi,
    output logic        spi_miso,
    output logic        spi_miso_oe,   // 1 saat CS rendah (MISO boleh dibagi dengan slave lain)
    // AXI4-Lite master
    output logic [11:0] m_axil_awaddr,
    output logic        m_axil_awvalid,
    input  logic        m_axil_awready,
    output logic [31:0] m_axil_wdata,
    output logic [3:0]  m_axil_wstrb,
    output logic        m_axil_wvalid,
    input  logic        m_axil_wready,
    /* verilator lint_off UNUSEDSIGNAL */
    input  logic [1:0]  m_axil_bresp,  // slave selalu OKAY
    /* verilator lint_on UNUSEDSIGNAL */
    input  logic        m_axil_bvalid,
    output logic        m_axil_bready,
    output logic [11:0] m_axil_araddr,
    output logic        m_axil_arvalid,
    input  logic        m_axil_arready,
    input  logic [31:0] m_axil_rdata,
    /* verilator lint_off UNUSEDSIGNAL */
    input  logic [1:0]  m_axil_rresp,
    /* verilator lint_on UNUSEDSIGNAL */
    input  logic        m_axil_rvalid,
    output logic        m_axil_rready
);
    // sinkroniser
    logic [2:0] sck_s;
    logic [1:0] cs_s, mosi_s;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sck_s <= '0; cs_s <= 2'b11; mosi_s <= '0;
        end else begin
            sck_s  <= {sck_s[1:0], spi_sck};
            cs_s   <= {cs_s[0], spi_cs_n};
            mosi_s <= {mosi_s[0], spi_mosi};
        end
    end
    wire cs_aktif = !cs_s[1];
    wire naik     = cs_aktif && sck_s[1] && !sck_s[2];

    typedef enum logic [1:0] {DIAM, TULIS, TUNGGU_B, BACA} tahap_t;
    tahap_t tahap;

    logic [5:0]  n;           // tepi naik SCK sejak CS turun
    logic [15:0] header;
    logic [30:0] data_in;         // bit data ke-32 diambil langsung dari MOSI
    logic [31:0] data_out;
    wire         tulis = header[15];
    wire         header_tulis = header[14];          // bit 15 header saat tepi naik ke-16 (n = 15) belum digeser

    assign spi_miso    = data_out[31];
    assign spi_miso_oe = cs_aktif;

    assign m_axil_wstrb  = 4'hF;
    assign m_axil_bready = 1'b1;
    assign m_axil_rready = 1'b1;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            n <= '0; header <= '0; data_in <= '0; data_out <= '0; tahap <= DIAM;
            m_axil_awaddr <= '0; m_axil_awvalid <= 1'b0; m_axil_wdata <= '0; m_axil_wvalid <= 1'b0;
            m_axil_araddr <= '0; m_axil_arvalid <= 1'b0;
        end else begin
            if (!cs_aktif)
                n <= '0;                                       // frame batal atau selesai: mulai dari awal
            else if (naik) begin
                n <= (n == 6'd63) ? n : n + 6'd1;
                if (n < 6'd16) header <= {header[14:0], mosi_s[1]};
                else           data_in <= {data_in[29:0], mosi_s[1]};
                if (n >= 6'd24) data_out <= {data_out[30:0], 1'b0};
            end

            case (tahap)
                DIAM:
                    if (naik && n == 6'd15 && !header_tulis) begin        // header baca lengkap
                        m_axil_araddr  <= {header[10:0], mosi_s[1]};
                        m_axil_arvalid <= 1'b1;
                        tahap          <= BACA;
                    end else if (naik && n == 6'd47 && tulis) begin            // data tulis lengkap
                        m_axil_awaddr  <= header[11:0];
                        m_axil_wdata   <= {data_in[30:0], mosi_s[1]};
                        m_axil_awvalid <= 1'b1;
                        m_axil_wvalid  <= 1'b1;
                        tahap          <= TULIS;
                    end
                TULIS: begin
                    if (m_axil_awready) m_axil_awvalid <= 1'b0;
                    if (m_axil_wready)  m_axil_wvalid  <= 1'b0;
                    if ((m_axil_awready || !m_axil_awvalid) && (m_axil_wready || !m_axil_wvalid)) tahap <= TUNGGU_B;
                end
                TUNGGU_B: if (m_axil_bvalid) tahap <= DIAM;
                BACA: begin                                    // slave boleh memberi rvalid bersamaan arready
                    if (m_axil_arready) m_axil_arvalid <= 1'b0;
                    if (m_axil_rvalid) begin
                        m_axil_arvalid <= 1'b0;
                        data_out       <= m_axil_rdata;        // jauh sebelum tepi naik ke-25 (bit data pertama)
                        tahap          <= DIAM;
                    end
                end
                default: tahap <= DIAM;
            endcase
        end
    end
endmodule
