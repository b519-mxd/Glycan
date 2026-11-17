"""Smoke tests use small, genuinely sourced records; not scientific accuracy claims."""
import unittest
from glycopath_research.real_reference_adapter import (
    RegistryReference,CuratedLectinReference,build_registry_state,
    build_curated_state,run_feedback)


REGISTRY=[
 {'accession':'G44522YF','iupac':'Glc(b1-3)All','signature':'All[b1-3:Glc]',
  'composition':['All','Glc']},
 {'accession':'G95126JK','iupac':'Glc(a1-3)All','signature':'All[a1-3:Glc]',
  'composition':['All','Glc']}
]
LECTIN=[
 {'head':'lectin:AAA','tail':'motif:Fuc(a1-2)','kind':'primary',
  'source':'https://doi.org/10.1007/BF00731446','species':'Anguilla anguilla'},
 {'head':'lectin:AAL','tail':'motif:GalNAc(a1-3)[Fuc(a1-2)]Gal','kind':'negative',
  'source':'https://doi.org/10.1021/acschembio.1c00689','species':'Aleuria aurantia'},
 {'head':'lectin:MNA-G,MNA G','tail':'motif:Gal(a1-3)','kind':'primary',
  'source':'unknown','species':'Morus nigra'}
]


class RealReferenceSmoke(unittest.TestCase):
    def setUp(self):
        self.r=RegistryReference(REGISTRY)
        self.e=CuratedLectinReference(LECTIN)

    def test_same_composition_distinct_accessions(self):
        x=[self.r.identify(v['iupac']) for v in REGISTRY]
        self.assertEqual([v['status'] for v in x],['VERIFIED','VERIFIED'])
        self.assertNotEqual(x[0]['registry_id'],x[1]['registry_id'])

    def test_incremental_refresh_matches_full_rerun(self):
        s=build_registry_state([REGISTRY[0],REGISTRY[1]])
        run_feedback(s,self.r,self.e,budget=6)
        self.assertEqual(s.gate('trace:0000').state,'PASS')
        p=s.artifacts['entity:0000'].payload.copy()
        p.update(raw_iupac=REGISTRY[1]['iupac'],
                 structure_status='UNKNOWN',registry_id=None)
        s.put('entity:0000','entity',p)
        self.assertEqual(s.gate('assertion:0000').code,'STALE_DEPENDENCY')
        report=run_feedback(s,self.r,self.e,budget=3)
        self.assertEqual(report['used_budget'],3)
        self.assertEqual(s.artifacts['assertion:0000'].payload['subject_accession'],
                         'G95126JK')
        self.assertEqual(s.gate('trace:0000').state,'PASS')
        fresh=build_registry_state([REGISTRY[1],REGISTRY[1]])
        rerun=run_feedback(fresh,self.r,self.e,budget=6)
        self.assertEqual(rerun['used_budget'],6)
        self.assertEqual(fresh.artifacts['assertion:0000'].payload['subject_accession'],
                         'G95126JK')

    def test_unknown_bibliography_abstains(self):
        s=build_curated_state(LECTIN,[2])
        run_feedback(s,self.r,self.e,budget=1)
        self.assertEqual(s.gate('curated:0002').code,'MISSING_PROVENANCE')

    def test_negative_polarity_preserved(self):
        s=build_curated_state(LECTIN,[1])
        run_feedback(s,self.r,self.e,budget=1)
        self.assertEqual(s.artifacts['curated:0001'].payload['polarity'],-1)

    def test_species_mismatch_is_blocked(self):
        s=build_curated_state(LECTIN,[0])
        p=s.artifacts['curated:0000'].payload.copy()
        p['query_species']='different_species'
        s.put('curated:0000','relation',p)
        run_feedback(s,self.r,self.e,budget=1)
        self.assertEqual(s.gate('curated:0000').code,'CONTEXT_CONFLICT')

    def test_registry_trace_not_functional_hypothesis(self):
        s=build_registry_state([REGISTRY[0]])
        run_feedback(s,self.r,self.e,budget=3)
        self.assertIn('not_functional_hypothesis',
            s.artifacts['trace:0000'].payload['path_kind'])


if __name__=='__main__':unittest.main()
