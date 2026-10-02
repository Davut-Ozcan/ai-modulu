"""Uçtan uca analiz. Her aşamada ilerleme olayı üretir (UI canlı gösterir).

  1 Yükle        CSV → satırlar
  2 Gürültü      ekran metni → anlamlı segmentler (UI kromu atılır)
  3 Tekilleştir  aynı segment bir kez işlenir (scroll tekrarları)
  4 Kural        sözlük + regex (her zaman çalışır, AI'dan bağımsız)
  5 AI           sadece içerik segmentleri, toplu istek, önbellek
  6 Birleştir    kural ∪ AI, cihaz + zaman bazında bulgu
"""
from __future__ import annotations

import time
from collections import Counter, defaultdict
from typing import Iterator

import httpx

from . import llm
from .engine import classify
from .lexicon import CATEGORY_LABEL, DB_CODE
from .loader import load_csv
from .normalize import normalize
from .parse import segments

SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
AI_KINDS = {"caption", "comment", "text", "audio"}
MAX_AI_CHARS = 400


def _ai_worthy(text: str) -> bool:
    letters = sum(ch.isalpha() for ch in text)
    return letters >= 4 and len(text) >= 5


def run(raw: bytes, use_ai: bool = True) -> Iterator[dict]:
    t0 = time.time()

    # 1 ── yükle
    df, load_stats = load_csv(raw)
    raw_chars = int(df["screen_text"].str.len().sum())
    yield {"type": "stage", "stage": "load", "rows": load_stats["rows_valid"], "chars": raw_chars, **load_stats}

    # 2 ── gürültü filtresi + 3 tekilleştirme
    occ: dict[str, list] = defaultdict(list)      # seg_key → [(row, kind, text)]
    seg_info: dict[str, dict] = {}
    seg_total = seg_chars = 0
    for r in df.itertuples(index=False):
        for s in segments(r.screen_text):
            key = normalize(s["text"]).strip()
            if not key:
                continue
            seg_total += 1
            seg_chars += len(s["text"])
            occ[key].append(r)
            if key not in seg_info:
                seg_info[key] = {"kind": s["kind"], "text": s["text"], "app": r.app_name}
    yield {"type": "stage", "stage": "filter", "segments": seg_total, "chars": seg_chars,
           "removed_pct": round(100 * (1 - seg_chars / raw_chars), 1) if raw_chars else 0}
    uniq_chars = sum(len(v["text"]) for v in seg_info.values())
    yield {"type": "stage", "stage": "dedupe", "segments": len(seg_info), "chars": uniq_chars}

    # 4 ── kural motoru
    hits: dict[tuple[str, str], dict] = {}        # (seg_key, category) → hit
    for key, info in seg_info.items():
        for h in classify(info["text"], info["kind"]):
            hits[(key, h.category)] = {"category": h.category, "severity": h.severity, "score": h.score,
                                       "terms": h.terms, "sources": {"kural"}, "reason": ""}
    yield {"type": "stage", "stage": "rules", "hits": len(hits)}

    # 5 ── AI
    st = llm.status()
    ai = {"mode": st.mode if use_ai else "off", "model": st.model, "state": "off", "message": "",
          "candidates": 0, "chars": 0, "calls": 0, "cached": 0, "failed_batches": 0, "hits": 0}
    if not use_ai:
        ai["message"] = "AI katmanı kapalı, sadece kural motoru çalıştı."
    elif not st.enabled:
        ai["message"] = f"AI kapalı: {st.reason}. Sonuçlar sadece kural motorundan."
    else:
        cands = [(k, v) for k, v in seg_info.items() if v["kind"] in AI_KINDS and _ai_worthy(v["text"])]
        ai["candidates"] = len(cands)
        ai["chars"] = sum(min(len(v["text"]), MAX_AI_CHARS) for _, v in cands)
        todo = []
        for k, v in cands:
            c = llm.cached(v["text"][:MAX_AI_CHARS], st.model)
            if c is None:
                todo.append((k, v))
            else:
                ai["cached"] += 1
                _merge_ai(hits, k, c)
        batch = int(__import__("os").getenv("GEMINI_BATCH", "60"))
        batches = [todo[i:i + batch] for i in range(0, len(todo), batch)]
        ai["state"] = "running"
        yield {"type": "stage", "stage": "ai_start", "batches": len(batches), **ai}

        with httpx.Client() as client:
            for bi, b in enumerate(batches):
                items = [{"id": i, "text": v["text"][:MAX_AI_CHARS], "kind": v["kind"], "app": v["app"]}
                         for i, (_, v) in enumerate(b)]
                try:
                    res = llm.classify_batch(client, items, bi)
                except llm.QuotaExhausted as e:
                    ai["state"] = "quota"
                    ai["message"] = (f"{e}. {bi}/{len(batches)} paket AI ile işlendi; "
                                     f"kalan {len(batches) - bi} paket sadece kural motoruyla değerlendirildi.")
                    break
                except llm.AIUnavailable as e:
                    ai["state"] = "error"
                    ai["message"] = f"{e}. Sonuçlar kural motorundan."
                    break
                except Exception as e:  # tek paket bozuk yanıt → atla, devam et
                    ai["failed_batches"] += 1
                    ai["message"] = f"{ai['failed_batches']} paket işlenemedi ({str(e)[:80]})."
                    continue
                ai["calls"] += 1
                by_id = defaultdict(list)
                for x in res if isinstance(res, list) else []:
                    if isinstance(x, dict) and x.get("category") in CATEGORY_LABEL and isinstance(x.get("id"), int) and 0 <= x["id"] < len(b):
                        by_id[x["id"]].append({k: x.get(k) for k in ("category", "severity", "reason", "terms")})
                for i, (k, v) in enumerate(b):
                    found = by_id.get(i, [])
                    llm.put_cache(v["text"][:MAX_AI_CHARS], st.model, found)
                    _merge_ai(hits, k, found)
                yield {"type": "stage", "stage": "ai_progress", "done": bi + 1, "batches": len(batches)}
            llm._save_cache()
        if ai["state"] == "running":
            if ai["failed_batches"]:
                ai["state"] = "partial" if ai["calls"] or ai["cached"] else "error"
            else:
                ai["state"] = "ok"
                ai["message"] = f"{ai['candidates']} içerik parçası AI ile analiz edildi ({ai['cached']} önbellekten)."
    ai["hits"] = sum(1 for h in hits.values() if "ai" in h["sources"])
    yield {"type": "stage", "stage": "ai_done", **ai}

    # 6 ── birleştir: (cihaz, segment, kategori) bazında bulgu
    findings = []
    for (key, cat), h in hits.items():
        info = seg_info[key]
        by_dev = defaultdict(list)
        for r in occ[key]:
            by_dev[r.device_id].append(r)
        for dev, rows in by_dev.items():
            findings.append({
                "device": str(dev)[-4:] if dev else "?",
                "app": rows[0].app_name,
                "category": cat,
                "db_category": DB_CODE[cat],
                "category_label": CATEGORY_LABEL[cat],
                "severity": h["severity"],
                "score": h.get("score", 0),
                "terms": h["terms"],
                "reason": h["reason"],
                "source": "ikisi" if len(h["sources"]) == 2 else next(iter(h["sources"])),
                "kind": info["kind"],
                "text": info["text"],
                "context": rows[0].screen_text[:700],
                "first_seen": rows[0].ts.isoformat(),
                "last_seen": rows[-1].ts.isoformat(),
                "count": len(rows),
            })
    findings.sort(key=lambda f: (-SEV_RANK[f["severity"]], -len(f["source"]), f["first_seen"]))

    yield {"type": "result", "meta": {
        **load_stats,
        "devices": int(df["device_id"].nunique()),
        "apps": dict(Counter(df["app_name"])),
        "range": [df["ts"].min().isoformat(), df["ts"].max().isoformat()],
        "raw_chars": raw_chars, "segments": seg_total, "segment_chars": seg_chars,
        "unique_segments": len(seg_info), "unique_chars": uniq_chars,
        "ai": ai, "elapsed_s": round(time.time() - t0, 1),
        "by_severity": dict(Counter(f["severity"] for f in findings)),
        "by_category": dict(Counter(f["category_label"] for f in findings)),
    }, "findings": findings}


def _merge_ai(hits: dict, key: str, found: list[dict]):
    for x in found:
        cat = x["category"]
        sev = x.get("severity") if x.get("severity") in SEV_RANK else "medium"
        if cat == "kendine_zarar":
            sev = "critical"
        terms = [t for t in (x.get("terms") or []) if isinstance(t, str)][:6]
        h = hits.get((key, cat))
        if h is None:
            hits[(key, cat)] = {"category": cat, "severity": sev, "score": 0, "terms": terms,
                                "sources": {"ai"}, "reason": x.get("reason") or ""}
        else:
            h["sources"].add("ai")
            h["reason"] = x.get("reason") or h["reason"]
            if SEV_RANK[sev] > SEV_RANK[h["severity"]]:
                h["severity"] = sev
            h["terms"] = sorted(set(h["terms"]) | set(terms))
