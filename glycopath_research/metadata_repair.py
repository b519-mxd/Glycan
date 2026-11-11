"""Only verified, exact PMCID-to-PMID lookups; never infer IDs by digits."""
from __future__ import annotations
import json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode

def verify_pmcid_pmid(pmcid:str,timeout:float=12.0):
    if not (pmcid.startswith('PMC') and pmcid[3:].isdigit()):
        return {'status':'INVALID_PMCID','pmid':None}
    query=urlencode({'query':f'EXT_ID:{pmcid} AND SRC:PMC','format':'json','pageSize':'3'})
    url='https://www.ebi.ac.uk/europepmc/webservices/rest/search?'+query
    req=Request(url,headers={'User-Agent':'GlycoPath-metadata-validation/0.1'})
    with urlopen(req,timeout=timeout) as response:
        obj=json.load(response)
    matches=[row for row in obj.get('resultList',{}).get('result',[]) if row.get('pmcid','').upper()==pmcid.upper()]
    pmids={str(x['pmid']) for x in matches if str(x.get('pmid','')).isdigit()}
    if len(pmids)!=1:
        return {'status':'NO_UNIQUE_AUTHORITATIVE_PMID','pmid':None,'results':len(matches),'api':url}
    return {'status':'VERIFIED','pmid':pmids.pop(),'results':len(matches),'api':url}

def repair_manifest(manifest_path:str,output_path:str,sleep_s:float=.25):
    rows=[json.loads(line) for line in Path(manifest_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    unresolved=[]
    for row in rows:
        if row.get('pmid'):continue
        try:result=verify_pmcid_pmid(row['pmcid'])
        except Exception as error:result={'status':'API_FAILED','pmid':None,'error':type(error).__name__}
        row['pmid_verification']=result
        if result.get('pmid'):row['pmid']=result['pmid']
        else:unresolved.append(row['pmcid'])
        time.sleep(max(0,sleep_s))
    target=Path(output_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    return {'records':len(rows),'pmids_verified_by_api':sum(r.get('pmid_verification',{}).get('status')=='VERIFIED' for r in rows),
            'pmids_unresolved_after_attempt':len(unresolved),'unresolved_pmcids':unresolved,'output':str(target)}
