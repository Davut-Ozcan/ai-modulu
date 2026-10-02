"""CSV → normalize edilmiş DataFrame. Farklı export sorgularına toleranslı."""
from __future__ import annotations

import io
from zoneinfo import ZoneInfo

import pandas as pd

TZ = ZoneInfo("Europe/Istanbul")
ALIASES = {
    "screen_text": ["text", "content", "message", "body"],
    "captured_at_device": ["captured_at", "received_at", "created_at", "timestamp", "time"],
}
APP_NAMES = {
    "com.instagram.android": "Instagram", "com.whatsapp": "WhatsApp", "com.zhiliaoapp.musically": "TikTok",
    "com.ss.android.ugc.trill": "TikTok", "com.google.android.youtube": "YouTube", "com.snapchat.android": "Snapchat",
    "com.twitter.android": "X (Twitter)", "org.telegram.messenger": "Telegram", "com.discord": "Discord",
    "com.android.chrome": "Chrome", "com.facebook.katana": "Facebook", "com.reddit.frontpage": "Reddit",
}


class CSVError(ValueError):
    pass


def load_csv(raw: bytes) -> tuple[pd.DataFrame, dict]:
    try:
        df = pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding_errors="replace")
    except Exception as e:
        raise CSVError(f"Dosya CSV olarak okunamadı: {e.__class__.__name__}")
    df.columns = [c.strip().lower() for c in df.columns]
    total = len(df)

    for col, alts in ALIASES.items():
        if col not in df.columns:
            alt = next((a for a in alts if a in df.columns), None)
            if alt is None:
                raise CSVError(
                    f"'{col}' kolonu bulunamadı. Kabul edilen adlar: {', '.join([col] + alts)}. "
                    f"Dosyadaki kolonlar: {', '.join(df.columns[:12])}"
                )
            df[col] = df[alt]
    for col, default in (("id", None), ("device_id", "bilinmiyor"), ("package_name", ""), ("app_name", "")):
        if col not in df.columns:
            df[col] = df.index.astype(str) if default is None else default

    df["app_name"] = [
        a or APP_NAMES.get(p, p.split(".")[-1].capitalize() if p else "Bilinmeyen")
        for a, p in zip(df["app_name"], df["package_name"])
    ]
    df["screen_text"] = df["screen_text"].astype(str)
    df = df[df["screen_text"].str.strip().str.len() > 2].copy()
    no_text = total - len(df)

    df["ts"] = pd.to_datetime(df["captured_at_device"], utc=True, errors="coerce", format="mixed").dt.tz_convert(TZ)
    bad_ts = int(df["ts"].isna().sum())
    df = df[df["ts"].notna()].sort_values("ts")
    if df.empty:
        raise CSVError("Dosyada analiz edilecek geçerli satır yok (metin ya da tarih boş).")
    return df, {"rows_total": total, "rows_no_text": no_text, "rows_bad_time": bad_ts, "rows_valid": len(df)}
