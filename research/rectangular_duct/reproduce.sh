#!/usr/bin/env bash
# Offline research replay; run from any working directory. No downloads.
set -euo pipefail
CODE_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(cd -- "$CODE_DIR/../.." && pwd)"
export RECTANGULAR_OUTPUT_DIR="$(python "$CODE_DIR/prepare_replay.py")"
printf "Research replay output: %s\n" "$RECTANGULAR_OUTPUT_DIR"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export MPLCONFIGDIR="$RECTANGULAR_OUTPUT_DIR/.mplconfig" XDG_CACHE_HOME="$RECTANGULAR_OUTPUT_DIR/.cache"
python "$CODE_DIR/test_packaging.py"
python "$CODE_DIR/rectangular_graetz.py" verify
python "$CODE_DIR/independent_galerkin_reference.py" > "$RECTANGULAR_OUTPUT_DIR/independent_galerkin_reference.jsonl"
python "$CODE_DIR/compare_independent_reference.py"
python "$CODE_DIR/rectangular_graetz.py" curve
python "$CODE_DIR/compare_experiment.py"
python "$CODE_DIR/render_plots.py"
python "$CODE_DIR/compare_accepted_evidence.py"
python "$CODE_DIR/audit_package.py"
