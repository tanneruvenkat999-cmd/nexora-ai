import os
from pathlib import Path
Path("test_nexora.sqlite3").unlink(missing_ok=True)
os.environ["DATABASE_URL"] = "sqlite:///./test_nexora.sqlite3"
os.environ["JWT_SECRET"] = "test-secret-32-characters-minimum-12345"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "test-password-12345"
from fastapi.testclient import TestClient
from app.main import app
from app.agents import AGENTS

def test_15_agents():
    assert len(AGENTS) == 15

def test_approval_and_client_isolation():
    with TestClient(app) as c:
        login = c.post('/auth/login', json={'email':'admin@example.com','password':'test-password-12345'})
        assert login.status_code == 200
        admin = {'Authorization': 'Bearer '+login.json()['access_token']}
        client = c.post('/clients',headers=admin,json={'email':'client1@example.com','password':'client-password-123'}).json()
        project = c.post('/projects',headers=admin,json={'name':'Demo','brief':'Build a real customer dashboard','owner_id':client['id']})
        assert project.status_code == 201
        pid=project.json()['id']
        task=c.post(f'/projects/{pid}/tasks',headers=admin,json={'agent':'frontend_developer','instruction':'Build a responsive customer dashboard'})
        assert task.status_code == 201
        tid=task.json()['id']
        assert c.post(f'/tasks/{tid}/execute',headers=admin).status_code == 409
        assert c.post(f'/tasks/{tid}/approve',headers=admin).status_code == 200
        assert c.post(f'/tasks/{tid}/approve',headers=admin).status_code == 409
        result=c.post(f'/tasks/{tid}/execute',headers=admin)
        assert result.status_code == 200
        assert result.json()['status']=='failed' and 'OPENAI_API_KEY' in result.json()['error']
        c.post('/clients',headers=admin,json={'email':'client2@example.com','password':'client-password-123'})
        other_token=c.post('/auth/login',json={'email':'client2@example.com','password':'client-password-123'}).json()['access_token']
        other_headers={'Authorization':'Bearer '+other_token}
        assert c.get(f'/projects/{pid}/tasks',headers=other_headers).status_code == 403
        assert c.post(f'/tasks/{tid}/approve',headers=other_headers).status_code == 403

def test_successful_approved_execution(monkeypatch):
    async def fake_agent(agent, brief, instruction):
        assert agent == 'qa_engineer'
        assert 'customer dashboard' in brief
        return 'Verified synthetic test response (model call replaced in test)'
    monkeypatch.setattr('app.main.run_agent', fake_agent)
    with TestClient(app) as c:
        login = c.post('/auth/login', json={'email': 'admin@example.com', 'password': 'test-password-12345'})
        assert login.status_code == 200
        headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
        project = c.post('/projects', headers=headers, json={'name':'QA project', 'brief':'Build a real customer dashboard'})
        assert project.status_code == 201
        task = c.post(f"/projects/{project.json()['id']}/tasks", headers=headers, json={'agent':'qa_engineer','instruction':'Write integration tests for dashboard'})
        assert task.status_code == 201
        tid = task.json()['id']
        assert c.post(f'/tasks/{tid}/approve', headers=headers).status_code == 200
        executed = c.post(f'/tasks/{tid}/execute', headers=headers)
        assert executed.status_code == 200
        assert executed.json()['status'] == 'completed'
        assert 'synthetic test response' in executed.json()['output']
        assert c.post(f'/tasks/{tid}/execute', headers=headers).status_code == 409
        assert c.get('/audit', headers=headers).status_code == 200

def test_invalid_token_and_password():
    with TestClient(app) as c:
        assert c.post('/auth/login', json={'email':'admin@example.com','password':'wrong-password'}).status_code == 401
        assert c.get('/projects', headers={'Authorization':'Bearer invalid.token.signature'}).status_code == 401
        assert c.get('/projects').status_code == 401
