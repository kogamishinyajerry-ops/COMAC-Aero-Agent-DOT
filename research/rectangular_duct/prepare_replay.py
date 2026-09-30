#!/usr/bin/env python3
"""Create isolated research output; never overwrite accepted application evidence."""
import os
from pathlib import Path
import shutil
import tempfile

CODE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CODE_DIR.parents[1]
ACCEPTED = (REPO_ROOT / 'examples' / 'rectangular_experiment').resolve()

def prepare_output():
    requested = os.environ.get('RECTANGULAR_OUTPUT_DIR')
    if requested:
        result = Path(requested).expanduser().resolve()
    else:
        root = REPO_ROOT / 'output'
        root.mkdir(parents=True, exist_ok=True)
        result = Path(tempfile.mkdtemp(prefix='rectangular-replay-', dir=root))
    if result == ACCEPTED or result.is_relative_to(ACCEPTED) or ACCEPTED.is_relative_to(result):
        raise ValueError('Replay output must be separate from the accepted evidence directory')
    if result == CODE_DIR or result.is_relative_to(CODE_DIR) or CODE_DIR.is_relative_to(result):
        raise ValueError('Replay output must be separate from the research code directory')
    result.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ACCEPTED / 'README.md', result / 'README.md')
    return result

if __name__ == '__main__':
    print(prepare_output())
