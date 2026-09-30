"""Generate the same six-case live engineering story used by the browser."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aerolab.nacelle_story import engineering_story


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'nacelle-story.json')
    args=parser.parse_args()
    result=engineering_story()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    print(f"Wrote {args.output}; story identity {result['story_hash']}")
    for name,summary in result['summaries'].items():
        print(f"{name}: winding={summary['motor_temperature_c']:.3f}C HV={summary['hv_temperature_c']:.3f}C "
              f"mass={summary['mass_kg']:.3f}kg screening={summary['within_model_limits']} "
              f"physical_validation={summary['physically_validated']}")

if __name__=='__main__':
    main()
