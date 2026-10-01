# Quick Setup Guide

## Full Docker Run

1. Copy `backend/.env.example` to `backend/.env`.
2. Fill `GEMINI_API_KEY`, `SECRET_KEY`, and Google OAuth values if sign-in is needed.
3. Start Docker Desktop.
4. Run:

```bash
docker compose up --build
```

Open the Docker app at `http://localhost:3001`. The Docker backend is available at `http://localhost:8002`.

The Docker stack includes frontend, backend, Redis, Letta, and Letta Postgres. It uses the MySQL and Ollama already running on your machine at `localhost:3306` and `localhost:11434`.

## Local Backend Run

For native development, run:

```bash
./start.sh --frontend
```

This starts the infrastructure containers, uses `backend/venv`, initializes MySQL, starts FastAPI on `http://localhost:8000`, and optionally starts Next.js on `http://localhost:3000`.

## Useful Checks

```bash
backend/venv/bin/python -m pytest backend/tests
npm --prefix frontend run build
docker compose config -q
```
