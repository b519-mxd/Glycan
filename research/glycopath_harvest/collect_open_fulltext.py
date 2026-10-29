#!/usr/bin/env python3
"""Real OA JATS collection. Metadata and checksums only by default; never PDF."""
import csv, json, re, time, hashlib, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from pathlib import Path
BASE="https://www.ebi.ac.uk/europepmc/webservices/rest"
QUERIES=[
 '(glycan OR glycosylation OR glycomic) AND (immune OR receptor OR lectin OR binding)',
 '(polysaccharide OR oligosaccharide) AND (immune OR inflammation OR macrophage OR antiviral)',
 '(glycan OR glycoside) AND (structure OR stereochemistry OR linkage OR branching)',
 '(glycosylation OR glycoprotein OR glycan) AND (signaling OR pathway OR immunology)',
 '(glycan OR polysaccharide) AND (adjuvant OR antitumor OR immunomodulatory)',
 '(glycan OR glycoconjugate) AND (function OR recognition OR specificity)'
]
def text(e): return re.sub(r'\s+',' ',''.join(e.itertext())).strip()
def get(url,query=None):
 if query:url+="?"+urllib.parse.urlencode(query)
 req=urllib.request.Request(url,headers={"User-Agent":"GlycoPath-Research-Harvester/1.0","Accept":"application/json,application/xml"})
 with urllib.request.urlopen(req,timeout=50) as r:return r.read()
def jats(blob,pmcid):
 if len(blob)>25000000 or re.search(br'<!DOCTYPE|<!ENTITY',blob,re.I):raise ValueError("Unsafe XML")
 root=ET.fromstring(blob)
 ids=[text(e) for e in root.iter() if e.tag.split('}')[-1]=='article-id' and e.attrib.get('pub-id-type') in ('pmc','pmcid')]
 if pmcid not in ['PMC'+str(x).upper().removeprefix('PMC') for x in ids]:raise ValueError("PMCID mismatch")
 body=next((e for e in root.iter() if e.tag.split('}')[-1]=='body'),None)
 if body is None:raise ValueError("Missing body")
 paragraphs=[text(e) for e in body.iter() if e.tag.split('}')[-1]=='p']
 full='\n\n'.join(p for p in paragraphs if p)
 if len(full.split())<300:raise ValueError("Too short")
 lic=' '.join(' '.join(e.attrib.values())+' '+text(e) for e in root.iter() if e.tag.split('}')[-1]=='license').lower()
 ok=bool(re.search(r'creativecommons.org/licenses/(by|by-sa|by-nc|by-nd|by-nc-sa|by-nc-nd)/|creativecommons.org/publicdomain/zero/',lic))
 return full,lic[:500],ok
def write(path,records):
 with open(path,'w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['pmcid','doi','pmid','title','year','journal','url','status','license','word_count','sha256','error']);w.writeheader();w.writerows(records.values())
def main():
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--target',type=int,default=1134);a.add_argument('--output',default='research/glycopath_harvest/results');a.add_argument('--save-text',action='store_true');args=a.parse_args()
 out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
 log=[]; records={}
 for qi,q in enumerate(QUERIES):
  cursor='*'
  for page in range(45):
   try:
    query=f'({q}) AND OPEN_ACCESS:Y AND IN_PMC:Y AND FIRST_PDATE:[2000-01-01 TO 2026-10-29]'
    j=json.loads(get(BASE+'/search',{'query':query,'format':'json','pageSize':100,'resultType':'lite','cursorMark':cursor}))
    batch=j.get('resultList',{}).get('result',[])
    for z in batch:
     p=str(z.get('pmcid','')).upper()
     if not p.startswith('PMC') or not p[3:].isdigit():continue
     if p not in records:records[p]={'pmcid':p,'doi':z.get('doi',''),'pmid':z.get('id',''),'title':z.get('title',''),'year':z.get('pubYear',''),'journal':z.get('journalTitle',''),'url':'https://europepmc.org/articles/'+p,'status':'QUEUED','license':'','word_count':0,'sha256':'','error':''}
    log.append({'query':qi,'page':page,'returned':len(batch),'candidate_count':len(records)})
    nxt=j.get('nextCursorMark')
    if not batch or not nxt or nxt==cursor:break
    cursor=nxt;time.sleep(0.2)
    if len(records)>=max(args.target*3,3500):break
   except Exception as e:log.append({'query':qi,'page':page,'error':str(e)});break
  if len(records)>=max(args.target*3,3500):break
 passed=0
 for i,(pmc,r) in enumerate(records.items()):
  if passed>=args.target:break
  try:
   full,lic,ok=jats(get(BASE+'/'+pmc+'/fullTextXML'),pmc)
   r['license']=lic;r['word_count']=len(full.split());r['sha256']=hashlib.sha256(full.encode()).hexdigest()
   r['status']='LICENSED_TEXT' if ok else 'LICENSE_UNCLEAR'
   if ok:
    passed+=1
    if args.save_text:
     dest=out/'text';dest.mkdir(exist_ok=True);(dest/(pmc+'.txt')).write_text(full,encoding='utf-8')
  except Exception as e:r['status']='ERROR';r['error']=str(e)[:180]
  if i%25==0:write(out/'records.csv',records);(out/'progress.json').write_text(json.dumps({'processed':i+1,'licensed':passed,'target':args.target}))
  time.sleep(0.2)
 write(out/'records.csv',records)
 summary={'target':args.target,'metadata':len(records),'licensed_fulltexts':passed,'status':'PASS' if passed>=args.target else 'BLOCKED','downloaded_pdf':0,'gold_labels':0,'qwen_experiments':'NOT_RUN','note':'Not original GlycoPath cohort; requires expert review and independent model evaluation.'}
 (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'retrieval_log.json').write_text(json.dumps(log,indent=2))
 print(json.dumps(summary));return 0 if passed>=args.target else 2
if __name__=='__main__':
 import sys;sys.exit(main())
