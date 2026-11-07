"""Four focused groups retaining the review defect predicates and positive controls."""
from scope_engine import *
import select_scope as selector
import tempfile,io
from contextlib import closing,redirect_stdout

def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def fixture(path):
    s=Store(path,2,'review-fixture')
    s.initialize([dict(id=1,vector=[1.,0.],path='fixture/a.txt',text='synthetic',version=1)],1)
    snap=s.snapshot()
    return s,snap,ScopeEngine(s,snap,'review','full',DirectoryIndex(snap))

def request(commits=1):
    return Request(np.array([1.,0.]),scope=Scope('fixture/'),k=1,use_cache=False,
        limits=dict(canonical_scores=1,source_reads=1,state_commits=commits))

def selector_fixture(total,small):
    with tempfile.TemporaryDirectory(prefix='scope-boundary-revision-') as td:
        selector.PRIVATE=Path(td);frozen=Path(td)/'plan-v1-stage1';frozen.mkdir()
        with closing(sqlite3.connect(frozen/'frozen.sqlite')) as db:
            db.executescript('CREATE TABLE docs(id INTEGER,visible INTEGER);CREATE TABLE chunks(id INTEGER,path TEXT);')
            for ident in range(total):
                db.execute('INSERT INTO docs VALUES(?,1)',(ident,))
                db.execute('INSERT INTO chunks VALUES(?,?)',(ident,('small/' if ident<small else 'large/')+str(ident)))
            db.commit()
        try:
            with redirect_stdout(io.StringIO()):selector.main()
        except ValueError as exc:
            assert 'no nontrivial eligible directory' in str(exc)
            return dict(total_visible=total,selected_members=None,selected_fraction=None,declared_minimum=.1,
                defect_observed=False,outcome='no_eligible_directory')
        value=json.loads((Path(td)/'plan-v1-stage3-scope/scope-selection.json').read_text(encoding='utf-8'))
        n=value['eligible_count']
        return dict(total_visible=total,selected_members=n,selected_fraction=n/total,declared_minimum=.1,
            defect_observed=10*n<total,outcome='selected')

def main():
    files=[HERE/'scope_engine.py',HERE/'select_scope.py',HERE/'verify_revision.py',HERE.parent/'阶段二/framework.py']
    frozen={str(p):sha(p.read_bytes()) for p in files};done=[];details={}
    with tempfile.TemporaryDirectory(prefix='scope-terminal-revision-') as td:
        path=Path(td)/'terminal.sqlite';s,snap,e=fixture(path)
        try:
            first=e.run(request());assert first.kind==ResultKind.APPROXIMATE and len(first.items)==1
            signature=s.db.execute('SELECT id FROM executions').fetchone()[0]
            assert s.restore(signature).phase=='done'
            counts=first.resources['consumed'].copy();s.close()
            with closing(Store(path,2,'review-fixture')) as reopened:
                ss=reopened.snapshot();new=ScopeEngine(reopened,ss,'review','full',DirectoryIndex(ss))
                restored=reopened.restore(signature);saved_phase=restored.phase
                again=new.run(request(),restored)
                assert again.kind==ResultKind.APPROXIMATE and again.items==first.items
                assert again.resources['consumed']==counts
                r1=dict(first_result=first.kind.value,first_items=len(first.items),saved_phase=saved_phase,
                    resume_result=again.kind.value,resume_reason=again.reason,resume_items=len(again.items),
                    commits=again.resources['consumed']['state_commits'],
                    defect_observed=(first.kind.value=='approximate' and saved_phase=='commit'
                        and again.kind.value=='pending' and again.reason=='state_commits'))
        finally:s.close()
        done.append('R1_durable_done_reopens_in_new_store_and_engine_without_repeating_any_paid_work')

        with closing(fixture(Path(td)/'budget.sqlite')[0]) as s:
            snap=s.snapshot();e=ScopeEngine(s,snap,'review','full',DirectoryIndex(snap))
            blocked=e.run(request(0))
            assert blocked.kind==ResultKind.PENDING and blocked.state.phase=='commit'
            assert s.db.execute('SELECT count(*) FROM executions').fetchone()[0]==0
            assert blocked.resources['consumed']['canonical_scores']==blocked.resources['consumed']['source_reads']==1
            assert blocked.resources['consumed'].get('state_commits',0)==0
            repeated=e.run(request(0),blocked.state)
            assert repeated.kind==ResultKind.PENDING and repeated.state.phase=='commit'
            assert repeated.resources['consumed']==blocked.resources['consumed']
            finished=e.run(request(1),repeated.state,budget_change_reason='fixture caller adds one completion commit')
            assert finished.kind==ResultKind.APPROXIMATE
            assert finished.resources['consumed']['canonical_scores']==finished.resources['consumed']['source_reads']==1
            assert finished.resources['consumed']['state_commits']==1
            assert s.restore(repeated.state.signature).phase=='done'
            details['commit_budget']=dict(blocked='pending/commit',persistent_records_before_addition=0,
                canonical_scores=1,source_reads=1,commits_after_addition=1)
        done.append('R1_zero_commit_budget_stays_pending_and_explicit_addition_saves_done_once')

        lock_path=Path(td)/'sqlite-lock.sqlite'
        s,snap,e=fixture(lock_path)
        with closing(s),closing(sqlite3.connect(lock_path,isolation_level=None)) as holder:
            s.db.execute('PRAGMA busy_timeout=0');holder.execute('BEGIN IMMEDIATE')
            try:
                blocked=e.run(request(1))
                assert blocked.kind==ResultKind.PENDING and blocked.state.phase=='commit'
                assert blocked.guarantee['save_failed'] and 'state save failed' in blocked.reason
                assert s.db.execute('SELECT count(*) FROM executions').fetchone()[0]==0
            finally:holder.execute('ROLLBACK')
            assert blocked.resources['consumed']['state_commits']==1
            again=e.run(request(1),blocked.state)
            assert again.kind==ResultKind.PENDING and again.reason=='state_commits'
            finished=e.run(request(2),again.state,budget_change_reason='fixture caller adds one retry after SQLite lock')
            assert finished.kind==ResultKind.APPROXIMATE
            assert finished.resources['consumed']['canonical_scores']==finished.resources['consumed']['source_reads']==1
            assert finished.resources['consumed']['state_commits']==2
            assert s.restore(again.state.signature).phase=='done'
            details['save_failure']=dict(kind='real SQLite write-lock error, no process crash',
                failed_state='pending/commit',failed_attempt_charged=True,terminal_row_on_failure=False,
                total_save_attempts_after_explicit_retry=2,successful_terminal_records=1)
        done.append('R1_real_SQLite_save_failure_never_fakes_done_and_retry_respects_parent_budget')

    r2=selector_fixture(101,10)
    assert not r2['defect_observed'] and r2['outcome']=='no_eligible_directory'
    positive=selector_fixture(100,10);assert positive['selected_members']==10
    below_ten=selector_fixture(40,4);assert below_ten['selected_members']==4
    assert selector.eligible_count(75,100) and not selector.eligible_count(76,100)
    assert not selector.eligible_count(10,101) and selector.eligible_count(11,101)
    assert not selector.eligible_count(1,0)
    details['selector_boundaries']=dict(exact_ten_percent=positive,legitimate_short_scope=below_ten,
        exactly_75_percent=True,above_75_percent_rejected=True,no_hidden_ten_member_floor=True)
    done.append('R2_original_101_10_case_rejected_exact_10_and_75_percent_and_short_scopes_preserved')
    before=json.loads((HERE/'probe-before.json').read_text(encoding='utf-8'))
    flips={key:dict(before=before[key]['defect_observed'],after=value['defect_observed'],expectedAfterFix=False)
        for key,value in [('completed_checkpoint',r1),('scope_lower_boundary',r2)]}
    assert all(v['before'] and not v['after'] for v in flips.values())
    assert frozen=={str(p):sha(p.read_bytes()) for p in files}
    write(HERE/'probe-after.json',dict(completed_checkpoint=r1,scope_lower_boundary=r2,flips=flips,allFlipsAsExpected=True,
        adaptation='same review defect predicates; R2 no-eligible ValueError is now the expected valid outcome'))
    write(HERE/'revision-checks.json',dict(date='2026-10-30',passed=len(done),checks=done,details=details,
        dependencies_before_and_after=frozen,real_matrix_rerun=False,scope='fictitious persistence and boundary checks only'))
    print(json.dumps(dict(passed=len(done),flips=flips,details=details),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
