# AiSteth dashboard frontend

The dashboard authenticates existing users with Firebase email/password authentication. The Firebase ID token is verified by the FastAPI backend and stored by the frontend only in a short-lived `HttpOnly`, `SameSite=Lax` cookie. Tokens are not written to browser storage.

## Local configuration

Copy `.env.example` to `.env.local` and set:

- `NEXT_PUBLIC_FIREBASE_API_KEY`
- `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID`
- `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
- `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`
- `NEXT_PUBLIC_FIREBASE_APP_ID`
- `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` (optional)
- `DASHBOARD_API_BASE_URL` — the FastAPI origin, normally `http://127.0.0.1:8000` locally.

Firebase Authentication must have Email/Password enabled, and both `localhost` and the frontend Cloud Run hostname must be listed as authorized domains. `.env.local` is ignored by Git.

## Run

```powershell
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Google Cloud

The checked-in `cloudbuild.yaml` builds the frontend image and deploys it to Cloud Run with the Firebase web configuration and production backend URL. The backend `cloudbuild.yaml` uses `backend-env.yaml` and Firebase Admin Application Default Credentials. See [GCP deployment](DEPLOYMENT_GCP.md).

## Verification

```powershell
npm run audit:types
npm run build
npm audit
```
