"""Türkçe-duyarlı metin normalizasyonu (filtre kaçırma hilelerine karşı)."""
import re
import unicodedata

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "€": "e"})
_ZW = re.compile(r"[​-‏⁠️]")


def tr_lower(s: str) -> str:
    # Python lower() 'I'→'i' yapar; Türkçede 'I'→'ı', 'İ'→'i'
    return s.replace("I", "ı").replace("İ", "i").lower()


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text)
    t = _ZW.sub("", t)
    t = tr_lower(t)
    # a.m.k / s-i-k gibi tek harf ayraçlarını birleştir
    t = re.sub(r"\b(?:\w[\.\-\*_ ]){2,}\w\b", lambda m: re.sub(r"[\.\-\*_ ]", "", m.group()), t)
    t = t.translate(_LEET)
    # 3+ tekrar eden harfi 2'ye indir (ammmk → amk sonraki adımda, siiiktir → siktir)
    t = re.sub(r"(\w)\1{2,}", r"\1", t)
    # kullanıcı adlarındaki . _ ayraçlarını boşluğa çevir (bitch.llady → bitch llady)
    t = re.sub(r"(?<=\w)[._](?=\w)", " ", t)
    return t
