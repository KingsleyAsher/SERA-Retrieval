"""Run public frozen regressions in a disposable copy, preserving archived outputs."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .runtime import atomic_publish

SCRIPTS = ['阶段二/check_framework.py', '阶段二/review_fix_probes.py',
           '阶段二/check_review_boundaries.py', '阶段三-候选复用/check_candidate_engine.py',
           '阶段三-紧凑缓存与IVF/checks.py']


def run_regressions():
    root = Path(__file__).resolve().parents[2]
    relative = Path('research/ChatGPT/总体计划执行-v1')
    before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (root / relative).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    results = []
    with tempfile.TemporaryDirectory(prefix='sera-frozen-checks-') as temp:
        target = Path(temp)
        shutil.copytree(root / relative, target / relative,
                        ignore=shutil.ignore_patterns('__pycache__'))
        for script in SCRIPTS:
            command = [sys.executable, str(relative / script)]
            if script.endswith('review_fix_probes.py'):
                command += ['--module', str(relative / '阶段二/framework.py'),
                            '--output', str(target / 'review-fix-probes.json')]
            run = subprocess.run(command, cwd=target,
                                  capture_output=True, text=True)
            predicates_passed = True
            if script.endswith('review_fix_probes.py') and run.returncode == 0:
                predicates_passed = json.loads((target / 'review-fix-probes.json').read_text())['all_flips_as_expected']
            results.append(dict(script=str(relative / script), exit_code=run.returncode,
                                predicates_passed=predicates_passed,
                                stdout=run.stdout[-12000:], stderr=run.stderr[-4000:]))
    after = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in (root / relative).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    return dict(format=1, isolated_copy=True, archive_unchanged=before == after,
                passed=before == after and all(r['exit_code'] == 0 and r['predicates_passed'] for r in results), checks=results)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run_regressions()
    atomic_publish(args.output, result)
    print(json.dumps(dict(passed=result['passed'], archive_unchanged=result['archive_unchanged'])))
    raise SystemExit(0 if result['passed'] else 1)
