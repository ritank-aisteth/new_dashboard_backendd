# Firebase authentication on Google Cloud Run

The frontend and backend keep their existing Cloud Run services and API routes:

- Frontend: `https://aisteth-frontend-xm67mze56q-el.a.run.app`
- Backend: `https://aisteth-backend-586282894333.asia-south1.run.app`
- Session creation: `POST /api/auth/session`
- Session status: `GET /api/auth/status`
- Current identity: `GET /api/v1/auth/me`

## Firebase Console

In the existing `aisteth-development` Firebase project:

1. Enable Authentication > Sign-in method > Email/Password.
2. Under Authentication > Settings > Authorized domains, add:
   - `localhost`
   - `aisteth-frontend-xm67mze56q-el.a.run.app`

No new Firebase project or user import is required. The login form authenticates
against the users already present in this Firebase project.

## Local development

The frontend `.env.local` already contains the supplied Firebase web app values.
The backend `.env` contains:

```dotenv
GOOGLE_CLOUD_PROJECT=aisteth-development
FIREBASE_PROJECT_ID=aisteth-development
DASHBOARD_AUTHORIZATION_MODE=firebase-local
```

Firebase Admin uses Application Default Credentials locally:

```powershell
gcloud auth application-default login
python -m pip install -r ..\backend_dashboard\requirements-dev.txt
Push-Location ..
python -m backend_dashboard.run
Pop-Location
npm install
npm run dev
```

Open `http://127.0.0.1:3000`. The frontend calls the backend at
`http://127.0.0.1:8000`.

## Cloud Build deployment

The frontend `cloudbuild.yaml` deploys the Firebase web configuration as runtime
environment variables and points `DASHBOARD_API_BASE_URL` at the existing backend
Cloud Run service.

The backend `cloudbuild.yaml` deploys with `backend-env.yaml`. That file sets:

```yaml
GOOGLE_CLOUD_PROJECT: "aisteth-development"
FIREBASE_PROJECT_ID: "aisteth-development"
DASHBOARD_AUTHORIZATION_MODE: "dynamodb"
```

Deploy from each repository root:

```powershell
gcloud builds submit --config cloudbuild.yaml .
gcloud builds submit --config ..\backend_dashboard\cloudbuild.yaml ..\backend_dashboard
```

The Cloud Run backend initializes Firebase Admin with Application Default
Credentials from its runtime service account. It does not need a Firebase private
key or service-account JSON file.

## Role mapping

Firebase verifies identity. Authorization remains in the existing DynamoDB
user-roles table. The backend queries `user_id` using the verified Firebase email;
if a Firebase user has no email, it falls back to that user's Firebase UID. Existing
email-based role records therefore continue to work unchanged.

## Updating Firebase web configuration

When credentials change, update the Firebase values in `.env.local` and in the
frontend `cloudbuild.yaml` `--set-env-vars` value. When the Firebase project ID
changes, also update `GOOGLE_CLOUD_PROJECT` and `FIREBASE_PROJECT_ID` in the
backend `backend-env.yaml`.
