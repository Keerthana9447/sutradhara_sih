# SUTRADHARA deployment (Render + Vercel)

## Architecture
- Frontend: Vercel (Vite/React)
- Backend: Render (FastAPI)
- Default voice input: browser Speech Recognition (no ASR API key)
- Default Read Aloud: browser SpeechSynthesis (no TTS API key)
- Existing Sarvam ASR/TTS endpoints remain available as optional server-side integrations.

## Local frontend
Create `frontend/.env.local` only if you want to point the UI at a non-local backend:
```
VITE_API_URL=http://127.0.0.1:8000
```
For normal local development, leave it unset; Vite's `/api` proxy is used.

## Render
Create a Web Service from this repository.
- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/health`

Set `CORS_ORIGINS` to the exact Vercel URL, e.g. `https://your-app.vercel.app`.
Add other secrets only when their corresponding optional feature is needed.

## Vercel
Create a project from the repository.
- Root Directory: `frontend`
- Build Command: `npm run build`
- Output Directory: `dist`
- Environment Variable: `VITE_API_URL=https://your-render-service.onrender.com`

Redeploy after setting the variable.

## Voice requirements
Use a current Chrome/Edge browser over the HTTPS Vercel URL and allow microphone access. Browser Speech Recognition support is browser-dependent. Read Aloud uses the browser/OS speech voices; Telugu/Hindi/etc. voice availability depends on installed browser/OS voices.

## Important
Do not put `GROQ_API_KEY`, `SARVAM_API_KEY`, or Bhashini secrets in Vercel `VITE_*` variables. Vite exposes `VITE_*` values to the browser.
