#!/usr/bin/env python3
"""Maintain exercise drafts, targeted renders, and explicitly reviewed releases."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from core import delivery
from core.approvals import is_approved, record_review

ROOT = Path(__file__).resolve().parent


def exercise_id(value):
    if not re.fullmatch(r'[a-z0-9_]+', value):
        raise argparse.ArgumentTypeError('Use lowercase letters, numbers and underscores')
    return value


def ids():
    return sorted(p.stem for p in (ROOT / 'catalog').glob('*.json'))


def pair(eid):
    return [delivery.read(ROOT / folder / (eid + '.json')) for folder in ('catalog', 'motion/specs')]


def validate(eid):
    cat, motion = pair(eid)
    if cat.get('id') != eid or motion.get('id') != eid:
        raise ValueError(eid + ': IDs must match both filenames')
    for key in ('name', 'breathing', 'source'):
        if not isinstance(cat.get(key), str) or not cat[key].strip():
            raise ValueError(eid + ': catalog needs ' + key)
    for key in ('primary', 'secondary', 'equipment', 'steps', 'cues', 'mistakes'):
        value = cat.get(key)
        if not isinstance(value, list) or not all(isinstance(x, str) and x.strip() for x in value):
            raise ValueError(eid + ': catalog needs a string list for ' + key)
        if key in ('primary', 'steps', 'cues', 'mistakes') and not value:
            raise ValueError(eid + ': empty ' + key)
    if 'TODO:' in json.dumps(cat):
        raise ValueError(eid + ': finish the TODO catalog fields before rendering')
    pattern = motion.get('pattern', '')
    if not re.fullmatch(r'[a-z_]+', pattern) or not (ROOT / 'motion/patterns' / (pattern + '.py')).is_file():
        raise ValueError(eid + ': unknown motion pattern')
    tempo = motion.get('tempo', {})
    if not tempo or any(type(n) is not int or n < 0 for n in tempo.values()) or sum(tempo.values()) < 2:
        raise ValueError(eid + ': tempo must contain nonnegative frame counts')
    views = motion.get('views', [])
    names = [v if isinstance(v, str) else v.get('name', '') for v in views]
    if not names or len(set(names)) != len(names) or any(not re.fullmatch(r'[A-Za-z0-9_]+', n) for n in names):
        raise ValueError(eid + ': views need unique valid names')
    if type(cat.get('reviewed')) is not bool or type(motion.get('approved')) is not bool:
        raise ValueError(eid + ': review flags must be booleans')


def create(eid, template, name):
    exercise_id(eid)
    exercise_id(template)
    cat, motion = pair(template)
    paths = [ROOT / folder / (eid + '.json') for folder in ('catalog', 'motion/specs')]
    if any(p.exists() for p in paths):
        raise ValueError(eid + ': already exists; use revise instead')
    cat.update(id=eid, name=name, reviewed=False, source='TODO: licensed data source or original description',
               steps=['TODO: write steps'], cues=['TODO: write cues'],
               mistakes=['TODO: write common mistakes'], breathing='TODO: write breathing notes')
    for key in ('adaptation', 'source_equipment'):
        cat.pop(key, None)
    motion.update(id=eid, approved=False)
    for path, value in zip(paths, (cat, motion)):
        path.write_text(json.dumps(value, indent=2) + '\n')
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('status', 'validate'):
        p = commands.add_parser(command)
        p.add_argument('ids', nargs='*', type=exercise_id)
    p = commands.add_parser('new')
    p.add_argument('id', type=exercise_id)
    p.add_argument('--from', dest='template', required=True, type=exercise_id)
    p.add_argument('--name', required=True)
    p = commands.add_parser('revise')
    p.add_argument('id', type=exercise_id)
    p.add_argument('--note', required=True)
    for command in ('preview', 'render'):
        p = commands.add_parser(command)
        p.add_argument('ids', nargs='+', type=exercise_id)
    p = commands.add_parser('approve')
    p.add_argument('--model',choices=('male','female'),required=True)
    p.add_argument('ids', nargs='*', type=exercise_id)
    p.add_argument('--all', action='store_true')
    p.add_argument('--reviewed', action='store_true', help='Explicit human review of the current versions')
    p.add_argument('--note', required=True)
    commands.add_parser('audit')
    args = parser.parse_args(argv)
    try:
        if args.command == 'new':
            for path in create(args.id, args.template, args.name):
                print(path.relative_to(ROOT))
            print('Draft created. Replace TODOs and check inherited muscles, equipment and motion parameters.')
        elif args.command == 'revise':
            record_review(args.id, False, None, args.note, ROOT)
            delivery.rebuild_manifest()
            print(args.id + ': reopened for changes; approval revoked')
        elif args.command == 'approve':
            if not args.reviewed or (args.all and args.ids) or not (args.all or args.ids):
                parser.error('Use IDs or --all, plus --reviewed after explicit human approval')
            entries = []
            for eid in ids() if args.all else args.ids:
                validate(eid)
                entry = delivery.read(ROOT / 'dist' / eid / args.model / 'asset.json')
                delivery.current_asset(eid, entry)
                entries.append((eid, entry))
            for eid, entry in entries:
                record_review(eid, True, entry, args.note, ROOT)
            delivery.rebuild_manifest()
            print(f'{len(entries)} current versions approved')
        elif args.command in ('preview', 'render'):
            for eid in args.ids:
                validate(eid)
            if args.command == 'render':
                subprocess.run([sys.executable, 'core/batch.py', *args.ids], cwd=ROOT, check=True)
            else:
                for eid in args.ids:
                    subprocess.run([sys.executable, 'build.py', eid, '--quick'], cwd=ROOT, check=True)
                    subprocess.run([sys.executable, 'qa/check.py', eid], cwd=ROOT, check=True)
        elif args.command == 'audit':
            delivery.rebuild_manifest()
            subprocess.run([sys.executable, 'core/verify_delivery.py'], cwd=ROOT, check=True)
        else:
            selected = args.ids or ids()
            for eid in selected:
                if args.command == 'validate':
                    validate(eid)
                    print(eid + ': valid')
                    continue
                try:
                    entry = delivery.read(ROOT / 'dist' / eid / 'asset.json')
                    delivery.current_asset(eid, entry)
                    state = 'APPROVED' if is_approved(eid, entry, ROOT) else 'NEEDS REVIEW'
                except (OSError, ValueError, KeyError) as exc:
                    state = 'NEEDS BUILD: ' + str(exc)
                print(eid + ': ' + state)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, str(exc) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
