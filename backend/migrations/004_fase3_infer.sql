-- Fase 3 armada: kolom yang dibutuhkan worker-infer (app/workers/infer.py, app/fleet/incidents.py).

-- Dua jenis insiden [DESAIN]: 'kondisi' (WASPADA/KRITIS, punya nilai kerugian) dan 'data' (TIDAK_ADA_DATA,
-- tanpa nilai kerugian). Satu insiden terbuka per (truk, jenis, trip): insiden trip lama yang belum ditutup
-- operator tidak menelan episode trip baru.
ALTER TABLE incidents ADD COLUMN jenis text NOT NULL DEFAULT 'kondisi' CHECK (jenis IN ('kondisi', 'data'));
ALTER TABLE incidents ADD COLUMN recovered_at timestamptz;          -- kembali normal tanpa breach (loss.py)
DROP INDEX incidents_satu_terbuka_per_truk;
CREATE UNIQUE INDEX incidents_satu_terbuka ON incidents (truck_id, jenis, coalesce(trip_id, 0))
    WHERE phase NOT IN ('SELESAI', 'GAGAL');
CREATE INDEX incidents_truk_waktu ON incidents (truck_id, detected_at DESC);

ALTER TABLE truck_state ADD COLUMN trip_id bigint REFERENCES trips (id);
ALTER TABLE truck_state ADD COLUMN sensor_health jsonb;              -- skor 0-100, grade, alasan
ALTER TABLE truck_state ADD COLUMN perlu_diperbarui jsonb;           -- temuan perangkat (devices.py)
ALTER TABLE truck_state ADD COLUMN computed_at timestamptz;          -- jam bersama saat dihitung (app/clock)

CREATE INDEX notifications_belum_dibaca ON notifications (created_at DESC) WHERE read_at IS NULL;
