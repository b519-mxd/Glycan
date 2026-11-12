"""Registry-reference identity collision audit; accession inequality is not chemical nonidentity."""
import csv,json,hashlib,random,collections,re,itertools,sys
from pathlib import Path
from glycopath_research.structure_graph import parse_glycan,ParseError
O=Path('registry_output');O.mkdir(exist_ok=True)
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False))
p=Path('cosmos/glycans.csv');rng=random.Random(2026)
sample=[];total=0;parse_count=0;eligible=0;fail=collections.Counter()
with p.open(encoding='utf-8-sig',newline='') as f:
    r=csv.DictReader(f);headers=r.fieldnames
    acc=next(k for k in headers if ('accession' in k.lower() or 'glytoucan' in k.lower()) and 'subsum' not in k.lower())
    iup=next(k for k in headers if 'iupac' in k.lower())
    wur=next(k for k in headers if 'wurcs' in k.lower())
    for row in r:
        total+=1
        a=(row.get(acc) or '').strip();x=(row.get(iup) or '').strip();w=(row.get(wur) or '').strip()
        if not re.fullmatch(r'G[0-9]{5}[A-Z]{2}',a) or not x or not w.startswith('WURCS'):continue
        eligible+=1
        try:g=parse_glycan(x)
        except ParseError as e:fail[str(e).split('_AT_')[0]]+=1;continue
        if not g.full_linkages:continue
        parse_count+=1
        v={'accession':a,'iupac':x,'wurcs':w,'composition':sorted(g.residues),'signature':g.signature}
        if len(sample)<2500:sample.append(v)
        else:
            j=rng.randrange(parse_count)
            if j<2500:sample[j]=v
    print('headers',headers,'rows',total,'eligible',eligible,'full supported',parse_count,flush=True)
assert len(sample)>=50
# Different accessions used as registry-level reference labels, not guaranteed chemically distinct.
groups=collections.defaultdict(list)
for v in sample:groups[tuple(v['composition'])].append(v)
pairs=[];seen=0
for group in groups.values():
    for a,b in itertools.combinations(group,2):
        if a['accession']==b['accession']:continue
        seen+=1
        d={'a':a['accession'],'b':b['accession'],'iupac_a':a['iupac'],'iupac_b':b['iupac'],'same_iupac':a['iupac']==b['iupac'],'same_graph':a['signature']==b['signature'],'same_wurcs':a['wurcs']==b['wurcs']}
        if len(pairs)<5000:pairs.append(d)
        else:
            j=rng.randrange(seen)
            if j<5000:pairs[j]=d
assert pairs
# A high-score match to multiple accessions must abstain; test on the frozen reference sample.
index=collections.defaultdict(set)
for a in sample:index[a['signature']].add(a['accession'])
amb=[v for v in sample if len(index[v['signature']])>1]
m={'source':'https://download.glycosmos.org/glycosmos_glycans_list.csv','sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'headers':headers,'rows':total,'eligible_iupac_wurcs':eligible,'fully_supported_linkage_count':parse_count,'sample_size':len(sample),'unique_accessions':len({v['accession'] for v in sample}),'different_accession_same_composition_pairs_total':seen,'evaluated_pairs':len(pairs),'composition_baseline_registry_merges':len(pairs),'exact_iupac_registry_collisions':sum(p['same_iupac'] for p in pairs),'supported_graph_registry_collisions':sum(p['same_graph'] for p in pairs),'same_wurcs_different_accessions':sum(p['same_wurcs'] for p in pairs),'ambiguous_sample_rows':len(amb),'parse_failures':dict(fail),'scope':'registry accession distinction, not complete chemical identity; random sample; no natural mention linking gold'}
dump('registry_records.json',sample);dump('registry_pairs.json',pairs);dump('metrics.json',m);print(json.dumps(m,indent=2))
