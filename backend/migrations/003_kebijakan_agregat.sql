-- [ASUMSI] segarkan agregat 15 menit untuk 1 hari terakhir setiap 15 menit.
SELECT add_continuous_aggregate_policy('telemetry_15m', start_offset => interval '1 day',
                                       end_offset => interval '15 minutes', schedule_interval => interval '15 minutes');
