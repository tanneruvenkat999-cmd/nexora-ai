import httpx
from .config import settings

AGENTS = {
    "project_manager": "Break requirements into deliverables, milestones, dependencies, and acceptance criteria.",
    "software_architect": "Design architecture, interfaces, tradeoffs, and a deployment topology.",
    "frontend_developer": "Write usable, accessible frontend source code and integration instructions.",
    "backend_developer": "Write backend APIs with validation, authentication considerations, and error handling.",
    "fullstack_engineer": "Integrate frontend and backend, resolve contracts, and provide integration code.",
    "uiux_designer": "Create UX flows, accessibility guidance, component specifications and visual design tokens.",
    "database_engineer": "Design relational schemas, migrations, indexes, and safe data access patterns.",
    "aiml_engineer": "Design and implement AI features with evaluation and safety considerations.",
    "mobile_developer": "Build cross-platform mobile features with real API integration.",
    "qa_engineer": "Produce executable tests, test plans, and edge cases.",
    "security_engineer": "Threat model and review authorization, injection, dependencies, and secrets.",
    "devops_engineer": "Prepare reproducible Docker, CI/CD, deployment, rollback and monitoring guidance.",
    "code_reviewer": "Review source for correctness, security, readability, and concrete improvements.",
    "documentation_agent": "Write accurate setup, API, operational and user documentation.",
    "maintenance_agent": "Diagnose defects and propose regression-tested patches and operational remediation.",
}

class AgentError(Exception): pass

async def run_agent(agent: str, brief: str, instruction: str) -> str:
    if agent not in AGENTS:
        raise AgentError("Unknown agent")
    if not settings.openai_api_key:
        raise AgentError("OPENAI_API_KEY not configured; no AI task was executed")
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "You are the NEXORA AI " + agent + ". " + AGENTS[agent] + " Produce concrete, verifiable work. Do not claim code was executed or deployed. If requirements are missing, state assumptions. Never expose credentials."},
            {"role": "user", "content": "Project brief:\n" + brief[:15000] + "\n\nApproved task:\n" + instruction[:15000]},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": "Bearer " + settings.openai_api_key}, json=payload)
            r.raise_for_status()
            result = r.json()["choices"][0]["message"]["content"]
            if not result: raise AgentError("Model returned no content")
            return result
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        raise AgentError(f"Model request failed: {type(exc).__name__}") from exc
