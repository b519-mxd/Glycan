"""Controlled software-property tests; not scientific model benchmarks."""
import unittest
from glycopath_research.quality_feedback import (KnowledgeState, AdaptiveCoordinator,
                                                  Gate, Patch, Route)


def scenario():
    s = KnowledgeState()
    s.put('e:g1', 'entity', {'structure_status': 'UNKNOWN', 'registry_id': None})
    s.put('e:p1', 'entity', {'structure_status': 'VERIFIED', 'registry_id': 'demo:protein'})
    s.put('r:1', 'relation', {'evidence_ids': ['demo:quote1'], 'source_id':'demo:paper1',
                            'context_status':'MATCH','polarity':1}, ('e:g1','e:p1'))
    # A path depends only on relation objects (not directly on entities).
    s.put('p:1', 'path', {'relation_ids':['r:1'], 'direction_status':'VERIFIED'}, ('r:1',))
    return s


def handlers():
    def resolve(obj, snap, gate):
        d = obj.payload.copy()
        if gate.code in ('STRUCTURE_UNRESOLVED','STRUCTURE_CONFLICT'):
            # This is a synthetic registered accession for software testing.
            d.update(structure_status='VERIFIED', registry_id='demo:glycan1')
        return Patch(obj.aid, d)
    def refresh(obj, snap, gate):
        return Patch(obj.aid, obj.payload.copy())
    return {'resolve':resolve,'refresh_relation':refresh,'refresh_path':refresh}


def routes():
    return {('entity','STRUCTURE_UNRESOLVED'):Route('resolve',2),
            ('entity','STRUCTURE_CONFLICT'):Route('resolve',2),
            ('relation','STALE_DEPENDENCY'):Route('refresh_relation',1),
            ('path','STALE_DEPENDENCY'):Route('refresh_path',1)}


class QualityFeedbackTest(unittest.TestCase):
    def test_dependency_gates_not_bypassable(self):
        s = scenario()
        self.assertEqual(s.gate('e:g1').code,'STRUCTURE_UNRESOLVED')
        self.assertEqual(s.gate('r:1').code,'UPSTREAM_NOT_PASS')
        self.assertEqual(s.gate('p:1').code,'UPSTREAM_NOT_PASS')

    def test_full_local_repair_and_audit(self):
        s = scenario()
        result = AdaptiveCoordinator(s, routes(), handlers(), budget=4).run()
        self.assertFalse(result['unresolved'])
        self.assertEqual(result['used_budget'],4)
        self.assertEqual([x['agent'] for x in result['audit_log']],
                         ['resolve','refresh_relation','refresh_path'])
        self.assertEqual(result['revisions'],{'e:g1':2,'e:p1':1,'p:1':2,'r:1':2})

    def test_budget_limit_blocks_downstream(self):
        s = scenario()
        result = AdaptiveCoordinator(s, routes(), handlers(), budget=2).run()
        self.assertTrue(result['budget_exhausted'])
        self.assertEqual(s.gate('e:g1').state,'PASS')
        self.assertEqual(s.gate('r:1').code,'STALE_DEPENDENCY')
        self.assertEqual(s.gate('p:1').code,'STALE_DEPENDENCY')

    def test_missing_handler_remains_unresolved(self):
        s = scenario()
        r = AdaptiveCoordinator(s, {}, {}, budget=5).run()
        self.assertEqual(r['used_budget'],0)
        self.assertTrue(r['unresolved'])

    def test_rejected_cross_artifact_patch(self):
        s=scenario()
        a={'wrong':lambda obj, snap, gate:Patch('e:p1', {'structure_status':'CONFLICT'})}
        r=AdaptiveCoordinator(s,{('entity','STRUCTURE_UNRESOLVED'):Route('wrong')},a,
                              budget=2).run()
        self.assertEqual(s.artifacts['e:p1'].payload['structure_status'],'VERIFIED')
        self.assertEqual(r['audit_log'][0]['result'],'REJECTED')

    def test_missing_provenance_does_not_pass(self):
        s=KnowledgeState()
        s.put('e:1','entity',{'structure_status':'VERIFIED','registry_id':'demo:1'})
        s.put('r:1','relation',{'evidence_ids':[],'source_id':'demo:paper',
                              'context_status':'MATCH','polarity':1},('e:1',))
        self.assertEqual(s.gate('r:1').code,'MISSING_PROVENANCE')

    def test_unknown_context_not_assumed_match(self):
        s=KnowledgeState()
        s.put('e:1','entity',{'structure_status':'VERIFIED','registry_id':'demo:1'})
        s.put('r:1','relation',{'evidence_ids':['demo:e'],'source_id':'demo:paper',
                              'context_status':'UNKNOWN','polarity':1},('e:1',))
        self.assertEqual(s.gate('r:1').code,'CONTEXT_UNRESOLVED')

    def test_known_conflict_blocks(self):
        s=KnowledgeState()
        s.put('e:1','entity',{'structure_status':'CONFLICT','registry_id':None})
        self.assertEqual(s.gate('e:1').state,'BLOCK')

    def test_fingerprint_stable_and_invalidation(self):
        s=scenario()
        fp=s.artifacts['e:p1'].fingerprint
        self.assertFalse(s.put('e:p1','entity',{'registry_id':'demo:protein','structure_status':'VERIFIED'}))
        self.assertEqual(s.artifacts['e:p1'].fingerprint,fp)
        s.put('e:p1','entity',{'registry_id':'demo:protein-v2','structure_status':'VERIFIED'})
        self.assertTrue(s.artifacts['r:1'].stale)
        self.assertTrue(s.artifacts['p:1'].stale)

    def test_forbid_parent_rewrites_and_unknown_agent(self):
        s=scenario()
        with self.assertRaises(ValueError):
            s.put('r:1','relation',{'x':1},('e:g1',))
        with self.assertRaises(ValueError):
            AdaptiveCoordinator(s,{('entity','STRUCTURE_UNRESOLVED'):Route('missing')},{})

    def test_no_fabricated_evidence_after_refresh(self):
        s=KnowledgeState()
        s.put('e:1','entity',{'structure_status':'UNKNOWN','registry_id':None})
        s.put('r:1','relation',{'evidence_ids':[],'source_id':'',
                              'context_status':'UNKNOWN','polarity':1},('e:1',))
        r=AdaptiveCoordinator(s,routes(),handlers(),budget=5).run()
        self.assertEqual(s.gate('r:1').code,'MISSING_PROVENANCE')
        self.assertTrue(r['unresolved'])

    def test_bounded_no_progress(self):
        s=scenario()
        a={'noop':lambda obj,snap,gate:None}
        r=AdaptiveCoordinator(s,{('entity','STRUCTURE_UNRESOLVED'):Route('noop')},a,
                              budget=10,max_attempts_per_issue=2).run()
        self.assertEqual(len(r['audit_log']),2)
        self.assertEqual(r['used_budget'],2)

    def test_no_change_does_not_invalidate(self):
        s=scenario()
        # Trigger replacing identical payload for an unstale artifact
        self.assertFalse(s.put('e:p1','entity',s.artifacts['e:p1'].payload))
        self.assertFalse(s.artifacts['r:1'].stale)

    def test_invalid_direction_rejected(self):
        s=KnowledgeState()
        s.put('e:1','entity',{'structure_status':'VERIFIED','registry_id':'demo:1'})
        s.put('r:1','relation',{'evidence_ids':['demo:e'],'source_id':'demo:p',
                              'context_status':'MATCH','polarity':1},('e:1',))
        s.put('p:1','path',{'relation_ids':['r:1'],'direction_status':'CONFLICT'},('r:1',))
        self.assertEqual(s.gate('p:1').code,'DIRECTION_CONFLICT')


if __name__=='__main__':unittest.main()
