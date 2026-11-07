"""Reproduce two review findings using temporary, fictitious data only."""
from pathlib import Path
import contextlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / '阶段三-合法范围成本诊断'
sys.path.insert(0, str(SOURCE))
from scope_engine import Store, DirectoryIndex, ScopeEngine, Scope, Request, np


def completed_checkpoint():
    with tempfile.TemporaryDirectory(prefix='scope34-review-') as td:
        with contextlib.closing(Store(Path(td) / 'fixture.sqlite', 2, 'review-fixture')) as store:
            store.initialize([dict(id=1, vector=[1., 0.], path='fixture/a.txt',
                                   text='synthetic', version=1)], 1)
            snap = store.snapshot()
            engine = ScopeEngine(store, snap, 'review', 'full', DirectoryIndex(snap))
            req = Request(np.array([1., 0.]), scope=Scope('fixture/'), k=1,
                          use_cache=False, limits={'canonical_scores': 1,
                                                  'source_reads': 1, 'state_commits': 1})
            first = engine.run(req)
            signature = store.db.execute('SELECT id FROM executions').fetchone()[0]
            restored = store.restore(signature)
            saved_phase = restored.phase
            again = engine.run(req, restored)
            return dict(first_result=first.kind.value, first_items=len(first.items),
                        saved_phase=saved_phase, resume_result=again.kind.value,
                        resume_reason=again.reason, resume_items=len(again.items),
                        commits=again.resources['consumed']['state_commits'],
                        defect_observed=(first.kind.value == 'approximate'
                                         and saved_phase == 'commit'
                                         and again.kind.value == 'pending'
                                         and again.reason == 'state_commits'))


def scope_lower_boundary():
    spec = importlib.util.spec_from_file_location('review_selector', SOURCE / 'select_scope.py')
    selector = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(selector)
    with tempfile.TemporaryDirectory(prefix='scope34-selector-') as td:
        selector.PRIVATE = Path(td)
        frozen = Path(td) / 'plan-v1-stage1'
        frozen.mkdir()
        with contextlib.closing(sqlite3.connect(frozen / 'frozen.sqlite')) as db:
            db.executescript('CREATE TABLE docs(id INTEGER, visible INTEGER);'
                             'CREATE TABLE chunks(id INTEGER, path TEXT);')
            for ident in range(101):
                db.execute('INSERT INTO docs VALUES (?,1)', (ident,))
                prefix = 'small/' if ident < 10 else 'large/'
                db.execute('INSERT INTO chunks VALUES (?,?)', (ident, prefix + str(ident)))
            db.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            selector.main()
        result = json.loads((Path(td) / 'plan-v1-stage3-scope/scope-selection.json').read_text(encoding='utf-8'))
        n, total = result['eligible_count'], result['total_visible']
        return dict(total_visible=total, selected_members=n, selected_fraction=n / total,
                    declared_minimum=.1, defect_observed=n * 10 < total)


if __name__ == '__main__':
    print(json.dumps(dict(completed_checkpoint=completed_checkpoint(),
                          scope_lower_boundary=scope_lower_boundary()), indent=2))
