# Experimental Sweep

Run the weekend sweep from tmux so disconnects do not stop it:

```bash
tmux new -s 3dreefs-sweep
PYTHONPATH=src uv run python -m sweep.run_sweep smoke
PYTHONPATH=src uv run python -m sweep.run_sweep run
```

Progress is written to `data/experiments/README.md`, with machine-readable rows in
`data/experiments/results.csv`.

The runner is intentionally serial and resumable. Re-running `run` skips completed
experiments already present in `results.csv`.
