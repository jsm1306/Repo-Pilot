# RepoPilot

RepoPilot is an AI-powered repository intelligence and software
engineering assistant.

The goal is to build a system that can:

- understand an unfamiliar codebase
- retrieve relevant code and documentation
- investigate software issues
- test applications through browser automation
- propose code fixes
- verify fixes through automated tests
- keep humans in the loop before making risky changes

## Architecture

Coming soon.

## Development Roadmap

- [x] Project initialization
- [ ] Repository ingestion
- [ ] Repository structure analysis
- [ ] Code/document retrieval
- [ ] RAG pipeline
- [ ] LangChain integration
- [ ] LangGraph orchestration
- [ ] MCP integration
- [ ] Browser QA
- [ ] Bug investigation
- [ ] Human-in-the-loop fixes
- [ ] Automated verification

## Tech Stack

Python  
LangChain  
LangGraph  
Langflow  
MCP  
Playwright  
RAG  
Vector Database  
LLMs

## Render deployment

Build command:

```text
pip install -r requirements-render.txt && npm ci --prefix frontend && npm run build --prefix frontend
```

Start command:

```text
uvicorn app.api:app --host 0.0.0.0 --port $PORT --workers 1
```

Required Render environment variables are `APP_ENV=production`, `DATABASE_URL`,
`GROQ_API_KEY`, `GOOGLE_CLIENT_ID`, `REPOPILOT_AUTH_SECRET`, `APP_ORIGIN`, and
`REPOPILOT_COOKIE_SECURE=true`. Set `APP_ORIGIN` to the exact Render service
origin, for example `https://repopilot.example.onrender.com`.

Add that same origin in Google Cloud Console under Authorized JavaScript
origins. This application uses Google Identity Services credential posting;
it does not use a redirect URI.

Neon PostgreSQL is the source of truth for indexed vectors. Repository clones
created by indexing are stored under the local `repos/` directory, which is
ephemeral on Render and is not a persistent deployment volume.
