"""Invented fixtures verify review provenance and honest opportunity ceilings."""
import json
import tempfile
import unittest
from pathlib import Path

from research.reuse_foundation.common import digest
from .analyze import analyze,break_even


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        packets=[];labels=[]
        for f in range(16):
            queries=[f'invented question {f}/{v}' for v in range(3)]
            candidates=[dict(id=f*2+i,content_sha=digest(f'invented evidence {f}/{i}'),version=1) for i in range(2)]
            packets.append(dict(family=f,queries=queries,candidates=candidates))
            for v,q in enumerate(queries):
                labels.extend(dict(query_index=f*3+v,chunk_id=c['id'],query_sha256=digest(q),content_sha256=c['content_sha'],version=1,grade=1) for c in candidates)
        self.put('review-packet.json',dict(packets=packets))
        self.review=dict(packet_sha256=digest((self.root/'review-packet.json').read_bytes()),user_accepted=False,gold=False,judgment_pool_complete=False,judgments=labels)
        self.put('reviewed-labels.json',self.review)
        sec=dict(total=.002,prepare=.0008,ann_search=.0002,lexical_search=.0001,canonical_score=.0005,rank=.0002,source_fetch=.0001,state_commit=.0004)
        resource=dict(seconds=sec,consumed=dict(canonical_scores=10))
        rows=[dict(rep=rep,query=q,backend=b,resources=resource) for rep in range(3) for q in range(48) for b in ('full','ann','hybrid')]
        pairs=[dict(backend=b,query=q,miss=dict(cache_hit=False,ids=list(range(10)),resources=resource),hit=dict(cache_hit=True,ids=list(range(10)),resources=dict(seconds=sec,consumed=dict(source_reads=10,state_commits=1)))) for q in range(48) for b in ('full','ann','hybrid')]
        self.data=dict(measurements=rows,cache_pairs=pairs,natural_trace=False,matching=[dict(seconds=.0002)],warmup={b:dict(resources=resource) for b in ('full','ann','hybrid')})
        self.put('measurements.json',self.data);self.put('data-card.json',dict(protocol_sha='invented'))

    def tearDown(self):self.temp.cleanup()
    def put(self,name,value):(self.root/name).write_text(json.dumps(value))
    def run_audit(self):return analyze(*(self.root/name for name in ('measurements.json','data-card.json','review-packet.json','reviewed-labels.json')))

    def test_provisional_labels_never_turn_into_quality_metrics(self):
        r=self.run_audit();self.assertIsNone(r['semantic_review']['formal_ndcg_at_10']);self.assertIsNone(r['semantic_review']['answerability'])
        self.assertEqual(r['semantic_review']['judgments'],96);self.assertNotIn('invented question',json.dumps(r));self.assertNotIn('chunk_id',json.dumps(r))
    def test_hash_version_and_grade_binding(self):
        for key,value in [('content_sha256','bad'),('version',2),('query_sha256','bad'),('grade',3)]:
            original=self.review['judgments'][0][key];self.review['judgments'][0][key]=value;self.put('reviewed-labels.json',self.review)
            with self.assertRaises(ValueError):self.run_audit()
            self.review['judgments'][0][key]=original
    def test_missing_or_duplicate_judgments_fail(self):
        self.review['judgments'][-1]=self.review['judgments'][0];self.put('reviewed-labels.json',self.review)
        with self.assertRaises(ValueError):self.run_audit()
    def test_no_fabricated_accepted_gold(self):
        self.review['gold']=True;self.put('reviewed-labels.json',self.review)
        with self.assertRaises(ValueError):self.run_audit()
    def test_break_even_unknowns_and_impossibility_are_preserved(self):
        r=break_even(.2,.1);self.assertEqual(r['lookup_only_required_valid_hit_probability'],2)
        self.assertIsNone(r['actual_required_valid_hit_probability']);self.assertIsNone(r['measured_natural_valid_hit_probability'])
        self.assertIsNone(break_even(.1,0)['lookup_only_required_valid_hit_probability'])
        self.assertAlmostEqual(break_even(.1,1,fill=1,uses=10,maintenance=.1)['actual_required_valid_hit_probability'],.3)
    def test_overlap_and_ordinary_cache_source_checks_fail_closed(self):
        self.data['cache_pairs'][0]['hit']['resources']['consumed']['source_reads']=0;self.put('measurements.json',self.data)
        with self.assertRaises(ValueError):self.run_audit()
    def test_natural_trace_is_not_inferred_from_ordered_questions(self):
        r=self.run_audit();self.assertTrue(all(b['natural_hit_rate'] is None for b in r['backends']))
        self.data['natural_trace']=True;self.put('measurements.json',self.data)
        with self.assertRaises(ValueError):self.run_audit()


if __name__=='__main__':unittest.main()
