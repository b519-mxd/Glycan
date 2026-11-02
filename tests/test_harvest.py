"""Synthetic parser + gate tests. Fixtures are not study metrics."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('harvest',ROOT/'research/glycopath_harvest/collect_open_fulltext.py')
mod=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

def make_xml(license='https://creativecommons.org/licenses/by/4.0/',pmcid='PMC100'):
    return ('<!DOCTYPE article SYSTEM "journal.dtd"><article><front><article-meta><article-id pub-id-type="pmc">'+pmcid+'</article-id><permissions><license xmlns:xlink="http://www.w3.org/1999/xlink" xlink:href="'+license+'"/></permissions></article-meta></front><body><p>'+('glycan recognition evidence '*120)+'</p></body></article>').encode()

class HarvestTests(unittest.TestCase):
    def test_license_and_doctype(self):
        full,_,kind,url=mod.parse_jats(make_xml(),'PMC100')
        self.assertGreaterEqual(len(full.split()),300)
        self.assertEqual(kind,'by')
        self.assertTrue(url.endswith('/by/4.0/'))
        for bad in ['by-nc','by-nc-nd','by-nd']:
            _,_,kind,_=mod.parse_jats(make_xml('https://creativecommons.org/licenses/'+bad+'/4.0/'),'PMC100')
            self.assertNotIn(kind,mod.PUBLIC_LICENSES)
        _,_,kind,_=mod.parse_jats(make_xml('https://creativecommons.org/publicdomain/zero/1.0/'),'PMC100')
        self.assertEqual(kind,'cc0')
        with self.assertRaisesRegex(ValueError,'PMCID mismatch'):
            mod.parse_jats(make_xml(),'PMC999')
    def test_saved_gate_and_unsaved_block(self):
        def fake_get(url,query=None):
            if url.endswith('/search'):
                return json.dumps({'resultList':{'result':[{'pmcid':'PMC100','id':'100','doi':'10.1/x','title':'Glycan test'}]}}).encode()
            if url.endswith('/PMC100/fullTextXML'):
                return make_xml()
            raise AssertionError(url)
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(output=tmp+'/saved',target=1,save_text=True,max_pages=1,max_candidates=1,sleep=0)
            with patch.object(mod,'get',fake_get):
                self.assertEqual(mod.acquire(args),0)
                self.assertTrue(Path(tmp+'/saved/text/PMC100.txt').exists())
                self.assertTrue(json.loads(Path(tmp+'/saved/progress.json').read_text())['final'])
                args.save_text=False
                args.output=tmp+'/not_saved'
                self.assertEqual(mod.acquire(args),2)
                self.assertEqual(json.loads(Path(args.output+'/summary.json').read_text())['status'],'BLOCKED')

if __name__=='__main__':
    unittest.main()
