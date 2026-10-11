-- Fase 1 armada: skema TimescaleDB (CONTEXT_FLEET_SCALEUP.md §4 Fase 1).
-- Dijalankan sekali oleh app/db/migrate.py (dicatat di schema_migrations).

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE depots (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    city        text NOT NULL,
    lat         double precision NOT NULL,
    lon         double precision NOT NULL
);

CREATE TABLE trucks (
    id          text PRIMARY KEY,                 -- nomor polisi
    depot_id    text NOT NULL REFERENCES depots (id),
    label       text,
    active      boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);

-- Logger/sensor di truk. Firmware, gateway, kalibrasi, dan baterai datang dari topik MQTT
-- coldtrack/v1/{truck_id}/status (retained + LWT), bukan dari bacaan telemetri.
CREATE TABLE devices (
    id                   text PRIMARY KEY,
    truck_id             text NOT NULL REFERENCES trucks (id),
    firmware             text,
    gateway_version      text,
    calibrated_at        date,
    calibration_offset_c real,
    battery_v            real,
    online               boolean NOT NULL DEFAULT false,
    last_status_at       timestamptz
);

-- Engine membutuhkan riwayat sejak awal trip, jadi trip dicatat eksplisit.
CREATE TABLE trips (
    id               bigserial PRIMARY KEY,
    truck_id         text NOT NULL REFERENCES trucks (id),
    cargo_profile    text NOT NULL,
    mass_kg          real,
    cargo_value_idr  bigint,                       -- [ASUMSI] harga per kg di config.yaml
    depot_id         text REFERENCES depots (id),
    started_at       timestamptz NOT NULL,
    ended_at         timestamptz
);
CREATE UNIQUE INDEX trips_satu_aktif_per_truk ON trips (truck_id) WHERE ended_at IS NULL;

CREATE TABLE telemetry (
    truck_id         text NOT NULL REFERENCES trucks (id),
    ts               timestamptz NOT NULL,         -- UTC
    device_id        text,
    seq              bigint,
    temp_c           real NOT NULL,
    humidity         real NOT NULL,
    ambient_c        real NOT NULL,
    door_open        boolean NOT NULL,
    reefer_on        boolean NOT NULL,
    speed_kmh        real NOT NULL,
    harsh_events     integer NOT NULL DEFAULT 0,
    solar_radiation  real,
    lat              double precision,
    lon              double precision,
    received_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (truck_id, ts)                     -- dedupe: publish ulang tidak menggandakan
);
SELECT create_hypertable('telemetry', 'ts', chunk_time_interval => interval '1 day');

CREATE TABLE predictions (
    truck_id          text NOT NULL REFERENCES trucks (id),
    ts                timestamptz NOT NULL,        -- menit terakhir jendela
    trip_id           bigint REFERENCES trips (id),
    status            text NOT NULL,               -- AMAN|WASPADA|KRITIS|TIDAK_ADA_DATA|MENUNGGU_DATA|DATA_TIDAK_LENGKAP
    risk_index        real,
    ttb_show_min      real,
    ttb_model_min     real,
    failure_label     text,
    failure_conf      real,
    probabilities     jsonb,
    forecast          jsonb,
    data_lengkap      boolean,
    sensor_health     jsonb,
    model_version     text,
    provider          text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (truck_id, ts)
);
SELECT create_hypertable('predictions', 'ts', chunk_time_interval => interval '7 days');

CREATE TABLE truck_state (
    truck_id         text PRIMARY KEY REFERENCES trucks (id),
    status           text NOT NULL,
    last_ts          timestamptz,                  -- bacaan terakhir yang diterima
    last_prediction  jsonb,
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Fase penanganan: hanya TERDETEKSI dan GAGAL diisi sistem; sisanya oleh operator (audit trail).
CREATE TABLE incidents (
    id               bigserial PRIMARY KEY,
    truck_id         text NOT NULL REFERENCES trucks (id),
    trip_id          bigint REFERENCES trips (id),
    phase            text NOT NULL DEFAULT 'TERDETEKSI'
                     CHECK (phase IN ('TERDETEKSI', 'DITUGASKAN', 'DITANGANI', 'SELESAI', 'GAGAL')),
    status_puncak    text NOT NULL,
    failure_label    text,
    detected_at      timestamptz NOT NULL,
    breach_at        timestamptz,                  -- T_cargo_est >= t_hi
    closed_at        timestamptz,
    assignee         text,
    cargo_value_idr  bigint,
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX incidents_satu_terbuka_per_truk ON incidents (truck_id)
    WHERE phase NOT IN ('SELESAI', 'GAGAL');

CREATE TABLE incident_events (
    id           bigserial PRIMARY KEY,
    incident_id  bigint NOT NULL REFERENCES incidents (id),
    at           timestamptz NOT NULL DEFAULT now(),
    actor        text NOT NULL,                    -- 'Sistem' atau nama operator (tanpa login: di luar cakupan)
    from_phase   text,
    to_phase     text NOT NULL,
    note         text
);

CREATE TABLE notifications (
    id           bigserial PRIMARY KEY,
    created_at   timestamptz NOT NULL DEFAULT now(),
    truck_id     text REFERENCES trucks (id),
    incident_id  bigint REFERENCES incidents (id),
    level        text NOT NULL CHECK (level IN ('info', 'waspada', 'kritis')),
    title        text NOT NULL,
    body         text,
    read_at      timestamptz
);

-- Kebijakan Timescale [ASUMSI]: kompresi > 7 hari, retensi 180 hari, agregat 15 menit.
ALTER TABLE telemetry SET (timescaledb.compress, timescaledb.compress_segmentby = 'truck_id');
SELECT add_compression_policy('telemetry', interval '7 days');
SELECT add_retention_policy('telemetry', interval '180 days');
SELECT add_retention_policy('predictions', interval '180 days');

-- Agregat 15 menit ada di 002 (CREATE MATERIALIZED VIEW ... continuous tidak boleh di dalam transaksi;
-- skrip multi-pernyataan dijalankan sebagai satu transaksi implisit).
