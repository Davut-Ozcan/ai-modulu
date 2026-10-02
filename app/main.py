"""GiDA içerik analiz demo servisi.

uvicorn app.main:app --host 0.0.0.0 --port 8090
"""
import json
import os
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from analyzer import llm
from analyzer.loader import CSVError
from analyzer.pipeline import run

ROOT = Path(__file__).resolve().parent
MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024
_lock = threading.Lock()  # aynı anda tek analiz → ücretsiz kota korunur

app = FastAPI(title="GiDA Content Analyzer", docs_url="/api/docs")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    st = llm.status()
    return {"ok": True, "ai": {"enabled": st.enabled, "mode": st.mode, "model": st.model, "reason": st.reason}}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), use_ai: bool = Form(True)):
    raw = await file.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        return JSONResponse({"error": f"Dosya {MAX_BYTES // 1024 // 1024} MB sınırını aşıyor."}, status_code=413)
    if not raw.strip():
        return JSONResponse({"error": "Dosya boş."}, status_code=400)

    def stream():
        if not _lock.acquire(timeout=120):
            yield json.dumps({"type": "error", "message": "Başka bir analiz sürüyor, biraz sonra tekrar deneyin."}) + "\n"
            return
        try:
            for ev in run(raw, use_ai=use_ai):
                yield json.dumps(ev, ensure_ascii=False) + "\n"
        except CSVError as e:
            yield json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False) + "\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": f"Beklenmeyen hata: {e.__class__.__name__}: {str(e)[:200]}"},
                             ensure_ascii=False) + "\n"
        finally:
            _lock.release()

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
