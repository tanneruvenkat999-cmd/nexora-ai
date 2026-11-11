# NEXORA AI — Multi-Agent Software Agency

A FastAPI + PostgreSQL platform with a web dashboard, 15 specialized AI roles, project and client management, audit events, and **mandatory admin approval before AI execution**.

## Features
- Administrator and client login, signed expiring bearer tokens, salted PBKDF2 password hashing
- Client-isolated projects and tasks
- 15 specialized AI agent profiles
- Approval and rejection gates, real model requests after approval
- Dashboard at `/`; health endpoint `/health`; API documentation `/docs`
- PostgreSQL for production, SQLite for local development, automated API tests

## Deploy on Render without Docker
1. Connect this GitHub repository through **Render → New → Blueprint**.
2. Render detects `render.yaml`, creating a Python web service and PostgreSQL database.
3. Review paid hosting plans and costs before approving.
4. Provide `ADMIN_EMAIL`, a strong `ADMIN_PASSWORD` (12+ characters), and `OPENAI_API_KEY` as secret environment variables. Render auto-generates `JWT_SECRET` and wires the database URL.
5. Open the web service's assigned URL; verify `/health` returns `{"status":"ok"}`.
6. Sign in, create a client/project/task, approve and execute it. Valid API credentials and API billing are required for actual AI results.
7. If necessary, change `CORS_ORIGINS` to the real HTTPS hostname.

## Run locally
Python 3.12+:

```bash
python -m venv .venv
pip install -r requirements-dev.txt
# Copy .env.example to .env, configure secure admin + JWT values.
# For local SQLite set DATABASE_URL=sqlite:///./nexora.db
uvicorn app.main:app --reload
python -m pytest -q
```

## Security
Never commit `.env` or tokens. The dashboard stores the login token only in page memory. The web service contains no external repository write functionality. Before hosting paying customers, add login throttling, migrations, backup/restore, background queues, account recovery, monitoring, and a security review.

## Current limitations
These agents generate and store text. They **do not automatically modify repositories, run generated code, open pull requests, or deploy customer applications**. Tests simulate successful model responses; live API execution and Render deployment require separate verification. Admin execution is synchronous and not suitable for high throughput.

## Application endpoints
- `POST /auth/login`
- `GET /agents`
- `GET/POST /clients` (admin only)
- `GET/POST /projects`
- `GET/POST /projects/{project_id}/tasks`
- `POST /tasks/{task_id}/approve` / `reject` / `execute` (admin only)
- `GET /audit` (admin only)
- `GET /health`

## Billing
The provided Blueprint requests paid Render web and PostgreSQL plans. OpenAI API usage is billed separately.
