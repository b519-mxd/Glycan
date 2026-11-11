"""Batch PMCID-to-PMID repair via official NCBI PMC ID Converter.

Fail-closed: only exact matching PMCID with a numeric PMID is accepted.
An API outage never causes a synthesized or copied identifier.
"""
from __future__ import annotations
import json,os,re
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlencode

ROOT='https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/'

def fetch_verified_pmid_map(pmcids:list[str],timeout:float=35.0):
    if any(not re.fullmatch(r'PMC\d+',pmcid) for pmcid in pmcids):
        raise ValueError('INVALID_PMCID')
    if len(pmcids)>200:raise ValueError('NCBI_MAX_200')
    if not pmcids:return {},{'status':'NO_INPUT','request_count':0}
    params={'ids':','.join(sorted(set(pmcids))),'format':'json','tool':'GlycoPathResearch'}
    email=os.getenv('GLYCOPATH_CONTACT_EMAIL','')
    if email and '@' in email:params['email']=email
    request=Request(ROOT+'?'+urlencode(params),headers={'User-Agent':'GlycoPathResearch/0.2'})
    with urlopen(request,timeout=timeout) as response:data=json.load(response)
    if data.get('status')!='ok':raise RuntimeError('NCBI_ID_CONVERTER_NOT_OK')
    mapping={};ambiguous=set();requested=set(pmcids)
    for item in data.get('records',[]):
        pmcid=str(item.get('pmcid','')).upper();pmid=str(item.get('pmid',''))
        if pmcid not in requested or not pmid.isdigit():continue
        if pmcid in mapping and mapping[pmcid]!=pmid:ambiguous.add(pmcid)
        mapping[pmcid]=pmid
    for pmcid in ambiguous:mapping.pop(pmcid,None)
    return mapping,{'status':'AUTHORITATIVE_BATCH_RESPONSE','request_count':len(requested),
                    'verified_count':len(mapping),'ambiguous_pmcids':sorted(ambiguous),
                    'endpoint':ROOT,'source':'NCBI_PMC_ID_CONVERTER'}

def repair_manifest(manifest_path:str,output_path:str,sleep_s:float=0.0):
    rows=[json.loads(line) for line in Path(manifest_path).read_text(encoding='utf8').splitlines() if line.strip()]
    missing=sorted({row['pmcid'] for row in rows if not row.get('pmid')})
    mapping={};batch_logs=[]
    for start in range(0,len(missing),200):
        chunk=missing[start:start+200]
        try:
            found,log=fetch_verified_pmid_map(chunk)
            mapping.update(found);batch_logs.append(log)
        except Exception as error:
            batch_logs.append({'status':'API_FAILED','pmcids':chunk,'error_type':type(error).__name__})
    for row in rows:
        if row.get('pmid'):continue
        value=mapping.get(row['pmcid'])
        row['pmid_verification']={'status':'VERIFIED_NCBI' if value else 'UNRESOLVED',
                                 'source':'NCBI_PMC_ID_CONVERTER'}
        if value:row['pmid']=value
    target=Path(output_path);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf8')
    return {'records':len(rows),'previously_unresolved':len(missing),
            'pmids_verified_by_api':len(mapping),
            'pmids_unresolved_after_attempt':sum(not row.get('pmid') for row in rows),
            'batch_log':batch_logs,'output':str(target)}
