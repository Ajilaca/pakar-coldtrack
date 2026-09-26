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

Iteration 2 (engine rule changes) adds a second test set, the held-out trips of the new simulator
(`ml/dataset_v3.parquet`, not in git), and a sweep of the near-limit warning margin:

```bash
python -m eval.run_eval --tag iter2                  # v4 results
python -m eval.run_eval --tag iter2 --margin-sweep   # -> results/margin_sweep_iter2.json
python -m eval.sim_check --tag iter2                 # -> results/sim_v3_iter2.json (dataset_v3 test split)
python -m eval.make_artifact --iteration 2           # -> results/Evaluation_Artifact_Iteration_2.pdf
```

`sim_v3_iter1.json` was produced the same way with the engine at commit `ff9aacd`.

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
| `sim_check.py` | per-trip regression check on the new simulator's held-out trips (guards against tuning to v4) |
| `make_artifact.py` | builds `Evaluation_Artifact_Iteration.pdf` (`--tag iter1`) and `Evaluation_Artifact_Iteration_2.pdf` (`--iteration 2`) |
| `results/` | JSON results, figures, PDF |

## Same checks on the new simulator's data (in-distribution)

`run_eval --data` scores the same 19 checks, same thresholds, on a new-simulator parquet
(`ml/dataset_v3.parquet`, not in git, ~80 MB). The test split is `prep_windows.split_trips` seed 0,
the same trips `eval/sim_check.py` uses. Mapping and exclusions: `eval/new_sim_data.py`.

```bash
python -m eval.run_eval --data ml/dataset_v3.parquet --tag sim_iter2   # ~2-4 min
EVAL_TAG=sim_iter2 pytest eval/test_baseline.py -q
```

Report it next to the v4 run: v4 is out-of-distribution for the new model (trained on its own
simulator), the new-simulator run is in-distribution. Known by construction on this data: no vaccine
trips (the "every cargo profile" check fails), fresh-meat trips (0-4 C) are excluded (no backend profile).
