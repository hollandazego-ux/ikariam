# Ikariam Backend API

Bu servis, buyuk JSON dosyasini server-side yukler ve frontend'e sadece gerekli kucuk yanitlari doner.

## Ozellikler

- Tek seferde veri yukleme (server acilisinda)
- Ada ozet listesi endpoint'i
- Ada detay endpoint'i
- Kullanici/oyuncu arama endpoint'i
- CORS acik (frontend farkli domain'de olsa da cagirabilir)

## Kurulum

```bash
cd backend-api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Calistirma

Varsayilan veri dosyasi proje kokundeki `ikariam_world_slim.json`.

```bash
cd /Users/mac/Desktop/ikariam/backend-api
IKARIAM_DATA_FILE=../ikariam_world_slim.json uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Farkli dosya vermek icin:

```bash
cd /Users/mac/Desktop/ikariam/backend-api
IKARIAM_DATA_FILE=../ikariam_full_fresh_world_and_nonempty_details.json uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Endpointler

- `GET /health`
- `GET /api/meta`
- `GET /api/islands/summary`
- `GET /api/island/{x}/{y}`
- `GET /api/search?q=zegovski&mode=player&limit=100`

`mode` degerleri:

- `player`: Oyuncu odakli arama
- `alliance`: Ittifak odakli arama
- `all`: Tum alanlarda arama

## Deploy Notu

Netlify yerine backend tarafi icin Render/Railway/Fly.io gibi bir servis kullan.
Static frontend'in API isteklerini bu servise yonlendir.

Frontend (Netlify) tarafinda:

- API Base URL alanina backend adresini yaz (ornek: `https://ikariam-api.onrender.com`)
- `API'ye Baglan` tusuna bas
- Arama tipini `Oyuncu` veya `Ittifak` sec

Render ornegi:

- Runtime: Python
- Root Directory: `backend-api`
- Build command: `pip install -r requirements.txt`
- Start command: `IKARIAM_DATA_FILE=../ikariam_world_slim.json uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment variable (opsiyonel): `IKARIAM_MAX_SEARCH_RESULTS=200`

Not: Root Directory `backend-api` olarak ayarlanirsa, veri dosyasi proje kokunde oldugu icin `IKARIAM_DATA_FILE=../ikariam_world_slim.json` kullan.
