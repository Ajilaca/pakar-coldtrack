import torch
import torch.nn as nn


class ColdTrackGRU(nn.Module):
    """Backbone GRU 2 lapis + 3 kepala tugas (forecast, failure mode, time-to-breach)."""

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

        self.head_forecast = nn.Linear(hidden_size, 3)
        self.head_failure = nn.Linear(hidden_size, n_classes)
        self.head_ttb = nn.Linear(hidden_size, 1)

    def forward(self, x):
        # x: (batch, 60, 12)
        _, h_n = self.gru(x)
        last_hidden = h_n[-1]              # (batch, hidden_size) -- lapis atas, menit terakhir
        last_hidden = self.dropout(last_hidden)

        forecast = self.head_forecast(last_hidden)          # (batch, 3)
        failure_logits = self.head_failure(last_hidden)     # (batch, 7)
        ttb = self.head_ttb(last_hidden).squeeze(-1)         # (batch,) -- dari (batch,1) jadi (batch,)

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
