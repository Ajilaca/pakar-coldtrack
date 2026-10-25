-- Hasil chip edge (hw/, KV260) per bacaan: rekaman yang disegel, rantai hash, paket hasil, dan HMAC
-- (app/edge.py, docs/device_contract.md). Worker-infer memakai paket yang verifikasinya sah alih-alih
-- menghitung ulang status dan diagnosis di cloud.
CREATE TABLE edge_results (
    truck_id     text NOT NULL REFERENCES trucks (id),
    ts           timestamptz NOT NULL,          -- ts bacaan yang sama di tabel telemetry
    device_id    text,
    seq_rek      bigint NOT NULL,               -- seq di dalam rekaman 23 byte (0 = awal trip, rantai mulai dari nol)
    rek          bytea NOT NULL,
    rantai       bytea NOT NULL,
    paket        bytea NOT NULL,
    mac          bytea NOT NULL,
    skor         jsonb,                         -- 7 skor kelas Q8.16, tidak ikut MAC
    verifikasi   text NOT NULL,                 -- OK | OK_RANTAI_BARU | MAC_SALAH | RANTAI_PUTUS | REKAMAN_BEDA | TANPA_KUNCI
    received_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (truck_id, ts)
);
SELECT create_hypertable('edge_results', 'ts', chunk_time_interval => interval '1 day');
CREATE INDEX edge_results_rantai ON edge_results (truck_id, seq_rek, ts DESC);
