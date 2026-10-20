"""
Account deletion: everything a user created goes with them.

Deleting the `users` row alone would not do that. Investigations and 1.x
reports keep a nullable owner (`ON DELETE SET NULL`), and an unowned 1.x
report is readable by anyone holding its id, so a bare delete would have
left a deleted user's submissions behind and made some of them public.
Uploaded files live outside the database and need deleting explicitly.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


class AccountDeletionBlocked(Exception):
    """The account owns a workspace other people still use."""


def delete_account(session: Session, user) -> dict:
    """Delete `user` and everything they own. Returns counts for the application log."""
    from truthshield.infra.models import (
        Investigation, Organization, OrganizationMember, Report,
    )
    from truthshield.investigations import service
    from truthshield.services.auth import Principal

    owned_orgs = session.query(Organization).filter(Organization.owner_id == user.id).all()
    for org in owned_orgs:
        others = (
            session.query(OrganizationMember)
            .filter(OrganizationMember.org_id == org.id, OrganizationMember.user_id != user.id)
            .count()
        )
        if others:
            raise AccountDeletionBlocked(
                f"You own the workspace '{org.name}', which other people use. "
                "Transfer it or remove its members first."
            )

    principal = Principal(user_id=user.id, email=user.email, role=user.role or "USER")

    # Investigations one by one, so their stored files are removed too.
    investigations = session.query(Investigation).filter(Investigation.user_id == user.id).all()
    for inv in investigations:
        service.delete(session, principal, inv)

    reports = session.query(Report).filter(Report.user_id == user.id).delete(synchronize_session=False)

    for org in owned_orgs:
        session.delete(org)  # cascades its members, API keys and remaining reports
    session.flush()

    session.delete(user)  # cascades refresh tokens and memberships
    session.commit()
    return {"investigations": len(investigations), "reports": reports,
            "workspaces": len(owned_orgs)}
