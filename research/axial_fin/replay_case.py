#!/usr/bin/env python3
"""Research subprocess: execute one unchanged scalar-run case in a fresh snapshot."""
import argparse, importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True
if sys.platform != 'linux':
    raise SystemExit('Numerical replay requires Linux: immutable core interprets ru_maxrss as KiB')

def main():
    p = argparse.ArgumentParser(); p.add_argument('--nx', type=int, required=True); p.add_argument('--ny', type=int, required=True); p.add_argument('--nz', type=int, required=True); p.add_argument('--speed', type=float, required=True); p.add_argument('--output', type=pathlib.Path, required=True); a = p.parse_args()
    source = pathlib.Path(__file__).resolve().parent/'study/axial_fin_numerical_run.py'
    spec = importlib.util.spec_from_file_location('exact_axial_scalar_run', source); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    r = mod.AxialModel(a.nx, a.ny, a.nz, a.speed, 1.).solve(include_samples=False)
    data = (json.dumps(r, indent=2, allow_nan=False)+'\n').encode()
    if len(data) >= 100000: raise ValueError('Replay result exceeds JSON size cap')
    with a.output.open('xb') as f: f.write(data)

if __name__ == '__main__': main()
