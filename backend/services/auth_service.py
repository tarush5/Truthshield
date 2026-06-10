"""
TruthShield — Authentication, Workspace & RBAC Service
"""
import uuid
import secrets
import hashlib
import json
import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from backend.models.db import User, Organization, OrganizationMember, APIKey, AuditLog

logger = logging.getLogger(__name__)


class AuthService:
    """Service handling multi-tenant workspaces, API key credentials, RBAC, and audit trails."""

    @staticmethod
    def get_or_create_user(db: Session, email: str) -> User:
        """Fetch user by email, or auto-create them if not exists."""
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email)
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"User {email} auto-created.")
        return user

    @staticmethod
    def create_organization(db: Session, name: str, user_id: uuid.UUID) -> Organization:
        """Create a new Workspace and add the creator as Admin."""
        org = Organization(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)

        # Creator becomes admin
        member = OrganizationMember(
            org_id=org.id,
            user_id=user_id,
            role="Admin"
        )
        db.add(member)
        db.commit()

        AuthService.log_action(
            db, org.id, user_id, "workspace_created", {"name": name}
        )
        logger.info(f"Workspace '{name}' created by user {user_id}.")
        return org

    @staticmethod
    def invite_member(db: Session, org_id: uuid.UUID, email: str, role: str, actor_id: uuid.UUID) -> Optional[OrganizationMember]:
        """Invite a member by email, auto-creating a User record if necessary."""
        # Find or create user
        user = AuthService.get_or_create_user(db, email)

        # Check if already a member
        existing = db.query(OrganizationMember).filter(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user.id
        ).first()

        if existing:
            logger.warning(f"User {email} is already in workspace {org_id}.")
            return existing

        member = OrganizationMember(
            org_id=org_id,
            user_id=user.id,
            role=role
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        AuthService.log_action(
            db, org_id, actor_id, "member_invited", {"email": email, "role": role}
        )
        logger.info(f"User {email} invited as {role} to workspace {org_id}.")
        return member

    @staticmethod
    def get_members(db: Session, org_id: uuid.UUID) -> List[Tuple[OrganizationMember, str]]:
        """Retrieve workspace members with their email addresses."""
        results = db.query(OrganizationMember, User.email).join(
            User, OrganizationMember.user_id == User.id
        ).filter(OrganizationMember.org_id == org_id).all()
        return results

    @staticmethod
    def generate_api_key(db: Session, org_id: uuid.UUID, label: str, user_id: uuid.UUID) -> Tuple[APIKey, str]:
        """Generate a cryptographically secure API key and store its SHA-256 hash."""
        # Format: ts_live_[32 random hex characters]
        raw_key = f"ts_live_{secrets.token_hex(16)}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

        key_record = APIKey(
            org_id=org_id,
            key_hash=key_hash,
            label=label,
            created_by=user_id,
            is_active=True
        )
        db.add(key_record)
        db.commit()
        db.refresh(key_record)

        AuthService.log_action(
            db, org_id, user_id, "api_key_created", {"label": label}
        )
        logger.info(f"API Key '{label}' created for workspace {org_id}.")
        return key_record, raw_key

    @staticmethod
    def validate_api_key(db: Session, api_key: str) -> Optional[APIKey]:
        """Validate API key hash and return key record if valid and active."""
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key_record = db.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True
        ).first()
        return key_record

    @staticmethod
    def list_api_keys(db: Session, org_id: uuid.UUID) -> List[APIKey]:
        """List active API keys in workspace."""
        return db.query(APIKey).filter(
            APIKey.org_id == org_id,
            APIKey.is_active == True
        ).all()

    @staticmethod
    def revoke_api_key(db: Session, key_id: uuid.UUID, actor_id: uuid.UUID) -> bool:
        """Revoke / deactivate an API key."""
        key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
        if key_record:
            key_record.is_active = False
            db.commit()
            AuthService.log_action(
                db, key_record.org_id, actor_id, "api_key_revoked", {"label": key_record.label}
            )
            logger.info(f"API Key {key_id} revoked.")
            return True
        return False

    @staticmethod
    def log_action(db: Session, org_id: uuid.UUID, user_id: Optional[uuid.UUID], action: str, details: dict):
        """Write a new entry to the workspace audit trail."""
        log = AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            details=json.dumps(details)
        )
        db.add(log)
        db.commit()

    @staticmethod
    def get_audit_logs(db: Session, org_id: uuid.UUID) -> List[Tuple[AuditLog, Optional[str]]]:
        """Fetch audit log timeline for workspace."""
        results = db.query(AuditLog, User.email).outerjoin(
            User, AuditLog.user_id == User.id
        ).filter(AuditLog.org_id == org_id).order_by(
            AuditLog.created_at.desc()
        ).limit(100).all()
        return results

    @staticmethod
    def check_user_role(db: Session, org_id: uuid.UUID, user_id: uuid.UUID) -> Optional[str]:
        """Retrieve user role in workspace. Returns role string or None if not a member."""
        member = db.query(OrganizationMember).filter(
            OrganizationMember.org_id == org_id,
            OrganizationMember.user_id == user_id
        ).first()
        return member.role if member else None
