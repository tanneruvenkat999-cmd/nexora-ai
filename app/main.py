from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import Base, engine
from .models import User, Project, Task, Audit
from .auth import db_session, pwd, make_token, current_user
from .agents import AGENTS, run_agent, AgentError

@contextmanager
def next_session():
    from .db import SessionLocal
    with SessionLocal() as db:
        yield db

@asynccontextmanager
async def lifespan(app):
    if len(settings.jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET must be at least 32 characters")
    if not settings.admin_email or not settings.admin_password or len(settings.admin_password) < 12:
        raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters)")
    Base.metadata.create_all(bind=engine)
    with next_session() as db:
        if not db.scalar(select(User).where(User.email == settings.admin_email.lower())):
            db.add(User(email=settings.admin_email.lower(), password_hash=pwd.hash(settings.admin_password), role="admin"))
            db.commit()
    yield

app = FastAPI(title="NEXORA AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in settings.cors_origins.split(",")], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

class Login(BaseModel):
    email: EmailStr
    password: str

class NewClient(Login):
    pass

class NewProject(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    brief: str = Field(min_length=10, max_length=20000)
    owner_id: int | None = None

class NewTask(BaseModel):
    agent: str
    instruction: str = Field(min_length=10, max_length=20000)

@app.get("/")
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/auth/login")
def login(body: Login, db: Session = Depends(db_session)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not pwd.verify(body.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")
    return {"access_token": make_token(user), "role": user.role}

@app.post("/clients", status_code=201)
def create_client(body: NewClient, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email exists")
    if len(body.password) < 12:
        raise HTTPException(422, "Password must be at least 12 characters")
    client = User(email=body.email.lower(), password_hash=pwd.hash(body.password), role="client")
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"id": client.id, "email": client.email}

@app.get("/clients")
def clients(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return [{"id": c.id, "email": c.email} for c in db.scalars(select(User).where(User.role == "client")).all()]

@app.get("/agents")
def agents(user: User = Depends(current_user)):
    return [{"id": k, "description": v} for k, v in AGENTS.items()]

@app.post("/projects", status_code=201)
def create_project(body: NewProject, user: User = Depends(current_user), db: Session = Depends(db_session)):
    owner = body.owner_id if user.role == "admin" and body.owner_id is not None else user.id
    if not db.get(User, owner):
        raise HTTPException(404, "Owner not found")
    project = Project(owner_id=owner, name=body.name, brief=body.brief)
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "name": project.name, "owner_id": project.owner_id}

@app.get("/projects")
def projects(user: User = Depends(current_user), db: Session = Depends(db_session)):
    q = select(Project)
    if user.role != "admin":
        q = q.where(Project.owner_id == user.id)
    return [{"id": p.id, "name": p.name, "brief": p.brief, "owner_id": p.owner_id} for p in db.scalars(q).all()]

def get_project(project_id: int, user: User, db: Session):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    if user.role != "admin" and project.owner_id != user.id:
        raise HTTPException(403, "Forbidden")
    return project

@app.post("/projects/{project_id}/tasks", status_code=201)
def create_task(project_id: int, body: NewTask, user: User = Depends(current_user), db: Session = Depends(db_session)):
    get_project(project_id, user, db)
    if body.agent not in AGENTS:
        raise HTTPException(422, "Unknown agent")
    task = Task(project_id=project_id, agent=body.agent, instruction=body.instruction)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_view(task)

def task_view(t: Task):
    return {"id": t.id, "project_id": t.project_id, "agent": t.agent, "instruction": t.instruction, "status": t.status, "output": t.output, "error": t.error}

@app.get("/projects/{project_id}/tasks")
def tasks(project_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    get_project(project_id, user, db)
    return [task_view(t) for t in db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.id.desc())).all()]

@app.post("/tasks/{task_id}/approve")
def approve(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin approval required")
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status != "pending_approval":
        raise HTTPException(409, "Task is not pending approval")
    t.status = "approved"
    db.add(Audit(actor_id=user.id, task_id=t.id, action="approved"))
    db.commit()
    return task_view(t)

@app.post("/tasks/{task_id}/reject")
def reject(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status != "pending_approval":
        raise HTTPException(409, "Task is not pending approval")
    t.status = "rejected"
    db.add(Audit(actor_id=user.id, task_id=t.id, action="rejected"))
    db.commit()
    return task_view(t)

@app.post("/tasks/{task_id}/execute")
async def execute(task_id: int, user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    t = db.get(Task, task_id)
    if not t:
        raise HTTPException(404, "Task not found")
    if t.status != "approved":
        raise HTTPException(409, "Task must be approved")
    project = db.get(Project, t.project_id)
    t.status = "running"
    db.add(Audit(actor_id=user.id, task_id=t.id, action="started"))
    db.commit()
    try:
        t.output = await run_agent(t.agent, project.brief, t.instruction)
        t.status = "completed"
        t.error = None
    except AgentError as exc:
        t.status = "failed"
        t.error = str(exc)
    db.add(Audit(actor_id=user.id, task_id=t.id, action=t.status))
    db.commit()
    return task_view(t)

@app.get("/audit")
def audit(user: User = Depends(current_user), db: Session = Depends(db_session)):
    if user.role != "admin":
        raise HTTPException(403, "Admin only")
    return [{"id": e.id, "actor_id": e.actor_id, "task_id": e.task_id, "action": e.action, "created_at": e.created_at.isoformat()} for e in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100)).all()]
