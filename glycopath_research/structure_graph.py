"""Restricted, fail-closed IUPAC-like branched glycan parser (NOT full IUPAC/WURCS)."""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
import re
LEX=re.compile(r'([A-Z][A-Za-z0-9]*)(?:\(([abαβ?])([1-9?][0-9]*)-([1-9?][0-9]*)\))?|([\[\]])')

class ParseError(ValueError):
    pass

@dataclass(frozen=True)
class ParsedGlycan:
    source: str
    residues: tuple[str,...]
    edges: tuple[tuple[int,int,str|None,int|None,int|None],...]
    root: int
    full_linkages: bool
    signature: str

def parse_glycan(text:str)->ParsedGlycan:
    s=re.sub(r'\s+','',text.strip())
    if not s: raise ParseError('EMPTY')
    tokens=[];position=0
    for m in LEX.finditer(s):
        if m.start()!=position: raise ParseError(f'UNSUPPORTED_SYNTAX_AT_{position}')
        position=m.end()
        tokens.append((m.group(5),) if m.group(5) else m.groups()[:4])
    if position!=len(s): raise ParseError('UNSUPPORTED_SYNTAX')
    if not tokens or len(tokens[-1])!=4 or tokens[-1][1] is not None:
        raise ParseError('MALFORMED_REDUCING_END')
    residues=[];edges=[];current=None;branches=[];root=None
    for tok in reversed(tokens):
        if tok==(']',):
            if current is None: raise ParseError('BRANCH_WITHOUT_PARENT')
            branches.append(current);continue
        if tok==('[',):
            if not branches:raise ParseError('UNMATCHED_BRANCH_START')
            current=branches.pop();continue
        name,ano,dp,ap=tok;index=len(residues);residues.append(name)
        if current is None:root=index
        else:
            if ano is None:raise ParseError('MISSING_LINKAGE')
            ano={'α':'a','β':'b','?':None}.get(ano,ano)
            edges.append((index,current,ano,int(dp) if dp and dp.isdigit() else None,
                          int(ap) if ap and ap.isdigit() else None))
        current=index
    if branches:raise ParseError('UNMATCHED_BRANCH_END')
    children={i:[] for i in range(len(residues))}
    for child,parent,ano,donor,acceptor in edges:
        children[parent].append((child,ano,donor,acceptor))
    def signature(index):
        desc=sorted(f'{a or "?"}{d or "?"}-{p or "?"}:{signature(c)}' for c,a,d,p in children[index])
        return residues[index]+('['+'|'.join(desc)+']' if desc else '')
    return ParsedGlycan(text,tuple(residues),tuple(edges),root,
         all(a is not None and d is not None and p is not None for _,_,a,d,p in edges),
         signature(root))

def compare_supported_graphs(a:ParsedGlycan,b:ParsedGlycan)->str:
    if a.signature==b.signature and a.full_linkages and b.full_linkages:
        return 'SAME_SUPPORTED_GRAPH' # NOT proof of complete chemical identity
    if Counter(a.residues)!=Counter(b.residues):return 'DIFFERENT_COMPOSITION'
    if a.full_linkages and b.full_linkages:return 'DIFFERENT_SUPPORTED_GRAPH'
    return 'UNRESOLVED'
