"""
TruthShield — Enterprise Workspace, API Keys, RBAC, and Audit Logs Tests
Direct calls to endpoint functions to bypass Starlette TestClient environment bugs.
"""
import os
import sys
import uuid
import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.db import Base, User, Organization, OrganizationMember, APIKey, AuditLog
from backend.api.auth import CurrentUser
from backend.services.auth_service import AuthService
from backend.services.analytics_service import AnalyticsService

# Create isolated sqlite test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./truthshield_test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./truthshield_test.db"):
        try:
            os.remove("./truthshield_test.db")
        except Exception:
            pass

@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

# Mock user credentials
MOCK_USER_ID = uuid.uuid4()
MOCK_USER_EMAIL = "admin-test@truthshield.com"


# ═══════════════════════════════════════════════
# Test Service Layer (Direct CRUD / RBAC)
# ═══════════════════════════════════════════════

def test_auth_service_organization_flow(db_session):
    # Setup test users
    admin_user = User(id=MOCK_USER_ID, email=MOCK_USER_EMAIL)
    member_user = User(id=uuid.uuid4(), email="member-test@truthshield.com")
    db_session.add(admin_user)
    db_session.add(member_user)
    db_session.commit()
    
    # Create Organization
    org = AuthService.create_organization(db_session, "TruthShield Org", admin_user.id)
    assert org.id is not None
    assert org.name == "TruthShield Org"
    
    # Verify Admin role was set automatically
    role = AuthService.check_user_role(db_session, org.id, admin_user.id)
    assert role == "Admin"
    
    # Invite a member
    member_record = AuthService.invite_member(
        db_session, org.id, member_user.email, "Member", admin_user.id
    )
    assert member_record is not None
    assert member_record.role == "Member"
    
    # Check roles
    assert AuthService.check_user_role(db_session, org.id, member_user.id) == "Member"
    
    # List members
    members = AuthService.get_members(db_session, org.id)
    assert len(members) == 2
    emails = [email for _, email in members]
    assert "admin-test@truthshield.com" in emails
    assert "member-test@truthshield.com" in emails


def test_auth_service_api_key_lifecycle(db_session):
    # Setup organization
    org = AuthService.create_organization(db_session, "API Org", MOCK_USER_ID)
    
    # Generate API key
    key_record, raw_key = AuthService.generate_api_key(
        db_session, org.id, "Prod Key", MOCK_USER_ID
    )
    assert raw_key.startswith("ts_live_")
    assert key_record.is_active is True
    
    # Validate API key
    validated_key = AuthService.validate_api_key(db_session, raw_key)
    assert validated_key is not None
    assert validated_key.id == key_record.id
    
    # List API keys
    keys = AuthService.list_api_keys(db_session, org.id)
    assert len(keys) == 1
    assert keys[0].label == "Prod Key"
    
    # Revoke API key
    success = AuthService.revoke_api_key(db_session, key_record.id, MOCK_USER_ID)
    assert success is True
    
    # Key should now be invalid
    assert AuthService.validate_api_key(db_session, raw_key) is None
    assert len(AuthService.list_api_keys(db_session, org.id)) == 0


def test_auth_service_audit_logs(db_session):
    org = AuthService.create_organization(db_session, "Audit Org", MOCK_USER_ID)
    
    # Logging an action
    AuthService.log_action(
        db_session, org.id, MOCK_USER_ID, "threat_level_changed", {"level": "CRITICAL"}
    )
    
    # Retrieve audit logs
    logs = AuthService.get_audit_logs(db_session, org.id)
    assert len(logs) >= 2
    actions = [log.action for log, _ in logs]
    assert "workspace_created" in actions
    assert "threat_level_changed" in actions


# ═══════════════════════════════════════════════
# Test API Routes (Direct Function Invocations)
# ═══════════════════════════════════════════════

def test_api_organizations_endpoints(db_session):
    from backend.api.routes import create_organization, list_organizations, invite_member, list_members
    
    # Add mock user to database
    admin_user = User(id=MOCK_USER_ID, email=MOCK_USER_EMAIL)
    db_session.add(admin_user)
    db_session.commit()
    
    current_user = CurrentUser(id=str(MOCK_USER_ID), email=MOCK_USER_EMAIL)
    
    # POST /organizations
    res = asyncio.run(create_organization(data={"name": "Cyber Defense Corp"}, current_user=current_user, db=db_session))
    assert "id" in res
    assert res["name"] == "Cyber Defense Corp"
    org_id = res["id"]
    
    # GET /organizations
    orgs_list = asyncio.run(list_organizations(current_user=current_user, db=db_session))
    assert len(orgs_list) == 1
    assert orgs_list[0]["name"] == "Cyber Defense Corp"
    assert orgs_list[0]["role"] == "Admin"
    
    # POST /organizations/{id}/invite
    invite_res = asyncio.run(invite_member(
        org_id=org_id,
        data={"email": "new-hire@truthshield.com", "role": "Viewer"},
        current_user=current_user,
        db=db_session
    ))
    assert invite_res["status"] == "ok"
    
    # GET /organizations/{id}/members
    members_list = asyncio.run(list_members(org_id=org_id, current_user=current_user, db=db_session))
    assert len(members_list) == 2
    emails = [m["email"] for m in members_list]
    assert "admin-test@truthshield.com" in emails
    assert "new-hire@truthshield.com" in emails


def test_api_keys_and_audit_logs_endpoints(db_session):
    from backend.api.routes import create_api_key, list_api_keys, revoke_api_key, get_audit_logs
    
    # Add mock user to database
    admin_user = User(id=MOCK_USER_ID, email=MOCK_USER_EMAIL)
    db_session.add(admin_user)
    db_session.commit()
    
    org = AuthService.create_organization(db_session, "Logistics Security", MOCK_USER_ID)
    org_id = str(org.id)
    current_user = CurrentUser(id=str(MOCK_USER_ID), email=MOCK_USER_EMAIL)
    
    # POST /organizations/{org_id}/apikeys
    key_res = asyncio.run(create_api_key(org_id=org_id, data={"label": "CI/CD Key"}, current_user=current_user, db=db_session))
    assert "api_key" in key_res
    assert key_res["label"] == "CI/CD Key"
    key_id = key_res["id"]
    
    # GET /organizations/{org_id}/apikeys
    keys_list = asyncio.run(list_api_keys(org_id=org_id, current_user=current_user, db=db_session))
    assert len(keys_list) == 1
    assert keys_list[0]["label"] == "CI/CD Key"
    
    # GET /organizations/{org_id}/audit-logs
    audit_logs = asyncio.run(get_audit_logs(org_id=org_id, current_user=current_user, db=db_session))
    assert len(audit_logs) >= 2
    actions = [log["action"] for log in audit_logs]
    assert "workspace_created" in actions
    assert "api_key_created" in actions
    
    # DELETE /apikeys/{key_id} (Revoke)
    revoke_res = asyncio.run(revoke_api_key(key_id=key_id, current_user=current_user, db=db_session))
    assert revoke_res["status"] == "ok"
    
    # Key should be gone
    keys_list2 = asyncio.run(list_api_keys(org_id=org_id, current_user=current_user, db=db_session))
    assert len(keys_list2) == 0


def test_threat_telemetry_endpoint(db_session):
    from backend.api.routes import get_realtime_threats
    
    # GET /realtime/threats
    threats = asyncio.run(get_realtime_threats(db=db_session))
    assert len(threats) > 0
    assert "claim" in threats[0]
    assert "lat" in threats[0]
    assert "lng" in threats[0]
    assert "severity" in threats[0]


def test_analyze_with_api_key_auth(db_session):
    from fastapi import BackgroundTasks
    from backend.api.routes import analyze_content
    from unittest.mock import patch
    from backend.models.schemas import AnalysisReport, CredibilityScore, Language, ContentType
    
    # Setup test DB user and org
    user = User(id=MOCK_USER_ID, email=MOCK_USER_EMAIL)
    org = AuthService.create_organization(db_session, "Gateway Org", user.id)
    db_session.add(user)
    db_session.commit()
    
    # Generate API key
    key_record, raw_key = AuthService.generate_api_key(db_session, org.id, "Gateway Key", user.id)
    
    # Setup current user context simulating API Key authorization
    api_key_user = CurrentUser(id=str(user.id), email=user.email, org_id=str(org.id))
    
    # Mock report to return
    mock_report = AnalysisReport(
        id="mock-report-id-123",
        content_type=ContentType.TEXT,
        original_text="Water boils at 100 degrees Celsius.",
        language=Language.EN,
        credibility=CredibilityScore(
            trust_score=95,
            verdict="TRUE",
            confidence_band="HIGH"
        ),
        processing_time_seconds=0.1,
        risk_factors=[]
    )
    
    async def mock_execute(*args, **kwargs):
        return mock_report
        
    # Perform analyze request with API Key auth context
    bg_tasks = BackgroundTasks()
    with patch("backend.pipeline.decision_pipeline.DecisionPipeline.execute", new=mock_execute):
        report = asyncio.run(analyze_content(
            background_tasks=bg_tasks,
            text="Water boils at 100 degrees Celsius.",
            lang="en",
            db=db_session,
            current_user=api_key_user
        ))
    
    assert report.original_text == "Water boils at 100 degrees Celsius."
    
    # Verify "analyze_created" was logged to audit trail
    logs = AuthService.get_audit_logs(db_session, org.id)
    actions = [log.action for log, _ in logs]
    assert "analyze_created" in actions

