# ColdTrack AI — evaluation suite

Scores the system **as deployed** (backend ONNX models + rule engine + HTTP API) on the
held-out test split of dataset v4 (split by `trip_id`).

```bash
pip install -r backend/requirements.txt scikit-learn xgboost matplotlib reportlab torch
python -m ml.preprocess.build_windows            # once; only needed for ml/ baselines
python -m eval.run_eval --tag baseline           # ~2 min -> eval/results/baseline_results.json
pytest eval/test_baseline.py -q                  # 23 acceptance checks (failures = documented weaknesses)
python -m eval.make_artifact --tag baseline      # -> eval/results/Evaluation_Artifact_baseline.pdf
```

After an iteration, re-run with `--tag iter1` (and `EVAL_TAG=iter1 pytest ...`) to get the before/after comparison.

| File | Purpose |
|---|---|
| `common.py` | test-window loading (with metadata), payload builder, ONNX runner, mirror of backend TTB gating |
| `run_eval.py` | G1 forecast · G2 classification · G3 imminent breach · G4 robustness · G5 end-to-end API |
| `test_baseline.py` | acceptance thresholds, one failure condition per check, with the reason |
| `make_artifact.py` | builds the Evaluation Artifact PDF |
| `results/` | JSON results, figures, PDF |
