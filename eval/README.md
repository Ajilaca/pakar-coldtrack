# ColdTrack AI — evaluation suite

Scores the system **as deployed** (`backend/app/inference.py`: physics/rule engine +
`coldtrack_gru.onnx` + `coldtrack_ttb.onnx`, and the HTTP API) on the held-out test split of
dataset v4 (split by `trip_id`) — the same trips and windows the baseline was scored on.

```bash
pip install -r backend/requirements.txt
python -m eval.run_eval --tag iter1              # ~4 min -> eval/results/iter1_results.json
pytest eval/test_baseline.py -q                  # 19 acceptance checks (failures = documented weaknesses)
python -m eval.make_artifact --tag iter1         # -> eval/results/Evaluation_Artifact_Iteration.pdf (before/after)
```

Contract `hybrid-v3` (current): 3 independent events (door open long, ambient shock, sensor fault),
cargo-temperature forecast, status and TTB from the engine. v4's fault modes map to events as
A1 → door, A7 → shock, A5/A6 → sensor; A2/A3/A4/A8 have no event and are judged through status/TTB only.
v4 has no cargo mass, so the cargo profile's `mass_kg_default` is used, as in production.

The model was trained on its own physics simulator, not on v4, so v4 is an out-of-distribution test
for it (the baseline was trained on v4).

`baseline` (old 7-class contract) can no longer be re-run: its models were removed. Its results and
check outcomes are archived in `results/baseline_results.json` and `results/Evaluation_Artifact_baseline.pdf`.

| File | Purpose |
|---|---|
| `common.py` | test-trip loading, readings builder, per-trip scoring via `inference_engine.analyze_trip` |
| `run_eval.py` | G1 forecast · G2 events · G3 imminent breach · G4 robustness · G5 end-to-end API (+ parity with G1–G3) |
| `test_baseline.py` | acceptance thresholds (baseline's where the metric carries over), one failure condition per check |
| `make_artifact.py` | builds `Evaluation_Artifact_Iteration.pdf` + `iteration_fig_*.png`; "before" column from `baseline_results.json` |
| `results/` | JSON results, figures, PDF |
