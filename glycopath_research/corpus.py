"""Re-audit archived 1134 JATS texts. This is NOT scientific model validation."""
import csv, io, hashlib, json, re, zipfile
from collections import Counter
from pathlib import Path

def audit_archive(path, output):
    dest=Path(output);dest.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path) as z:
        records=list(csv.DictReader(io.StringIO(z.read("records.csv").decode("utf-8-sig"))))
        saved=[r for r in records if r.get("status")=="SAVED_PERMISSIVE_TEXT"]
        names=set(z.namelist());issues=[];clean=[]
        pmcids=set();dois=set();digests=set();cnt=Counter()
        for r in saved:
            pmcid=r.get("pmcid","");doi=r.get("doi","").lower().strip()
            pmid=r.get("pmid","").strip();f=r.get("saved_file","")
            cnt["saved"]+=1
            if not re.fullmatch(r"PMC\d+",pmcid):issues.append({"pmcid":pmcid,"type":"INVALID_PMCID"})
            if pmcid in pmcids:issues.append({"pmcid":pmcid,"type":"DUP_PMCID"})
            pmcids.add(pmcid)
            if doi:
                if doi in dois:issues.append({"pmcid":pmcid,"type":"DUP_DOI"})
                dois.add(doi)
            else:cnt["missing_doi"]+=1
            if pmid==pmcid or (pmid.isdigit() and pmid==pmcid.removeprefix("PMC")):
                issues.append({"pmcid":pmcid,"type":"PMCID_IN_PMID"});pmid=""
                cnt["invalid_pmid"]+=1
            elif pmid and not pmid.isdigit():
                issues.append({"pmcid":pmcid,"type":"BAD_PMID"});pmid=""
                cnt["invalid_pmid"]+=1
            if r.get("license_type","").lower() not in {"by","by-sa","cc0","zero","cc-by","cc-by-sa"}:
                issues.append({"pmcid":pmcid,"type":"LICENSE_UNEXPECTED"})
            if f not in names:
                issues.append({"pmcid":pmcid,"type":"MISSING_FILE"});continue
            raw=z.read(f);sha=hashlib.sha256(raw).hexdigest()
            if sha!=r.get("sha256"):issues.append({"pmcid":pmcid,"type":"SHA_MISMATCH"})
            if sha in digests:issues.append({"pmcid":pmcid,"type":"DUP_SHA"})
            digests.add(sha)
            cnt["body_words"]+=len(raw.decode("utf8",errors="replace").split())
            if len(raw.split())<300:issues.append({"pmcid":pmcid,"type":"SHORT_BODY"})
            clean.append({"pmcid":pmcid,"pmid":pmid,"pmid_original":r.get("pmid",""),
                          "doi":doi,"license_type":r.get("license_type"),
                          "saved_file":f,"text_sha256":sha,"source":r.get("url")})
    cnt.update({"unique_pmcid":len(pmcids),"unique_doi":len(dois),"unique_sha":len(digests),
                "manifest_total":len(records)})
    hard={"INVALID_PMCID","DUP_PMCID","DUP_DOI","LICENSE_UNEXPECTED","MISSING_FILE","SHA_MISMATCH","DUP_SHA","SHORT_BODY"}
    result={"status":"FAIL" if any(x["type"] in hard for x in issues) else "PASS_WITH_METADATA_WARNINGS",
            "counts":dict(cnt),"errors":dict(Counter(x["type"] for x in issues)),
            "gold_standard":"NOT_AVAILABLE","model_metrics":"NOT_RUN",
            "scope":"file integrity and metadata only, not biological relevance or legal review"}
    (dest/"corpus_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
    (dest/"sanitized_manifest.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in clean))
    return result
