"""Publicly curated supplementary glycan structure and measured-binding benchmarks.

Pinned source: BojarLab/glycowork v1.11.0, MIT license.
Results are NOT expert-reviewed text NER/RE or biological pathway validation.
"""
from __future__ import annotations
import csv,hashlib,json,re
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from sklearn.feature_extraction import FeatureHasher
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from glycopath_research.structure_graph import parse_glycan,ParseError

SOURCE='https://github.com/BojarLab/glycowork/tree/v1.11.0/glycowork/glycan_data'

def audit_motifs(csv_path,output_dir):
    with open(csv_path,encoding='utf8') as handle: rows=list(csv.DictReader(handle))
    parsed=[];fail=Counter()
    for row in rows:
        try:g=parse_glycan((row.get('motif') or '').strip())
        except ParseError as error:
            fail[str(error).split('_AT_')[0]]+=1;continue
        parsed.append({'name':row['motif_name'],'signature':g.signature,
                       'full_linkages':g.full_linkages,'residues':sorted(g.residues)})
    collisions=[]
    for i,a in enumerate(parsed):
        for b in parsed[i+1:]:
            if a['residues']==b['residues'] and a['signature']!=b['signature']:
                collisions.append({'left':a['name'],'right':b['name']})
    result={'benchmark':'CURATED_MOTIF_STRUCTURE_COVERAGE_PROXY','source':SOURCE,
        'source_rows':len(rows),'parsed':len(parsed),
        'parse_coverage':len(parsed)/len(rows) if rows else 0,
        'full_linkage_parsed':sum(x['full_linkages'] for x in parsed),
        'same_composition_different_graph_pairs':len(collisions),
        'unparsed_reasons':dict(fail),
        'interpretation':'This tests partial notation support; no expert entity alignment gold.'}
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    (out/'motif_structure_audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    (out/'motif_collision_examples.json').write_text(json.dumps(collisions[:40],indent=2),encoding='utf8')
    return result

def features(protein,glycan,mode):
    result={}
    if mode!='glycan_only': result['protein='+protein]=1
    if mode!='protein_only':
        for width in (3,4,5):
            for i in range(len(glycan)-width+1):
                key='glycan'+str(width)+':'+glycan[i:i+width]
                result[key]=result.get(key,0)+1
    return result

def binding_regression(csv_path,output_dir,seeds=(11,19,42),max_pairs=18000):
    df=pd.read_csv(csv_path,low_memory=False)
    if df.shape[1]<3:raise ValueError('Expected protein by glycan Z-score matrix')
    protein_key=df.columns[0]
    cols=[c for c in df.columns[1:] if re.search(r'\([abαβ][1-9][0-9]*-[1-9][0-9]*\)',str(c))]
    if len(cols)<20:raise ValueError('Not enough glycan-structure columns: '+str(len(cols)))
    nums=df[cols].apply(pd.to_numeric,errors='coerce')
    selected=nums.notna().sum().sort_values(ascending=False).head(500).index.tolist()
    rows=nums[selected].notna().sum(axis=1).sort_values(ascending=False).head(200).index
    sub=nums.loc[rows,selected]
    if pd.__version__.startswith('1.'):
        stacked=sub.stack(dropna=True)
    else:
        stacked=sub.stack(future_stack=True).dropna()
    examples=[]
    for (ix,col),val in stacked.items():
        if np.isfinite(val):examples.append((str(df.loc[ix,protein_key]),str(col),float(val)))
    rng=np.random.default_rng(179)
    if len(examples)>max_pairs:
        ids=sorted(rng.choice(len(examples),max_pairs,replace=False))
        examples=[examples[i] for i in ids]
    if len(examples)<500 or len({e[1] for e in examples})<30:
        raise ValueError('Too few response measurements for held-out glycan benchmark')
    result_rows=[]
    for seed in seeds:
        glycans=sorted({e[1] for e in examples})
        rng=np.random.default_rng(seed);rng.shuffle(glycans)
        n=int(len(glycans)*.8);train_g=set(glycans[:n]);test_g=set(glycans[n:])
        train=[e for e in examples if e[1] in train_g]
        test=[e for e in examples if e[1] in test_g]
        if len(test)<50:raise ValueError('Not enough held-out measurements')
        ytr=np.array([e[2] for e in train]);yte=np.array([e[2] for e in test])
        global_mean=float(ytr.mean()); protein_means={}
        for p in {e[0] for e in train}:
            protein_means[p]=float(np.mean([e[2] for e in train if e[0]==p]))
        predictions={'protein_mean_baseline':np.array([protein_means.get(e[0],global_mean) for e in test])}
        for mode in ('protein_only','glycan_only','combined'):
            hasher=FeatureHasher(n_features=2**15,input_type='dict',alternate_sign=False)
            xx=hasher.transform([features(p,g,mode) for p,g,_ in train])
            xt=hasher.transform([features(p,g,mode) for p,g,_ in test])
            model=Ridge(alpha=30,solver='lsqr')
            model.fit(xx,ytr); predictions[mode]=model.predict(xt)
        for mode,pred in predictions.items():
            grouped={}
            for i,(p,g,y) in enumerate(test):
                grouped.setdefault(g,[]).append((float(pred[i]),float(y)))
            eligible=0;hits={1:0,3:0,10:0}
            for group in grouped.values():
                if not any(y>=1.5 for _,y in group):continue
                eligible+=1
                ordered=sorted(group,key=lambda x:-x[0])
                for k in hits:
                    hits[k]+=int(any(y>=1.5 for _,y in ordered[:k]))
            result_rows.append({'seed':seed,'model':mode,'train_pairs':len(train),'test_pairs':len(test),
                'train_glycans':len(train_g),'test_glycans':len(test_g),
                'mae':float(mean_absolute_error(yte,pred)),
                'rmse':float(np.sqrt(mean_squared_error(yte,pred))),
                'r2':float(r2_score(yte,pred)),
                'high_z_proxy_queries':eligible,
                'high_z_proxy_hits1':hits[1]/eligible if eligible else None,
                'high_z_proxy_hits3':hits[3]/eligible if eligible else None,
                'high_z_proxy_hits10':hits[10]/eligible if eligible else None})
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    result={'benchmark':'CURATED_MEASURED_ZSCORE_REGRESSION','source':SOURCE,
       'raw_shape':list(df.shape),'measured_pairs_used':len(examples),
       'unique_glycans':len({e[1] for e in examples}),
       'unique_proteins':len({e[0] for e in examples}),
       'target':'Continuous assay Z-score; no binary binding gold',
       'split':'Sequence-disjoint glycan 80/20 by seed; never pair random split',
       'high_z_proxy_definition':'Z>=1.5 is operational high-assay-response, NOT biological binding gold',
       'models':result_rows,
       'not_claimed':'Not NER/RE F1, not calibrated evidence probability, not IRRL multihop biological mechanism.'}
    (out/'glycowork_binding_regression.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    with (out/'glycowork_binding_metrics.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(result_rows[0]))
        writer.writeheader();writer.writerows(result_rows)
    return result

def source_hashes(motif,binding,output):
    result={'source':SOURCE,'files':{}}
    for p in [motif,binding]:
        f=Path(p)
        result['files'][f.name]={'bytes':f.stat().st_size,
            'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
    (Path(output)/'source_hashes.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--motifs',required=True);p.add_argument('--binding',required=True);p.add_argument('--output',required=True)
    args=p.parse_args()
    output={'structure':audit_motifs(args.motifs,args.output),
        'binding':binding_regression(args.binding,args.output),
        'source_hashes':source_hashes(args.motifs,args.binding,args.output)}
    print(json.dumps(output,indent=2))
