# RepoPilot frontend

This is the first frontend milestone: a standalone React + TypeScript + Vite design-system playground for the Evidence Field direction. It demonstrates reusable controls and the visual states that will support the future repository workbench.

The question flow and repository indexing are connected to the Python API. The frontend reads repositories from Chroma, starts background indexing jobs, and renders answers and evidence returned by the existing LangGraph workflow.

## Requirements

- Node.js 20 or newer
- npm

## Run locally

```powershell
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
- `GET /api/repositories`
- `POST /api/questions`
- `POST /api/indexing`
- `GET /api/indexing/{job_id}`

Indexing accepts an HTTPS GitHub URL and reports queued, running, completed, or failed stages. Existing local clones are reused.

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
