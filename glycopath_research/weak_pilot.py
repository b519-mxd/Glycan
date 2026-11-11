"""Weak-label CPU pilot on real JATS text; NOT a trained GlycoPath-Qwen model.

Metrics compare with regex-generated proxy labels, not independently audited gold.
"""
from __future__ import annotations
import csv,io,json,random,re,zipfile
from pathlib import Path
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_fscore_support,accuracy_score
from sklearn.pipeline import make_pipeline
import joblib

LINKAGE = re.compile(r'(?:alpha|beta|α|β)[- ]?\s*[12]\s*[-–,]\s*[2346]|\([abαβ][12][-–][2346]\)',re.I)
SENTENCES = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])')

def examples(archive,per_class=1200):
    pools={0:[],1:[]}
    with zipfile.ZipFile(archive) as z:
        rows=list(csv.DictReader(io.StringIO(z.read('records.csv').decode('utf-8-sig'))))
        for r in rows:
            if r.get('status')!='SAVED_PERMISSIVE_TEXT':continue
            txt=z.read(r['saved_file']).decode('utf8',errors='replace')
            counts={0:0,1:0}
            for sentence in SENTENCES.split(txt):
                sentence=' '.join(sentence.split())
                if not 45<=len(sentence)<=500:continue
                y=int(bool(LINKAGE.search(sentence)))
                if y==0 and not re.search(r'\b(?:glycan|glycosyl|saccharide|linkage)\w*\b',sentence,re.I):continue
                if counts[y] >= (6 if y else 3):continue
                pools[y].append({'document':r['pmcid'],'text':sentence,'weak_label':y})
                counts[y]+=1
    random.Random(99).shuffle(pools[0]);random.Random(100).shuffle(pools[1])
    return pools[0][:per_class]+pools[1][:per_class]

def pilot(archive, output, seeds=(11,19,42)):
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    data=examples(archive);all_scores=[]
    for seed in seeds:
        docs=sorted({x['document'] for x in data});random.Random(seed).shuffle(docs)
        n=len(docs);tr=set(docs[:int(.7*n)]);va=set(docs[int(.7*n):int(.85*n)]);te=set(docs[int(.85*n):])
        assert not(tr&va or tr&te or va&te)
        train=[x for x in data if x['document'] in tr]
        test=[x for x in data if x['document'] in te]
        if set(x['weak_label'] for x in train)!={0,1}:raise RuntimeError('Missing training weak class')
        model=make_pipeline(TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=2,
                                            max_features=10000,sublinear_tf=True),
                            LogisticRegression(max_iter=200,class_weight='balanced',random_state=seed))
        model.fit([x['text'] for x in train],[x['weak_label'] for x in train])
        pred=list(map(int,model.predict([x['text'] for x in test])))
        truth=[x['weak_label'] for x in test]
        p,r,f,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
        all_scores.append({'seed':seed,'n_train':len(train),'n_test':len(test),
                           'weak_proxy_precision':float(p),'weak_proxy_recall':float(r),
                           'weak_proxy_f1':float(f),'weak_proxy_accuracy':float(accuracy_score(truth,pred))})
        joblib.dump(model,out/f'weak_model_seed{seed}.joblib')
        with (out/f'predictions_seed{seed}.jsonl').open('w') as fh:
            for x,y in zip(test,pred):
                fh.write(json.dumps({'document':x['document'],'weak_label':x['weak_label'],
                                     'prediction':y,'text':x['text']},ensure_ascii=False)+'\n')
    result={'status':'WEAK_LABEL_PILOT_ONLY','scientific_gold_metrics':'NOT_AVAILABLE',
            'n_examples':len(data),'class_counts':dict(Counter(str(x['weak_label']) for x in data)),
            'scores':all_scores}
    (out/'weak_pilot_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
