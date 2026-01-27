# Deployment Guide

Backend jest deployed na **Render.com** (FREE tier). Ten dokument opisuje jak to zostało zrobione i jak można przenieść na Railway.

## Aktualne środowisko (27.01.2026)

**Platform:** Render.com  
**URL:** https://travel-planner-backend-xbsp.onrender.com  
**Tier:** Free (0$/miesiąc)  
**Region:** Frankfurt (EU Central)  
**Status:** Live ✅

## Render.com Setup (jak to zrobiliśmy)

### Krok 1: Konto Render

1. https://render.com/ → "Sign up with GitHub"
2. Authorize Render przez GitHub
3. Verify email

### Krok 2: Nowy Web Service

1. Dashboard → "New +" → "Web Service"
2. "Public Git Repository" tab
3. URL: `https://github.com/karolinasobotkiewicz-cyber/travel-planner-backend`
4. Click "Connect"

### Krok 3: Konfiguracja

**Name:** `travel-planner-backend`  
**Region:** Frankfurt (EU Central)  
**Branch:** main  
**Runtime:** Docker  
**Instance Type:** Free

### Krok 4: Environment Variables

Dodane zmienne (przez UI):

```
ENVIRONMENT=production
DEBUG=false
OPENWEATHER_API_KEY=your_openweather_key_here
GEOCODING_API_KEY=your_geocoding_key_here
CORS_ORIGINS=*
API_HOST=0.0.0.0
API_PORT=8000
```

### Krok 5: Deploy

Click "Create Web Service" → build started automatycznie.

Build time: ~8-10 minut.

Success indicators w logach:
```
INFO: Started server process
INFO: Application startup complete
INFO: Uvicorn running on http://0.0.0.0:8000
```

## Dockerfile

Backend używa multi-stage Dockerfile:

```dockerfile
# Stage 1: Builder - instaluje dependencies
FROM python:3.11-slim as builder
# ... instalacja pakietów

# Stage 2: Runtime - kopiuje tylko to co potrzebne
FROM python:3.11-slim
# ... minimalna warstwa runtime
```

**Zalety:**
- Mniejszy image (~200MB vs ~800MB)
- Szybszy startup
- Bezpieczniejszy (mniej surface attack)

## Free Tier Limitations

**Cold Starts:** Backend "zasypia" po 15 minutach bez requestów.

Pierwsze uruchomienie po przerwie:
- Cold start: 30-50 sekund
- Kolejne requesty: normalne (~50-200ms)

**Dla developmentu:** OK, można poczekać  
**Dla produkcji:** NIE OK, użytkownicy nie będą czekać

**Rozwiązanie:** Upgrade na paid tier ($7/miesiąc Render lub $5-20/miesiąc Railway).

## Monitoring

### Logi

Dashboard Render → Service → Logs tab

Live tail aktywny, filtrowanie po "All logs", "Build logs", "Deploy logs".

### Health Checks

Render automatycznie robi health checks:
- Endpoint: `/` (HEAD request)
- Interval: co 30s
- Timeout: 10s

Backend zwraca 405 dla HEAD (bo endpoint akceptuje GET) - to OK, Render to rozumie.

## Automatic Deploys

Render śledzi branch `main` na GitHubie.

Push do main → automatyczny redeploy (~5-10 minut).

**Wyłączenie auto-deploy:**
Settings → Build & Deploy → "Auto-Deploy: No"

## Custom Domain (opcjonalne)

Settings → Custom Domain → "Add Custom Domain"

Przykład:
- Domain: `api.travelplanner.pl`
- CNAME: `travel-planner-backend-xbsp.onrender.com`

## Migration do Railway (przyszłość)

Gdy klientka będzie gotowa na paid tier, migracja to 10 minut roboty.

### Krok 1: Railway Account

1. https://railway.app/ → "Login with GitHub"
2. $5 trial credits (wystarczy na kilka tygodni)

### Krok 2: New Project

1. Dashboard → "New Project"
2. "Deploy from GitHub repo"
3. Select: `karolinasobotkiewicz-cyber/travel-planner-backend`

### Krok 3: Environment Variables

Settings → Variables → "Raw Editor"

Paste (to samo co na Render):
```
ENVIRONMENT=production
DEBUG=false
OPENWEATHER_API_KEY=your_openweather_key_here
GEOCODING_API_KEY=your_geocoding_key_here
CORS_ORIGINS=*
API_HOST=0.0.0.0
API_PORT=8000
```

### Krok 4: Deploy

Railway auto-wykrywa Dockerfile → build starts.

Success: URL dostępny w ~5-10 minut.

**URL przykład:** `https://travel-planner-backend-production.up.railway.app`

### Krok 5: Update Frontend

Zmień w frontendzie API URL z Render na Railway.

**Gotowe!** Backend zawsze aktywny, bez cold starts.

## Cost Comparison

| Platform | Tier | Cost/m | Cold Starts | RAM | Deploy Time |
|----------|------|---------|-------------|-----|-------------|
| **Render Free** | Free | $0 | ⚠️ 30-50s po 15min | 512 MB | 8-10 min |
| **Render Starter** | Paid | $7 | ❌ None | 512 MB | 8-10 min |
| **Railway Hobby** | Trial | $5 trial | ❌ None | 8 GB | 5-8 min |
| **Railway Pro** | Paid | ~$20 | ❌ None | 8 GB | 5-8 min |

**Rekomendacja dla produkcji:** Railway Hobby (~$5-10/miesiąc zużycie) lub Render Starter ($7/miesiąc flat).

## Troubleshooting

### Build Failed

Check logs:
```
ModuleNotFoundError: No module named 'xxx'
```
→ Missing dependency w requirements.txt

```
ERROR: Failed to solve: failed to copy files
```
→ Problem z .dockerignore lub path w Dockerfile

### App Crashed

Check logs:
```
ImportError: cannot import name 'xxx'
```
→ Missing __init__.py exports

```
Address already in use
```
→ Port conflict (powinno być 8000, nie 80)

### Slow Response

Free tier cold start - poczekaj 30-50s przy pierwszym requeście po przerwie.

Lub upgrade na paid tier.

## Rollback

Render → Deploys tab → "..." przy starym deployu → "Redeploy"

Railway → Deployments → kliknij stary → "Redeploy"

## Security

**Secrets w environment variables - NIGDY w kodzie!**

`.env` w `.gitignore` ✅  
Environment variables tylko przez Render/Railway UI ✅

**CORS:**
- Teraz: `*` (wildcard, wszystkie origin)
- Produkcja: konkretny URL frontendu (np. `https://travelplanner.pl`)

Update w Render: Settings → Environment → Edit `CORS_ORIGINS`

## Backup Strategy

**Kod:** GitHub repo (karolinasobotkiewicz-cyber/travel-planner-backend)  
**Dane:** In-memory (ETAP 1) - restart = reset  
**Config:** Environment variables zapisane lokalnie w .env (gitignored) + dokumentacja

ETAP 2: PostgreSQL → backup database przez Railway/Render.

## Support

Render help: https://render.com/docs  
Railway help: https://docs.railway.app

Issues z deploymentem: ngencode.dev@gmail.com

---

Last update: 27.01.2026  
Status: Backend live on Render ✅