#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
OUT=${OPENFOAM_DIRECTIONAL_OUTPUT:-$REPO/output/openfoam-directional-replay-$(date -u +%Y%m%dT%H%M%SZ)}
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
# Uses the installed isolated tools and retained original source fields.
# Each solver timeout and aggregate successful/failed solver time are bounded by plan.json.
python "$HERE/study.py" --output "$OUT"
printf 'Fresh directional data saved to %s\n' "$OUT"
