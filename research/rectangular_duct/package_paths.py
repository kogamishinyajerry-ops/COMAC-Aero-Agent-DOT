"""Standard-library paths and bounded file helpers for offline package audits."""
import hashlib
import json
import os
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
INPUT_DIR = CODE_DIR / 'inputs'
ORIGINAL_DIR = CODE_DIR / 'original_freeze'
ROOT = Path(os.environ.get('RECTANGULAR_OUTPUT_DIR', CODE_DIR.parents[1] / 'examples' / 'rectangular_experiment')).resolve()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, obj):
    raw = (json.dumps(obj, indent=2, allow_nan=False) + '\n').encode()
    if len(raw) >= 100_000:
        raise ValueError(f'Compact evidence size limit exceeded: {path}: {len(raw)}')
    Path(path).write_bytes(raw)
