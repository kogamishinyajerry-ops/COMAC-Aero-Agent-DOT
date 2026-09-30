#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 XDG_CACHE_HOME="$PWD/.cache"
python rectangular_graetz.py verify | tee verification.log
python independent_galerkin_reference.py > independent_galerkin_reference.jsonl
python compare_independent_reference.py
python rectangular_graetz.py curve | tee freeze.log
python compare_experiment.py | tee comparison.log
python render_plots.py
python audit_artifacts.py | tee artifact_audit.log
