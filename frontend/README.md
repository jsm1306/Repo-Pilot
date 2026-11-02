# RepoPilot frontend

This is the first frontend milestone: a standalone React + TypeScript + Vite design-system playground for the Evidence Field direction. It demonstrates reusable controls and the visual states that will support the future repository workbench.

The question flow and repository indexing are connected to the Python API. Google Identity Services establishes a RepoPilot session before user-owned repositories, indexing jobs, answers, and evidence are available.

## Requirements

- Node.js 20 or newer
- npm

## Run locally

```powershell
# Configure frontend/.env from frontend/.env.example with the Google OAuth web client ID.
# Configure app/.env from app/.env.example with GOOGLE_CLIENT_ID and REPOPILOT_AUTH_SECRET.
# Apply the database migration from the repository root:
.\venv\Scripts\alembic.exe upgrade head

# Terminal 1, from the repository root:
.\venv\Scripts\python.exe -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000

# Terminal 2:
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Vite proxies `/api` requests to `http://127.0.0.1:8000`.

The API exposes:

- `GET /api/health`
- `POST /api/auth/google`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/repositories` (authenticated)
- `POST /api/questions` (authenticated)
- `GET /api/questions/stream` (authenticated)
- `POST /api/indexing` (authenticated)
- `GET /api/indexing/{job_id}` (authenticated and owner-scoped)

Indexing accepts an HTTPS GitHub URL and reports queued, running, completed, or failed stages. Existing local clones are reused.

## Google Cloud setup

Create a Google OAuth client of type **Web application** in Google Cloud Console.
Add the exact local origins `http://localhost:5173` and
`http://127.0.0.1:5173` as authorized JavaScript origins. Put the client ID in
both `frontend/.env` as `VITE_GOOGLE_CLIENT_ID` and `app/.env` as
`GOOGLE_CLIENT_ID`. Never put the client secret in the frontend or repository.

The backend verifies the GIS ID token with Google's official `google-auth`
library, checks issuer, audience, expiry, signature, and `email_verified`, and
uses the token's `sub` claim as the external identity. RepoPilot issues its own
15-minute HttpOnly session cookie; `REPOPILOT_AUTH_SECRET` must be a long random
secret and should be rotated through deployment secret management in production.

## Checks

```powershell
npm run typecheck
npm run build
```

## Structure

- `src/App.tsx` — workbench composition and API-backed interaction state
- `src/api.ts` — typed API client and response models
- `src/components.tsx` — reusable buttons, panels, statuses, alerts, fields, and code lines
- `src/styles.css` — semantic light/dark tokens and responsive component styling

No Tailwind CSS is used. The token layer is plain CSS so it can be reused or mapped to a future component framework without introducing a second styling system.
