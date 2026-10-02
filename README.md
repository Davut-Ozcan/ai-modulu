# GiDA İçerik Analizi (demo)

CSV sürükle-bırak → gürültü filtresi → kural motoru → Gemini → veli için bulgu listesi.

```
CSV ──► Gürültü filtresi ──► Tekilleştirme ──► Kural motoru ──┐
        (UI yazıları atılır)  (scroll tekrarı)  (her zaman)     ├─► Birleştir ─► Bulgular
                                          └──► Gemini (sadece içerik) ┘
```
Depoda örnek veri yoktur; analiz için kendi CSV dosyanı yüklemen gerekir.

## Yerelde çalıştır (macOS)

Bilgisayarda Python 3.12 veya üzeri ve internet bağlantısı gerekir. Terminalde `cd ` yazıp `gida-analyzer` klasörünü Terminal penceresine sürükle, ardından Enter'a bas. Örneğin klasör İndirilenler'deyse:

```sh
cd ~/Downloads/gida-analyzer
```

İlk kurulumda Python ortamını oluştur ve paketleri yükle:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`.env` dosyası zaten varsa tekrar kopyalama; kopyalamak kayıtlı API anahtarını siler. Yeni kurulumda dosyayı oluşturup anahtarı `GEMINI_API_KEY=` satırına yaz:

```sh
test -f .env || cp .env.example .env
nano .env
```

`nano` içinde kaydetmek için `Ctrl+O`, `Enter`, çıkmak için `Ctrl+X` kullan. Anahtarı kimseyle paylaşma. Sonra uygulamayı başlat:

```sh
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8090 --env-file .env
```

Tarayıcıda http://127.0.0.1:8090 adresini aç. Sunucuyu durdurmak için terminalde `Ctrl+C` kullan. Sonraki çalıştırmalarda yalnızca proje klasörüne girip son komutu çalıştırmak yeterlidir. 8090 portunda uygulama zaten çalışıyorsa ikinci kez başlatma.

Anahtar yoksa sistem otomatik olarak sadece kural motoruyla çalışır. Varsayılan AI modeli `gemini-3.5-flash-lite`'tır; modeli `.env` içindeki `GEMINI_MODEL` satırından değiştirebilirsin.
Test: `GEMINI_MOCK=1` (ağa çıkmaz), `GEMINI_MOCK=quota` (kota bitti senaryosu).

## Yerelde çalıştır (Windows / PowerShell)

Python 3.12 veya üzerini kur. Kurulumda Python başlatıcısının (`py`) kullanılabilir olduğundan emin ol. İnternet bağlantısı gerekir. `gida-analyzer` klasörünü aç, Dosya Gezgini'nin adres çubuğuna `powershell` yazıp Enter'a bas. Açılan PowerShell bu klasörde olmalı.

İlk kurulumda şu komutları sırayla çalıştır:

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Not Defteri'nde `GEMINI_API_KEY=` satırına kendi anahtarını yazıp dosyayı kaydet. `.env` zaten varsa kopyalama komutu içeriğini korur. Uygulamayı başlat:

```powershell
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8090 --env-file .env
```

Tarayıcıda http://127.0.0.1:8090 adresini aç. Durdurmak için PowerShell'de `Ctrl+C` kullan. Sonraki çalıştırmalarda proje klasöründe PowerShell açıp yalnızca son komutu çalıştır.

## AI hata davranışı
| Durum | Davranış |
|---|---|
| Anahtar yok | AI kapalı, ekranda uyarı, kural motoru çalışır |
| Dakikalık limit (429) | `retryDelay` kadar bekler (toplam en fazla 75 sn), sonra devam |
| Günlük kota bitti (429 PerDay) | AI durur, kalan paketler kural motoruyla, ekranda "kota doldu" |
| Geçersiz anahtar | AI kapanır, uyarı |
| Tek paket bozuk yanıt / güvenlik bloğu | O paket atlanır, devam |
| 5xx | 3 deneme, artan bekleme |

AI yanıtları `data/ai_cache.json`'a yazılır: aynı CSV tekrar yüklenince kota harcanmaz.

## Projeyi başkasına gönderme

`gida-analyzer` klasörünü paylaşırken kendi API anahtarını içeren `.env` dosyasını, `.venv` klasörünü, `data/ai_cache.json` dosyasını ve gerçek ekran verisi içeren CSV/JSONL dosyalarını çıkar. Bu dosyalar Git tarafından yok sayılır. Alıcı `.env.example` dosyasından kendi `.env` dosyasını oluşturup kendi API anahtarını ekler; sonra kendi işletim sistemine uygun yerel çalıştırma adımlarını izler. `.venv` her bilgisayarda yeniden oluşturulmalıdır. `eval/evaluate.py` kullanımı için alıcının kendi `eval/test_set.jsonl` dosyasını sağlaması gerekir.

## Oracle VM'e deploy
1. Klasörü VM'e kopyala (`~/gida-analyzer`), `.env` oluştur.
2. `deploy/compose.snippet.yml` → mevcut compose'a ekle.
3. `deploy/Caddyfile.snippet` → Caddyfile'a ekle (`flush_interval -1` ilerleme akışı için şart).
4. `docker compose up -d --build analyzer && docker compose restart caddy`
5. https://analiz.152-70-40-87.nip.io

## Kod
- `analyzer/parse.py` gürültü filtresi (UI kromu, hesap/şarkı/reklam ayrımı)
- `analyzer/normalize.py` Türkçe normalizasyon (İ/ı, leet, a.m.k, harf tekrarı)
- `analyzer/lexicon.py` kategori sözlüğü (kodlar = `content_categories.code`)
- `analyzer/engine.py` kural skoru → severity
- `analyzer/llm.py` Gemini istemcisi, prompt, JSON şema, kota yönetimi, önbellek
- `analyzer/pipeline.py` uçtan uca akış (ilerleme olayları üretir)
- `app/` FastAPI + tek sayfa arayüz
- `eval/` ortak benchmark (P/R/F1), `run_batch.py` komut satırı
