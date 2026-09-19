"""Local field validation; no tuning or training options."""
import argparse
import json
from pathlib import Path
from src.field_cohort import ROOT, freeze_protocol, freeze_cohort, private_location, validate_inputs, write_new
from src.field_evaluation import evaluate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    commands.add_parser('freeze-protocol',help='One-time developer bootstrap; existing protocol cannot be overwritten')
    for command in ('init','validate','freeze','evaluate'):
        child = commands.add_parser(command)
        child.add_argument('--root',type=Path,default=ROOT/'data/field_v07/cohort_001')
        if command == 'freeze':
            child.add_argument('--manifest',type=Path,required=True)
        if command == 'evaluate':
            child.add_argument('--manifest',type=Path,required=True)
            child.add_argument('--cohort-sha256',required=True,help='Hash printed by freeze; retain it in your collection log')
            child.add_argument('--output',type=Path,required=True,help='New local output directory (never overwritten)')
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze-protocol':
            result = freeze_protocol()
            print('Protocol created; never refreeze to accept model/configuration drift.')
        elif args.command == 'init':
            root = private_location(args.root)
            root.mkdir(parents=True,exist_ok=False)
            (root/'images').mkdir()
            write_new(root/'collection.json',{'cohort_id':'cohort_001','purpose':'independent_field_validation','scenes':[],'images':[]})
            write_new(root/'ground_truth.json',[])
            print('Empty local collection created. Add real consented images and blind counts; no example photos were fabricated.')
            return 0
        elif args.command == 'validate':
            result = validate_inputs(args.root)
            print(f"Validated {len(result['images'])} images / {len(result['scenes'])} groups; independence also requires collector review.")
            return 0
        elif args.command == 'freeze':
            result = freeze_cohort(args.root,args.manifest)
            print('Frozen cohort SHA-256: '+result['cohort_sha256'])
            return 0
        else:
            result = evaluate(args.root,args.manifest,args.cohort_sha256,args.output)
            print('Completed count-only evaluation: '+str(args.output/'REPORT.md'))
            print(json.dumps(result['analysis']['overall'],indent=2))
            return 0
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('Field operation failed: '+str(error))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
