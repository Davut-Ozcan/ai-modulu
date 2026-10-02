"""CSV export → findings.json (demo/ofline analiz).

Aynı içerik ardışık capture'larda tekrar tekrar görünür (scroll, like sayısı
değişimi). Bulgu anahtarı: (device, segment metni, kategori); ilk/son görülme
ve görülme sayısı tutulur → veli 40 satır değil 1 satır görür.
"""
import json
import sys
from collections import Counter
from zoneinfo import ZoneInfo

import pandas as pd

from analyzer.engine import classify
from analyzer.lexicon import CATEGORY_LABEL
from analyzer.parse import segments

TZ = ZoneInfo("Europe/Istanbul")
SEV_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

if len(sys.argv) < 2:
    sys.exit("Kullanım: python run_batch.py <export.csv>")
src = sys.argv[1]
df = pd.read_csv(src)

# Kolon toleransı: farklı export sorgularıyla da çalışsın
ALIASES = {"screen_text": ["text", "content"], "captured_at_device": ["captured_at", "received_at", "created_at"]}
for col, alts in ALIASES.items():
    if col not in df.columns:
        alt = next((a for a in alts if a in df.columns), None)
        if alt is None:
            sys.exit(f"CSV'de '{col}' kolonu yok (alternatifler: {alts}). Mevcut: {list(df.columns)}")
        df[col] = df[alt]
if "id" not in df.columns:
    df["id"] = df.index.astype(str)
if "device_id" not in df.columns:
    df["device_id"] = "unknown"
if "package_name" not in df.columns:
    df["package_name"] = ""
if "app_name" not in df.columns:
    df["app_name"] = df["package_name"]
df["app_name"] = df["app_name"].fillna(df["package_name"]).replace("", "Bilinmeyen")
df = df[df["screen_text"].notna() & (df["screen_text"].astype(str).str.strip().str.len() > 2)].copy()
df["screen_text"] = df["screen_text"].astype(str)
df["device_id"] = df["device_id"].astype(str)
df["ts"] = pd.to_datetime(df["captured_at_device"], utc=True, format="ISO8601", errors="coerce").dt.tz_convert(TZ)
df = df[df["ts"].notna()]
df = df.sort_values("ts")

findings: dict[tuple, dict] = {}
seg_total = 0
for r in df.itertuples():
    for seg in segments(r.screen_text):
        seg_total += 1
        for h in classify(seg["text"], seg["kind"]):
            key = (r.device_id, seg["text"].lower(), h.category)
            f = findings.get(key)
            if f is None:
                findings[key] = {
                    "device_id": r.device_id,
                    "device": r.device_id[-4:],
                    "app": r.app_name,
                    "package": r.package_name,
                    "category": h.category,
                    "category_label": CATEGORY_LABEL[h.category],
                    "severity": h.severity,
                    "score": h.score,
                    "terms": h.terms,
                    "kind": seg["kind"],
                    "text": seg["text"],
                    "context": r.screen_text[:600],
                    "first_seen": r.ts.isoformat(),
                    "last_seen": r.ts.isoformat(),
                    "count": 1,
                    "capture_ids": [r.id],
                }
            else:
                f["last_seen"] = r.ts.isoformat()
                f["count"] += 1
                if len(f["capture_ids"]) < 5:
                    f["capture_ids"].append(r.id)

out = sorted(findings.values(), key=lambda f: (-SEV_RANK[f["severity"]], -f["score"], f["first_seen"]))
meta = {
    "captures": len(df),
    "unique_texts": int(df["screen_text"].nunique()),
    "segments": seg_total,
    "devices": int(df["device_id"].nunique()),
    "range": [df["ts"].min().isoformat(), df["ts"].max().isoformat()],
    "by_category": Counter(f["category"] for f in out),
    "by_severity": Counter(f["severity"] for f in out),
}
json.dump({"meta": meta, "findings": out}, open("findings.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(meta, ensure_ascii=False, indent=1))
import subprocess, os
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo", "build.py")], check=True)
for f in out:
    print(f"{f['severity']:8} {f['score']:5} {f['category']:14} {f['kind']:8} x{f['count']:<3} {f['terms']} :: {f['text'][:90]}")
