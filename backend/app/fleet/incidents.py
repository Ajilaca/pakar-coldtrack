"""Transisi insiden per truk (tanpa I/O). Worker-infer menerapkan Rencana ke DB.

Aturan (CONTEXT_FLEET_SCALEUP.md Fase 3; pilihan [DESAIN] ditandai):
- Dua jenis insiden [DESAIN], masing-masing satu terbuka per (truk, jenis, trip):
    kondisi  episode WASPADA/KRITIS; punya nilai muatan (loss.py).
    data     episode TIDAK_ADA_DATA; tanpa nilai kerugian. Dipisah supaya putus data tidak "tereskalasi"
             menjadi insiden kondisi dengan detected_at/lead time yang salah.
  MENUNGGU_DATA dan DATA_TIDAK_LENGKAP tidak membuka insiden (kualitas data, ditampilkan di UI).
- Insiden dibuka (TERDETEKSI, oleh Sistem) di AWAL episode bila trip itu belum punya insiden terbuka
  sejenis. Insiden yang ditutup operator di tengah episode tidak dibuka ulang sampai episode berikutnya.
- kondisi: eskalasi WASPADA -> KRITIS dinotifikasi. breach_at diisi saat T_cargo_est >= t_hi pertama kali;
  insiden otomatis GAGAL. Kembali AMAN tanpa breach: recovered_at diisi (dihitung "berhasil diatasi");
  kambuh sebelum ditutup operator: recovered_at dikosongkan dan dinotifikasi lagi.
- data: pulih bila ada bacaan lagi (status apa pun selain TIDAK_ADA_DATA); hanya pembukaan yang
  dinotifikasi [DESAIN] supaya putus sinyal berulang tidak membanjiri kotak masuk.
- Hanya TERDETEKSI dan GAGAL yang otomatis; DITUGASKAN/DITANGANI/SELESAI lewat operator (PATCH, Fase 4).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

EPISODE = {"kondisi": {"WASPADA", "KRITIS"}, "data": {"TIDAK_ADA_DATA"}}
BOBOT = {"WASPADA": 1, "KRITIS": 2}
FASE_TERBUKA = ("TERDETEKSI", "DITUGASKAN", "DITANGANI")
LEVEL = {"TIDAK_ADA_DATA": "info", "WASPADA": "waspada", "KRITIS": "kritis"}

# Nama diagnosis untuk teks notifikasi (sama dengan frontend/src/lib/labels.ts, frame Figma).
NAMA_LABEL = {
    "normal_sehat": "Normal / sehat", "pintu_terbuka": "Pintu terbuka", "pintu_terbuka_lama": "Pintu terbuka lama",
    "kejutan_ambien_ekstrem": "Kejut ambien", "masalah_sensor": "Masalah sensor",
    "suhu_muatan_mendekati_batas": "Suhu muatan mendekati batas", "reefer_mati_total": "Reefer mati total",
    "prapendinginan_buruk": "Prapendinginan buruk", "degradasi_bertahap": "Degradasi pendinginan",
}


def _isi(label: str | None, ttb: float | None, reason: str | None) -> str | None:
    """Subjudul notifikasi kondisi (frame "Ringkasan + notifikasi"): 'Degradasi pendinginan · TTB 11 menit'."""
    bagian = [NAMA_LABEL.get(label, label.replace("_", " "))] if label else []
    if ttb is not None:
        bagian.append(f"TTB {round(ttb)} menit")
    return " · ".join(bagian) or reason


@dataclass
class Rencana:
    jenis: str
    buka: dict[str, Any] | None = None                    # kolom insiden baru
    ubah: dict[str, Any] = field(default_factory=dict)    # kolom insiden terbuka yang diperbarui
    events: list[dict[str, Any]] = field(default_factory=list)
    notifikasi: list[dict[str, Any]] = field(default_factory=list)

    @property
    def kosong(self) -> bool:
        return self.buka is None and not self.ubah and not self.events and not self.notifikasi


def langkah(jenis: str, truck_id: str, prev_status: str | None, status: str, terbuka: dict[str, Any] | None,
            ts: datetime, breach: bool = False, label: str | None = None, reason: str | None = None,
            trip_id: int | None = None, cargo_value_idr: int | None = None, ttb: float | None = None) -> Rencana:
    """terbuka: insiden terbuka jenis ini untuk trip aktif (id, phase, status_puncak, breach_at, recovered_at).
    ttb: TTB mesin fisika saat ini (menit; None = di atas batas tampil atau tidak ada)."""
    ep = EPISODE[jenis]
    r = Rencana(jenis)
    if terbuka is None:
        if status in ep and prev_status not in ep:
            r.buka = {"truck_id": truck_id, "trip_id": trip_id, "jenis": jenis, "phase": "TERDETEKSI",
                      "status_puncak": status, "failure_label": label if jenis == "kondisi" else None,
                      "detected_at": ts, "cargo_value_idr": cargo_value_idr if jenis == "kondisi" else None,
                      "ttb_terdeteksi_min": ttb if jenis == "kondisi" else None}
            if jenis == "kondisi":
                judul, isi = f"{truck_id} berstatus {status}", _isi(label, ttb, reason)
            else:
                judul, isi = f"{truck_id} tidak ada data", "Tidak ada bacaan dari perangkat · tidak pernah ditampilkan AMAN"
            r.events.append({"actor": "Sistem", "from_phase": None, "to_phase": "TERDETEKSI", "note": reason or judul})
            r.notifikasi.append({"level": LEVEL[status], "title": judul, "body": isi})
            if jenis == "kondisi" and breach:          # breach di menit yang sama dengan deteksi
                r.buka.update(phase="GAGAL", breach_at=ts, closed_at=ts)
                r.events.append(_event_gagal("TERDETEKSI"))
                r.notifikasi.append(_notif_gagal(truck_id))
        return r

    if jenis == "data":
        if status not in ep and terbuka.get("recovered_at") is None:
            r.ubah["recovered_at"] = ts
            r.events.append({"actor": "Sistem", "from_phase": terbuka["phase"], "to_phase": terbuka["phase"],
                             "note": "Bacaan kembali masuk."})
        elif status in ep and terbuka.get("recovered_at") is not None:
            r.ubah["recovered_at"] = None
        return r

    if status in ep and BOBOT[status] > BOBOT.get(terbuka.get("status_puncak"), 0):
        r.ubah["status_puncak"] = status
        if label:
            r.ubah["failure_label"] = label
        r.notifikasi.append({"level": LEVEL[status], "title": f"{truck_id} memburuk ke {status}",
                             "body": _isi(label, ttb, reason)})
    if breach and terbuka.get("breach_at") is None:
        r.ubah.update(breach_at=ts, phase="GAGAL", closed_at=ts)
        r.events.append(_event_gagal(terbuka["phase"]))
        r.notifikasi.append(_notif_gagal(truck_id))
        return r
    if status == "AMAN" and terbuka.get("recovered_at") is None:
        r.ubah["recovered_at"] = ts
        r.events.append({"actor": "Sistem", "from_phase": terbuka["phase"], "to_phase": terbuka["phase"],
                         "note": "Status kembali AMAN tanpa melewati batas."})
        r.notifikasi.append({"level": "ok", "title": f"{truck_id} kembali AMAN", "body": "Tanpa melewati batas suhu"})
    elif status in ep and terbuka.get("recovered_at") is not None:
        r.ubah["recovered_at"] = None
        if "status_puncak" not in r.ubah:
            r.notifikasi.append({"level": LEVEL[status], "title": f"{truck_id} kembali {status}",
                                 "body": _isi(label, ttb, reason)})
    return r


def notifikasi_sensor(truck_id: str, grade_lalu: str | None, sh: dict[str, Any] | None) -> dict[str, Any] | None:
    """Notifikasi saat kesehatan sensor BARU turun ke grade Ganti (frame "Ringkasan + notifikasi")."""
    if not sh or sh.get("grade") != "Ganti" or grade_lalu == "Ganti":
        return None
    return {"level": "waspada", "title": f"{truck_id}: sensor perlu diganti",
            "body": f"Skor sensor {sh.get('score')} · grade Ganti"}


def _event_gagal(dari: str) -> dict[str, Any]:
    return {"actor": "Sistem", "from_phase": dari, "to_phase": "GAGAL",
            "note": "Suhu muatan (estimasi) melewati batas atas."}


def _notif_gagal(truck_id: str) -> dict[str, Any]:
    return {"level": "kritis", "title": f"{truck_id} melewati batas suhu", "body": "Insiden ditandai GAGAL otomatis"}
