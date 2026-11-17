"""Strict real-reference adapters for the deterministic quality-feedback coordinator.
GlyCosmos accession lookup is scoped to fully supported IUPAC tree signatures.
Curated lectin DOIs are *bibliographic sources*, not independent experiments.
Neither creates or validates a biological glycan-function hypothesis.
"""
from collections import defaultdict
from copy import deepcopy
from glycopath_research.structure_graph import parse_glycan, ParseError
from glycopath_research.quality_feedback import (
    Artifact, Patch, Route, KnowledgeState, AdaptiveCoordinator)


class RegistryReference:
    def __init__(self, records):
        self.index = defaultdict(set)
        self.accession_to_record = {}
        for rec in records:
            try:
                g = parse_glycan(rec['iupac'])
            except ParseError:
                continue
            if not g.full_linkages:
                continue
            if rec.get('signature') != g.signature:
                raise ValueError('REFERENCE_SIGNATURE_MISMATCH:'+rec['accession'])
            self.index[g.signature].add(rec['accession'])
            self.accession_to_record[rec['accession']] = deepcopy(rec)
        self.accepted_count = len(self.accession_to_record)

    def identify(self, structure):
        try:
            g = parse_glycan(structure)
        except ParseError as e:
            return {'status':'UNKNOWN','registry_id':None,
                    'reason':'UNSUPPORTED_SYNTAX','detail':str(e)}
        if not g.full_linkages:
            return {'status':'UNKNOWN','registry_id':None,
                    'reason':'INCOMPLETE_LINKAGE'}
        matches = sorted(self.index.get(g.signature, ()))
        if len(matches) != 1:
            return {'status':'UNKNOWN','registry_id':None,
                    'reason':'NO_REFERENCE_MATCH' if not matches else 'AMBIGUOUS_ACCESSION',
                    'candidate_count':len(matches)}
        return {'status':'VERIFIED','registry_id':matches[0],
                'signature':g.signature,'reason':'UNIQUE_SUPPORTED_SIGNATURE_MATCH',
                'scope':'registry accession in restricted parser subset'}


class CuratedLectinReference:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
    def lookup(self, index, head, tail):
        if not isinstance(index,int) or index < 0 or index >= len(self.rows):
            return None
        row = self.rows[index]
        return deepcopy(row) if (row['head'],row['tail']) == (head,tail) else None


def registry_resolver(registry):
    def action(obj, snapshot, gate):
        if obj.kind != 'entity':
            return None
        d = deepcopy(obj.payload)
        v = registry.identify(d.get('raw_iupac',''))
        d.update(structure_status=v['status'],registry_id=v.get('registry_id'),
                 lookup_reason=v['reason'])
        if 'signature' in v:
            d['supported_signature']=v['signature']
        else:
            d.pop('supported_signature',None)
        return Patch(obj.aid,d)
    return action


def registry_assertion_refresh(obj,snapshot,gate):
    """Administrative registry citation, not a glycan biological edge."""
    if obj.kind != 'relation' or len(obj.parents) != 1:
        return None
    ent = snapshot[obj.parents[0]]
    if ent.kind != 'entity' or ent.payload.get('structure_status') != 'VERIFIED':
        return None
    accession = ent.payload['registry_id']
    d = deepcopy(obj.payload)
    d.update(evidence_ids=['GlyCosmos:accession:'+accession],
             source_id='GlyCosmos:registry-snapshot',
             context_status='MATCH',polarity=0,subject_accession=accession,
             evidence_kind='registry_annotation_not_biological_relation')
    return Patch(obj.aid,d)


def technical_trace_refresh(obj,snapshot,gate):
    """A dependency trace for control testing, NOT a functional hypothesis."""
    if obj.kind != 'path' or not obj.parents:
        return None
    if any(not snapshot[r].payload.get('evidence_ids') for r in obj.parents):
        return None
    d=deepcopy(obj.payload)
    d.update(relation_ids=list(obj.parents),direction_status='VERIFIED',
             path_kind='registry_dependency_trace_not_functional_hypothesis')
    return Patch(obj.aid,d)


def curated_provenance_resolver(reference):
    def action(obj,snapshot,gate):
        if obj.kind != 'relation' or obj.parents:
            return None
        d=deepcopy(obj.payload)
        row=reference.lookup(d.get('source_row_index'),d.get('head'),d.get('tail'))
        if row is None or not str(row['source']).startswith('https://doi.org/'):
            return None
        q=d.get('query_species')
        status='MATCH' if q and q == row.get('species') else (
               'CONFLICT' if q and row.get('species') else 'UNKNOWN')
        d.update(evidence_ids=['curated_lectin:record:'+str(d['source_row_index'])],
                 source_id=row['source'],context_status=status,
                 polarity=-1 if row['kind']=='negative' else 1,
                 evidence_kind='curated_motif_specificity_not_independent_study',
                 bibliographic_source=row['source'])
        return Patch(obj.aid,d)
    return action


def routes_and_agents(registry, lectins=None):
    routes={
        ('entity','STRUCTURE_UNRESOLVED'):Route('registry_resolve',1),
        ('relation','STALE_DEPENDENCY'):Route('relation_refresh',1),
        ('relation','MISSING_PROVENANCE'):Route('relation_refresh',1),
        ('relation','CONTEXT_UNRESOLVED'):Route('relation_refresh',1),
        ('path','STALE_DEPENDENCY'):Route('trace_refresh',1),
        ('path','PATH_UNRESOLVED'):Route('trace_refresh',1),
    }
    curated = curated_provenance_resolver(lectins) if lectins is not None else None
    def relation_action(obj,snapshot,gate):
        return registry_assertion_refresh(obj,snapshot,gate) if obj.parents else (
            curated(obj,snapshot,gate) if curated is not None else None)
    agents={'registry_resolve':registry_resolver(registry),
            'relation_refresh':relation_action,
            'trace_refresh':technical_trace_refresh}
    return routes,agents


def build_registry_state(rows):
    s=KnowledgeState()
    for i,r in enumerate(rows):
        eid=f'entity:{i:04d}';rid=f'assertion:{i:04d}';tid=f'trace:{i:04d}'
        s.put(eid,'entity',{'raw_iupac':r['iupac'],
              'structure_status':'UNKNOWN','registry_id':None})
        s.put(rid,'relation',{'evidence_ids':[],'source_id':'',
              'context_status':'UNKNOWN','polarity':0,
              'evidence_kind':'registry_annotation_not_biological_relation'},(eid,))
        s.put(tid,'path',{'relation_ids':[rid],'direction_status':'UNKNOWN',
              'path_kind':'registry_dependency_trace_not_functional_hypothesis'},(rid,))
    return s


def build_curated_state(rows, indices):
    s=KnowledgeState()
    for i in indices:
        r=rows[i]
        s.put(f'curated:{i:04d}','relation',{'head':r['head'],'tail':r['tail'],
              'source_row_index':i,'query_species':r.get('species'),
              'evidence_ids':[],'source_id':'','context_status':'UNKNOWN',
              'polarity':None,
              'evidence_kind':'curated_motif_specificity_not_independent_study'})
    return s


def run_feedback(state,registry,lectins=None,budget=100000):
    routes,agents=routes_and_agents(registry,lectins)
    return AdaptiveCoordinator(state,routes,agents,budget=budget,
                               max_attempts_per_issue=1).run()
