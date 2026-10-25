// Pembungkus Verilog-2001 coldtrack_top untuk block design Vivado (module reference tidak menerima top SV).
// Nama port s_axi_* dan atribut X_INTERFACE membuat Vivado mengenali slave AXI4-Lite, clock, dan reset,
// sehingga connection automation menyambungkannya ke M_AXI_HPM0_FPD Zynq UltraScale+ (KV260).
module coldtrack_axil #(
    parameter BERKAS_SIMPUL = "",
    parameter BERKAS_POHON  = "",
    parameter BERKAS_BASE   = ""
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET aresetn" *)
    input  wire        aclk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 aresetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWADDR" *)
    (* X_INTERFACE_PARAMETER = "PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 12" *)
    input  wire [11:0] s_axi_awaddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWPROT" *)
    input  wire [2:0]  s_axi_awprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWVALID" *)
    input  wire        s_axi_awvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi AWREADY" *)
    output wire        s_axi_awready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WDATA" *)
    input  wire [31:0] s_axi_wdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WSTRB" *)
    input  wire [3:0]  s_axi_wstrb,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WVALID" *)
    input  wire        s_axi_wvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi WREADY" *)
    output wire        s_axi_wready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BRESP" *)
    output wire [1:0]  s_axi_bresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BVALID" *)
    output wire        s_axi_bvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi BREADY" *)
    input  wire        s_axi_bready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARADDR" *)
    input  wire [11:0] s_axi_araddr,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARPROT" *)
    input  wire [2:0]  s_axi_arprot,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARVALID" *)
    input  wire        s_axi_arvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi ARREADY" *)
    output wire        s_axi_arready,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RDATA" *)
    output wire [31:0] s_axi_rdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RRESP" *)
    output wire [1:0]  s_axi_rresp,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RVALID" *)
    output wire        s_axi_rvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:aximm:1.0 s_axi RREADY" *)
    input  wire        s_axi_rready,

    output wire        alarm_waspada,
    output wire        alarm_kritis,
    output wire        alarm_sensor
);
    coldtrack_top #(
        .BERKAS_SIMPUL(BERKAS_SIMPUL),
        .BERKAS_POHON (BERKAS_POHON),
        .BERKAS_BASE  (BERKAS_BASE)
    ) u_ct (
        .clk           (aclk),
        .rst_n         (aresetn),
        .s_axil_awaddr (s_axi_awaddr),
        .s_axil_awvalid(s_axi_awvalid),
        .s_axil_awready(s_axi_awready),
        .s_axil_wdata  (s_axi_wdata),
        .s_axil_wstrb  (s_axi_wstrb),
        .s_axil_wvalid (s_axi_wvalid),
        .s_axil_wready (s_axi_wready),
        .s_axil_bresp  (s_axi_bresp),
        .s_axil_bvalid (s_axi_bvalid),
        .s_axil_bready (s_axi_bready),
        .s_axil_araddr (s_axi_araddr),
        .s_axil_arvalid(s_axi_arvalid),
        .s_axil_arready(s_axi_arready),
        .s_axil_rdata  (s_axi_rdata),
        .s_axil_rresp  (s_axi_rresp),
        .s_axil_rvalid (s_axi_rvalid),
        .s_axil_rready (s_axi_rready),
        .alarm_waspada (alarm_waspada),
        .alarm_kritis  (alarm_kritis),
        .alarm_sensor  (alarm_sensor)
    );

    // AxPROT tidak dipakai (semua akses diperlakukan sama)
    wire _prot_tidak_dipakai = ^{s_axi_awprot, s_axi_arprot};
endmodule
