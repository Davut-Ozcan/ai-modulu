FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY analyzer ./analyzer
COPY app ./app
ENV AI_CACHE_PATH=/srv/cache/ai_cache.json
EXPOSE 8090
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8090"]
