-- Agregat kontinu 15 menit untuk grafik riwayat. SATU pernyataan per berkas: Timescale menolak
-- CREATE MATERIALIZED VIEW ... (timescaledb.continuous) di dalam blok transaksi.
CREATE MATERIALIZED VIEW telemetry_15m WITH (timescaledb.continuous) AS
SELECT truck_id, time_bucket(interval '15 minutes', ts) AS bucket,
       avg(temp_c) AS temp_c_avg, max(temp_c) AS temp_c_max, min(temp_c) AS temp_c_min,
       avg(ambient_c) AS ambient_c_avg, bool_or(door_open) AS door_open_any, count(*) AS n
FROM telemetry
GROUP BY truck_id, bucket
WITH NO DATA
