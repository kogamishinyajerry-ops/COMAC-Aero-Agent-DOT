#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python verify_tradeoff.py > verification.log 2>&1
python check_inherited_operator.py > inherited_operator_check.log 2>&1
python run_sweep.py > sweep.log 2>&1
python summarize_results.py
python audit_study.py
python summarize_results.py
python audit_study.py
