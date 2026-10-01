#!/usr/bin/env bash
set -euo pipefail
HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
PYTHON=${PYTHON:-python}
# No package installation or network operation. This uses the already installed tools.
mkdir -p "$REPO/output"
OUT=${OPENFOAM_STUDY_OUTPUT:-$(mktemp -d "$REPO/output/openfoam-3d-replay-XXXXXXXX")}
mkdir -p "$OUT"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR="$OUT/.mplconfig"
"$PYTHON" "$HERE/study.py" run --output "$OUT" --levels 0,1,2
"$PYTHON" "$HERE/references.py" --output "$OUT"
"$PYTHON" "$HERE/diagnostics.py" extension --base "$OUT" --output "$OUT/diagnostics"
"$PYTHON" "$HERE/diagnostics.py" stationarity --base "$OUT" --output "$OUT/stationarity"
# Separately registered extra grid is reproduced without relabeling original failure.
"$PYTHON" "$HERE/additional_refinement.py" --output "$OUT"
"$PYTHON" "$HERE/diagnostics.py" stationarity --base "$OUT" --output "$OUT/stationarity" --levels 3
printf 'New replay saved to %s\n' "$OUT"
