"""Explicit local CLI. No implicit private source access, downloads or API calls."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from .baselines import Baselines
from .benchmark import run_benchmark, worker
from .common import packed
from .runtime import atomic_publish
from .sources import export_source
from .store import FoundationStore, import_snapshot


def run_checks(output=None):
    import re
    from .common import digest
    result = subprocess.run([sys.executable, '-m', 'unittest',
        'research.reuse_foundation.test_foundation', '-v'],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True)
    sys.stderr.write(result.stderr)
    count = re.search(r'Ran (\d+) tests?', result.stderr)
    report = dict(format=1, synthetic=True, passed=result.returncode == 0,
        tests=int(count[1]) if count else None, python=sys.version.split()[0],
        code_sha256={p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')},
        command='python -m unittest research.reuse_foundation.test_foundation -v')
    if output:
        atomic_publish(output, report)
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('checks')
    check.add_argument('--output')
    export = commands.add_parser('export')
    export.add_argument('--kind', choices=['knowledge', 'memory'], required=True)
    export.add_argument('--source', required=True)
    export.add_argument('--output', required=True)
    imp = commands.add_parser('import')
    imp.add_argument('--input', required=True); imp.add_argument('--store', required=True)
    events = commands.add_parser('events')
    events.add_argument('--input', required=True); events.add_argument('--store', required=True)
    query = commands.add_parser('query')
    query.add_argument('--store', required=True); query.add_argument('--vector', required=True, help='JSON file containing a canonical query vector')
    query.add_argument('--scope', action='append', default=None)
    query.add_argument('--backend', choices=['exact', 'ann'], default='exact')
    query.add_argument('--k', type=int, default=10); query.add_argument('--window', type=int, default=256)
    query.add_argument('--snapshot'); query.add_argument('--historical', action='store_true')
    query.add_argument('--limits', help='JSON hard limits'); query.add_argument('--resume', help='committed signature')
    query.add_argument('--output', required=True)
    for name in ('benchmark', '_bench-worker'):
        bench = commands.add_parser(name)
        bench.add_argument('--count', type=int, default=20000)
        bench.add_argument('--dimension', type=int, default=1024)
        bench.add_argument('--repeats', type=int, default=3)
        if name == '_bench-worker': bench.add_argument('--arm', choices=['full', 'window', 'ann'], required=True)
        else: bench.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    if getattr(args, 'output', None):
        output_path = Path(args.output).resolve()
        for name in ('store', 'input', 'vector'):
            value = getattr(args, name, None)
            if value and output_path == Path(value).resolve():
                raise ValueError('output must not overwrite a database or input file')
    if args.command == 'checks':
        return run_checks(args.output)
    if args.command == '_bench-worker':
        print(packed(worker(args.arm, args.count, args.dimension, args.repeats)))
        return 0
    if args.command == 'benchmark':
        report = run_benchmark(args.count, args.dimension, args.repeats)
        atomic_publish(args.output, report)
        print(packed(dict(output=args.output, synthetic=True)))
        return 0
    if args.command == 'export':
        result = export_source(args.kind, args.source)
        output = Path(args.output).resolve()
        source = Path(args.source).resolve()
        if output == source or args.kind == 'knowledge' and output.is_relative_to(source):
            raise ValueError('export output must not overwrite source assets')
        atomic_publish(output, result)
        print(packed(dict(output=args.output, records=len(result['records']))))
        return 0
    store = FoundationStore(args.store)
    try:
        if args.command in ('import', 'events'):
            data = json.loads(Path(args.input).read_text(encoding='utf-8'))
            result = import_snapshot(data, store) if args.command == 'import' else dict(snapshot=store.apply_events(data).identity)
        else:
            baseline = Baselines(store)
            result = baseline.run(json.loads(Path(args.vector).read_text()), backend=args.backend,
                k=args.k, window=args.window, scopes=tuple(args.scope or ['global']), snapshot=args.snapshot,
                historical=args.historical, limits=json.loads(args.limits) if args.limits else None,
                state=baseline.restore(args.resume) if args.resume else None)
            atomic_publish(args.output, result)
            result = dict(output=args.output, kind=result['kind'], coverage=result['coverage'])
        print(packed(result))
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
