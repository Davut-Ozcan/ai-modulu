"""Gemini istemcisi: toplu sınıflandırma, kota/hata yönetimi, disk önbelleği.

Ortam değişkenleri
  GEMINI_API_KEY        AI Studio anahtarı (yoksa sistem sadece kural motoruyla çalışır)
  GEMINI_MODEL          varsayılan gemini-3.5-flash-lite
  GEMINI_BATCH          tek istekte gönderilecek segment sayısı (varsayılan 60)
  GEMINI_MOCK           1 → ağa çıkmadan sahte yanıt (test), quota → ilk istekten sonra kota hatası
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from dataclasses import dataclass

import httpx

from .lexicon import CATEGORY_LABEL

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
CATEGORIES = list(CATEGORY_LABEL.keys())
SEVERITIES = ["low", "medium", "high", "critical"]

SYSTEM_PROMPT = f"""Sen okul tabanlı bir ebeveyn kontrol sisteminin içerik analiz modülüsün.
Girdi: bir gencin (13-17 yaş) telefon ekranından alınmış, arayüz yazıları önceden temizlenmiş metin parçaları.
Her parçanın id'si, tipi (caption=gönderi açıklaması, comment=yorum, text=ekran metni, audio=şarkı/ses adı) ve uygulaması var.

Görev: SADECE bir veli için sakıncalı olan parçaları döndür. Temiz parçaları hiç döndürme.

Kategoriler (category alanında sadece bu kodlar):
- hakaret: küfür, aşağılama, kişiye yönelik hakaret
- nefret_soylemi: etnik köken, cinsel yönelim, engellilik vb. gruplara yönelik nefret
- islamofobik: Müslümanlara/İslam'a yönelik nefret ve aşağılama
- mustehcenlik: cinsel içerik, cinselleştirme, pornografi, cinsel ima
- siddet: şiddet, tehdit, silah, kavga çağrısı
- kendine_zarar: intihar, kendine zarar verme, ölüm isteği (her zaman critical)
- kumar: casino, slot, poker vb.
- bahis: spor bahsi, bahis siteleri, bonus reklamları
- uyusturucu: uyuşturucu ve madde kullanımı
- bagimlilik: alkol, sigara, vape özendirme
- oyun: aşırı oyun oynama işaretleri (sıradan oyun reklamı DEĞİL; saatlerce aralıksız oynama gibi)
- diger: estetik/beden algısı baskısı, tehlikeli trend/challenge, yabancılarla gizli iletişim, kişisel bilgi paylaşımı

Kurallar:
- Türkçe argo, kısaltma ve kaçırma yazımlarını tanı (amk, s1kt1r, a.m.k, o.ç).
- Bağlama bak: "sex education dizisi", "boks siklet", "kan bağışı" gibi zararsız kullanımlar sakıncalı DEĞİL.
- Sıradan reklam, yemek, moda, haber, eğitim, mizah içerikleri sakıncalı değil.
- severity: low (hafif/dolaylı), medium (açık ama hafif), high (açık ve ciddi), critical (acil müdahale: kendine zarar, ciddi tehdit, çocuğa yönelik cinsel içerik).
- reason: velinin anlayacağı kısa Türkçe açıklama (en fazla 15 kelime).
- terms: metinde geçen tetikleyici kelime/ifadeler, metindeki yazımıyla.
- Bir parça birden fazla kategoriye girebilir; her biri ayrı nesne.
"""

RESPONSE_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "INTEGER"},
            "category": {"type": "STRING", "enum": CATEGORIES},
            "severity": {"type": "STRING", "enum": SEVERITIES},
            "reason": {"type": "STRING"},
            "terms": {"type": "ARRAY", "items": {"type": "STRING"}},
        },
        "required": ["id", "category", "severity", "reason"],
    },
}

SAFETY_OFF = [
    {"category": c, "threshold": "BLOCK_NONE"}
    for c in ("HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
              "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")
]


class QuotaExhausted(Exception):
    """Günlük kota bitti ya da dakikalık limit beklemeye rağmen aşılamadı."""


class AIUnavailable(Exception):
    """Anahtar geçersiz, ağ yok vb. — bu çalıştırmada AI kapatılır."""


@dataclass
class AIStatus:
    enabled: bool
    model: str
    mode: str  # "live" | "mock" | "off"
    reason: str = ""


def status() -> AIStatus:
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    if os.getenv("GEMINI_MOCK"):
        return AIStatus(True, model, "mock")
    if not os.getenv("GEMINI_API_KEY"):
        return AIStatus(False, model, "off", "GEMINI_API_KEY tanımlı değil")
    return AIStatus(True, model, "live")


# ---------------- önbellek ----------------
_CACHE_PATH = os.getenv("AI_CACHE_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "ai_cache.json"))
_cache_lock = threading.Lock()
_cache: dict[str, list[dict]] | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.load(open(_CACHE_PATH))
        except Exception:
            _cache = {}
    return _cache


def _save_cache():
    with _cache_lock:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        tmp = _CACHE_PATH + ".tmp"
        json.dump(_cache, open(tmp, "w"), ensure_ascii=False)
        os.replace(tmp, _CACHE_PATH)


def cache_key(text: str, model: str) -> str:
    return hashlib.sha1(f"{model}|{text}".encode()).hexdigest()


def cached(text: str, model: str):
    return _load_cache().get(cache_key(text, model))


def put_cache(text: str, model: str, hits: list[dict]):
    _load_cache()[cache_key(text, model)] = hits


# ---------------- Gemini çağrısı ----------------
def _parse_retry(err: dict) -> tuple[bool, float]:
    """(günlük kota mı, önerilen bekleme sn)"""
    daily, delay = False, 0.0
    for d in err.get("details", []):
        t = d.get("@type", "")
        if t.endswith("QuotaFailure"):
            for v in d.get("violations", []):
                if "PerDay" in v.get("quotaId", "") or "per_day" in v.get("quotaMetric", ""):
                    daily = True
        if t.endswith("RetryInfo"):
            m = re.match(r"([\d.]+)s", d.get("retryDelay", ""))
            if m:
                delay = float(m.group(1))
    if "per day" in err.get("message", "").lower():
        daily = True
    return daily, delay


def _mock_call(items: list[dict], call_no: int) -> list[dict]:
    from .engine import classify  # sahte yanıt: kural motorunu "AI" gibi döndür
    if os.getenv("GEMINI_MOCK") == "quota" and call_no >= 1:
        raise QuotaExhausted("Sahte kota hatası (GEMINI_MOCK=quota)")
    out = []
    for it in items:
        for h in classify(it["text"], it["kind"]):
            if h.severity != "low":
                out.append({"id": it["id"], "category": h.category, "severity": h.severity,
                            "reason": "Sahte AI yanıtı (mock mod)", "terms": h.terms})
    time.sleep(0.3)
    return out


def classify_batch(client: httpx.Client, items: list[dict], call_no: int) -> list[dict]:
    """items: [{id, text, kind, app}] → [{id, category, severity, reason, terms}]"""
    st = status()
    if st.mode == "mock":
        return _mock_call(items, call_no)
    if st.mode == "off":
        raise AIUnavailable(st.reason)

    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(items, ensure_ascii=False)}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
        "safetySettings": SAFETY_OFF,
    }
    if st.model.startswith("gemini-2.5-flash"):
        body["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

    url = API_URL.format(model=st.model)
    headers = {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}
    waited = 0.0
    for attempt in range(4):
        try:
            r = client.post(url, json=body, headers=headers, timeout=90)
        except httpx.HTTPError as e:
            if attempt == 3:
                raise AIUnavailable(f"Gemini'ye ulaşılamadı: {e.__class__.__name__}")
            time.sleep(2 * (attempt + 1))
            continue

        if r.status_code == 200:
            data = r.json()
            cands = data.get("candidates") or []
            if not cands or "content" not in cands[0]:
                reason = (cands[0].get("finishReason") if cands else None) or data.get("promptFeedback", {}).get("blockReason", "boş yanıt")
                raise ValueError(f"Gemini yanıt üretmedi ({reason})")
            text = "".join(p.get("text", "") for p in cands[0]["content"].get("parts", []))
            return json.loads(text)

        try:
            err = r.json().get("error", {})
        except Exception:
            err = {"message": r.text[:200]}

        if r.status_code == 429:
            daily, delay = _parse_retry(err)
            if daily:
                raise QuotaExhausted("Gemini günlük ücretsiz kotası doldu")
            delay = delay or 15 * (attempt + 1)
            if waited + delay > 75:
                raise QuotaExhausted("Gemini dakikalık istek limiti aşıldı, bekleme süresi çok uzun")
            time.sleep(delay)
            waited += delay
            continue
        if r.status_code in (400, 401, 403):
            msg = err.get("message", "")
            if "API key" in msg or err.get("status") in ("PERMISSION_DENIED", "UNAUTHENTICATED") or "API_KEY" in json.dumps(err):
                raise AIUnavailable("Gemini API anahtarı geçersiz ya da yetkisiz")
            if "location is not supported" in msg.lower():
                raise AIUnavailable("Gemini bu bölgede kullanılamıyor")
            raise ValueError(f"Gemini isteği reddetti: {msg[:160]}")
        if r.status_code in (500, 502, 503, 504):
            time.sleep(3 * (attempt + 1))
            continue
        raise ValueError(f"Gemini HTTP {r.status_code}: {err.get('message', '')[:160]}")
    raise AIUnavailable("Gemini art arda hata verdi")
