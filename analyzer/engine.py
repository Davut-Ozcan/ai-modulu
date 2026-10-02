"""Sözlük katmanı + skor. Model katmanı (BERTurk) sonradan aynı arayüze takılır:
   classify(segment_text) -> list[Hit]
"""
import re
from dataclasses import dataclass, asdict

from .lexicon import LEXICON, CATEGORY_PRIORITY
from .normalize import normalize

_COMPILED = {cat: [(re.compile(p, re.I), w) for p, w in pats] for cat, pats in LEXICON.items()}

# segment tipine göre güven: kullanıcının gördüğü caption/yorum > kullanıcı adı/şarkı adı
KIND_WEIGHT = {"caption": 1.0, "comment": 1.0, "text": 0.9, "audio": 0.7, "author": 0.6, "username": 0.6, "ad": 0.7}


@dataclass
class Hit:
    category: str
    terms: list[str]
    score: float
    severity: str
    source: str = "lexicon"


def severity_of(score: float) -> str:
    if score >= 4:
        return "critical"
    if score >= 2.5:
        return "high"
    if score >= 1.2:
        return "medium"
    return "low"


def classify(text: str, kind: str = "text") -> list[Hit]:
    norm = normalize(text)
    hits = []
    for cat, pats in _COMPILED.items():
        terms, best = [], 0
        for rx, w in pats:
            for m in rx.finditer(norm):
                terms.append(m.group().strip())
                best = max(best, w)
        if not terms:
            continue
        # en güçlü eşleşme × kategori önceliği × segment tipi, çoklu eşleşme küçük bonus
        score = best * CATEGORY_PRIORITY[cat] * KIND_WEIGHT.get(kind, 0.8) + 0.25 * (len(set(terms)) - 1)
        sev = "critical" if cat == "kendine_zarar" else severity_of(score)
        hits.append(Hit(cat, sorted(set(terms)), round(score, 2), sev))
    return hits


def to_dict(h: Hit) -> dict:
    return asdict(h)
