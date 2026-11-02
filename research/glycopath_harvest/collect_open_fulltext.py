#!/usr/bin/env python3
"""Auditable Europe PMC JATS acquisition; never fetch PDFs or invent measurements.

Public artifacts contain text ONLY when the JATS article explicitly carries CC BY,
CC BY-SA, or CC0. Attribution and license URLs accompany each deposited body.
These automated checks are not a substitute for human relevance/rights review.
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from defusedxml import ElementTree as ET

BASE = 'https://www.ebi.ac.uk/europepmc/webservices/rest'
QUERIES = [
    '(glycan OR glycosylation OR glycomic) AND (immune OR receptor OR lectin OR binding)',
    '(polysaccharide OR oligosaccharide) AND (immune OR inflammation OR macrophage OR antiviral)',
    '(glycan OR glycoside) AND (structure OR stereochemistry OR linkage OR branching)',
    '(glycosylation OR glycoprotein OR glycan) AND (signaling OR pathway OR immunology)',
    '(glycan OR polysaccharide) AND (adjuvant OR antitumor OR immunomodulatory)',
    '(glycan OR glycoconjugate) AND (function OR recognition OR specificity)',
]
FIELDS = ['pmcid', 'doi', 'pmid', 'title', 'authors', 'year', 'journal', 'url',
          'status', 'license_type', 'license_url', 'license', 'word_count',
          'sha256', 'saved_file', 'error']
# Full segment and version are required, preventing "by" from matching "by-nc".
CC_URL = re.compile(
    r'https?://(?:www\.)?creativecommons\.org/(?:licenses/(by(?:-nc)?(?:-nd|-sa)?)/(\d\.\d)|publicdomain/zero/(\d\.\d))/?',
    flags=re.IGNORECASE,
)
PUBLIC_LICENSES = {'by', 'by-sa', 'cc0'}


def node_text(element):
    return re.sub(r'\s+', ' ', ''.join(element.itertext())).strip()


def get(url, query=None):
    if query:
        url += '?' + urllib.parse.urlencode(query)
    req = urllib.request.Request(
        url, headers={'User-Agent': 'GlycoPath-Research-Harvester/2.0 (Europe PMC OA JATS)',
                      'Accept': 'application/json,application/xml'})
    with urllib.request.urlopen(req, timeout=50) as response:
        return response.read()


def parse_jats(blob, pmcid):
    if len(blob) > 25_000_000:
        raise ValueError('XML too large')
    root = ET.fromstring(blob)
    ids = [node_text(e) for e in root.iter()
           if e.tag.split('}')[-1] == 'article-id'
           and e.attrib.get('pub-id-type') in ('pmc', 'pmcid')]
    if pmcid.upper() not in {'PMC' + value.upper().removeprefix('PMC') for value in ids}:
        raise ValueError('PMCID mismatch')
    body = next((e for e in root.iter() if e.tag.split('}')[-1] == 'body'), None)
    if body is None:
        raise ValueError('Missing body')
    paragraphs = [node_text(e) for e in body.iter() if e.tag.split('}')[-1] == 'p']
    full = '\n\n'.join(para for para in paragraphs if para)
    if len(full.split()) < 300:
        raise ValueError('Too short')
    licenses = [e for e in root.iter() if e.tag.split('}')[-1] == 'license']
    raw_license = ' '.join(' '.join(e.attrib.values()) + ' ' + node_text(e)
                           for e in licenses)
    discovered = {}
    for match in CC_URL.finditer(raw_license):
        kind = match.group(1).lower() if match.group(1) else 'cc0'
        version = match.group(2) or match.group(3)
        canonical = ('https://creativecommons.org/licenses/' + kind + '/' + version + '/'
                     if kind != 'cc0' else
                     'https://creativecommons.org/publicdomain/zero/' + version + '/')
        discovered[(kind, version)] = canonical
    if len(discovered) != 1:
        return full, raw_license[:500], 'unclear', ''
    (kind, _), url = next(iter(discovered.items()))
    return full, raw_license[:500], kind, url


def save_records(out, records):
    with (out / 'records.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records.values())


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def acquire(args):
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    if args.save_text:
        (out / 'text').mkdir(exist_ok=True)
    log, records = [], {}
    for qi, query in enumerate(QUERIES):
        cursor = '*'
        for page in range(args.max_pages):
            try:
                ep_query = (f'({query}) AND OPEN_ACCESS:Y AND IN_PMC:Y '
                            f'AND FIRST_PDATE:[2000-01-01 TO {date.today().isoformat()}]')
                response = json.loads(get(BASE + '/search', {
                    'query': ep_query, 'format': 'json', 'pageSize': 100,
                    'resultType': 'lite', 'cursorMark': cursor}))
                batch = response.get('resultList', {}).get('result', [])
                for article in batch:
                    pmcid = str(article.get('pmcid') or '').upper()
                    if not re.fullmatch(r'PMC\d+', pmcid) or pmcid in records:
                        continue
                    records[pmcid] = {
                        'pmcid': pmcid, 'doi': article.get('doi') or '',
                        'pmid': article.get('id') or '',
                        'title': article.get('title') or '',
                        'authors': article.get('authorString') or '',
                        'year': article.get('pubYear') or '',
                        'journal': article.get('journalTitle') or '',
                        'url': 'https://europepmc.org/articles/' + pmcid,
                        'status': 'QUEUED', 'license_type': '', 'license_url': '',
                        'license': '', 'word_count': 0, 'sha256': '',
                        'saved_file': '', 'error': '',
                    }
                log.append({'query': qi, 'page': page, 'returned': len(batch),
                            'candidate_count': len(records)})
                next_cursor = response.get('nextCursorMark')
                if not batch or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                if len(records) >= args.max_candidates:
                    break
                time.sleep(args.sleep)
            except Exception as exc:
                log.append({'query': qi, 'page': page, 'error': str(exc)[:200]})
                break
        if len(records) >= args.max_candidates:
            break

    passed, processed = 0, 0
    used_doi, used_pmid, used_hash = set(), set(), set()
    for pmcid, record in records.items():
        if passed >= args.target:
            break
        processed += 1
        try:
            full, license_excerpt, license_type, license_url = parse_jats(
                get(BASE + '/' + pmcid + '/fullTextXML'), pmcid)
            record.update(license=license_excerpt, license_type=license_type,
                          license_url=license_url, word_count=len(full.split()),
                          sha256=hashlib.sha256(full.encode('utf-8')).hexdigest())
            if license_type not in PUBLIC_LICENSES:
                record['status'] = 'RESTRICTED_OR_UNCLEAR_LICENSE'
                continue
            doi, pmid, content_hash = record['doi'].strip().lower(), record['pmid'].strip(), record['sha256']
            if (doi and doi in used_doi) or (pmid and pmid in used_pmid) or content_hash in used_hash:
                record['status'] = 'DUPLICATE_IDENTIFIER_OR_TEXT'
                continue
            if args.save_text:
                rel = 'text/' + pmcid + '.txt'
                dest = out / rel
                temp = dest.with_suffix('.tmp')
                temp.write_text(full, encoding='utf-8')
                temp.replace(dest)
                if hashlib.sha256(dest.read_bytes()).hexdigest() != content_hash:
                    raise ValueError('Persisted text SHA-256 mismatch')
                record['saved_file'] = rel
                record['status'] = 'SAVED_PERMISSIVE_TEXT'
                passed += 1
            else:
                record['status'] = 'NOT_SAVED'
            if doi:
                used_doi.add(doi)
            if pmid:
                used_pmid.add(pmid)
            used_hash.add(content_hash)
        except Exception as exc:
            record['status'] = 'ERROR'
            record['error'] = str(exc)[:180]
        finally:
            if processed % 25 == 0:
                save_records(out, records)
                save_json(out / 'progress.json', {'processed': processed, 'saved': passed,
                                                   'target': args.target, 'final': False})
            time.sleep(args.sleep)
    save_records(out, records)
    accepted = [record for record in records.values() if record['status'] == 'SAVED_PERMISSIVE_TEXT']
    # Attribution: authors/title/source/DOI/CC license are all retained in records.csv.
    valid = len(accepted) == passed and len({r['pmcid'] for r in accepted}) == passed
    valid &= len({r['sha256'] for r in accepted}) == passed
    valid &= all((out / r['saved_file']).is_file() for r in accepted)
    status = 'PASS' if args.save_text and valid and passed >= args.target else 'BLOCKED'
    summary = {'target': args.target, 'metadata': len(records), 'processed': processed,
               'saved_permissive_fulltexts': passed, 'status': status,
               'license_policy': 'CC BY, CC BY-SA, CC0 only; URI within JATS license',
               'checks': 'PMCID, DOI/PMID/text dedup; >=300 words; saved-file SHA-256',
               'counts_by_status': {s: sum(r['status'] == s for r in records.values())
                                    for s in sorted({r['status'] for r in records.values()})},
               'downloaded_pdf': 0, 'gold_labels': 0,
               'independent_test_set': 'NOT_VERIFIED',
               'gpu_resources': 'NOT_VERIFIED', 'qwen_experiments': 'NOT_RUN',
               'human_relevance_review': 'NOT_DONE',
               'note': 'New independent harvested corpus; not the manuscript cohort. '
                       'Automated licensing is not legal review. No formal model metrics.'}
    save_json(out / 'summary.json', summary)
    save_json(out / 'retrieval_log.json', log)
    save_json(out / 'progress.json', {'processed': processed, 'saved': passed,
                                     'target': args.target, 'final': True, 'status': status})
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if status == 'PASS' else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', type=int, default=1134)
    parser.add_argument('--output', default='research/glycopath_harvest/results')
    parser.add_argument('--save-text', action='store_true')
    parser.add_argument('--max-candidates', type=int, default=6000)
    parser.add_argument('--max-pages', type=int, default=45)
    parser.add_argument('--sleep', type=float, default=0.2)
    args = parser.parse_args()
    if args.target < 1 or args.max_candidates < args.target or args.sleep < 0:
        parser.error('Invalid target, max-candidates, or sleep')
    return acquire(args)


if __name__ == '__main__':
    sys.exit(main())
