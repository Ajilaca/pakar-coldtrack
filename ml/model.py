import torch
import torch.nn as nn


class ColdTrackGRU(nn.Module):
    """Backbone GRU 2 lapis + statistik ringkasan jendela, lalu 3 kepala tugas.

    Statistik ringkasan (rata-rata, simpangan, min, maks, nilai terakhir, tren)
    disuplai langsung ke kepala. Alasannya: eksperimen menunjukkan GRU menghabiskan
    kapasitas untuk mempelajari statistik yang bisa dihitung langsung -- itu sebabnya
    XGBoost (yang menerimanya cuma-cuma) sempat unggul. Dengan ini GRU bebas fokus
    ke dinamika temporal, keunggulan yang tidak dimiliki model pohon.

    Hasilnya: Macro F1 naik 36% (0,440 -> 0,598) dan TTB jadi terbaik dari seluruh
    pendekatan yang diuji (21,84 menit).
    """

    N_STATS = 6      # mean, std, min, max, nilai terakhir, tren

    def __init__(self, n_features=12, hidden_size=64, num_layers=2, dropout=0.2, n_classes=7):
        super().__init__()

        self.gru = nn.GRU(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.dropout = nn.Dropout(dropout)

        fused_size = hidden_size + n_features * self.N_STATS      # 64 + 72 = 136
        self.head_forecast = nn.Linear(fused_size, 3)
        self.head_failure = nn.Linear(fused_size, n_classes)
        self.head_ttb = nn.Linear(fused_size, 1)

    def aggregate(self, x):
        """Ringkas jendela (batch, 60, 12) jadi (batch, 72). Tanpa parameter."""
        return torch.cat([
            x.mean(dim=1),
            x.std(dim=1),
            x.amin(dim=1),
            x.amax(dim=1),
            x[:, -1, :],                    # kondisi di menit terakhir ("sekarang")
            x[:, -1, :] - x[:, 0, :],       # tren: selisih akhir vs awal
        ], dim=1)

    def forward(self, x):
        # x: (batch, 60, 12) -- sudah ternormalisasi
        _, h_n = self.gru(x)
        fused = torch.cat([self.dropout(h_n[-1]), self.aggregate(x)], dim=1)

        forecast = self.head_forecast(fused)
        failure_logits = self.head_failure(fused)
        ttb = self.head_ttb(fused).squeeze(-1)

        return forecast, failure_logits, ttb

class ColdTrackDeploy(nn.Module):
    """Model siap-pakai untuk R3: terima 12 fitur MENTAH, keluarkan satuan asli.

    Normalisasi input dan denormalisasi output dibungkus di dalam sini supaya
    backend tidak perlu mengulang langkah preprocessing (sumber bug integrasi klasik).
    """

    def __init__(self, core, mean, std, temp_idx=0):
        super().__init__()
        self.core = core
        self.register_buffer('mean', torch.tensor(mean).view(1, 1, -1))
        self.register_buffer('std', torch.tensor(std).view(1, 1, -1))
        self.register_buffer('temp_mean', torch.tensor(float(mean[temp_idx])))
        self.register_buffer('temp_std', torch.tensor(float(std[temp_idx])))

    def forward(self, window_raw):
        x = (window_raw - self.mean) / self.std
        forecast, logits, ttb_log = self.core(x)

        forecast_c = forecast * self.temp_std + self.temp_mean      # kembali ke derajat C
        failure_prob = torch.softmax(logits, dim=1)                  # jadi probabilitas 0-1
        ttb_min = (torch.exp(ttb_log) - 1.0).clamp(min=0.0)          # kembali ke menit

        return forecast_c, failure_prob, ttb_min

if __name__ == "__main__":
    model = ColdTrackGRU()

    n_params = sum(p.numel() for p in model.parameters())
    print(f"Total parameter: {n_params:,} (target playbook: ~55.000)")

    # Tes cepat: dummy batch 4 contoh, bentuk (4, 60, 12)
    dummy_x = torch.randn(4, 60, 12)
    forecast, failure_logits, ttb = model(dummy_x)

    print(f"forecast shape       : {tuple(forecast.shape)}   (diharapkan: (4, 3))")
    print(f"failure_logits shape : {tuple(failure_logits.shape)}   (diharapkan: (4, 7))")
    print(f"ttb shape             : {tuple(ttb.shape)}   (diharapkan: (4,))")
