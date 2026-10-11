-- Frame Figma "Ringkasan + notifikasi" dan "Kerugian" (11 Oktober 2026).
-- Level 'ok' untuk notifikasi pemulihan (ikon hijau "kembali AMAN").
ALTER TABLE notifications DROP CONSTRAINT notifications_level_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_level_check CHECK (level IN ('info', 'ok', 'waspada', 'kritis'));

-- TTB (mesin fisika) saat insiden terdeteksi: lead time = perkiraan breach - deteksi untuk insiden
-- tanpa breach (app/fleet/loss.py). Insiden dengan breach memakai breach_at - detected_at.
ALTER TABLE incidents ADD COLUMN ttb_terdeteksi_min real;
