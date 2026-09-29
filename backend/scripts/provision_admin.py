"""Run from backend: python -m scripts.provision_admin --email EMAIL.

Reads the password from stdin when piped, otherwise prompts without echoing.
Uses the configured DATABASE_URL. Never stores credentials in source files.
"""
import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from core.database import AsyncSessionLocal, engine
from core.security import hash_password
from modules.auth.models import Role, User, UserPreferences
from modules.audit import service as audit
from modules.auth import sessions


async def provision(email: str, password: str, name: str, promote_existing: bool = False) -> None:
    if len(password) < 8 or not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least eight characters and a number.")
    async with AsyncSessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email).with_for_update())
        if user and (user.deleted_at is not None or user.suspended_at is not None):
            raise ValueError("Account is deleted or suspended; restore it explicitly first.")
        if user and user.role != Role.admin and not promote_existing:
            raise ValueError("An existing customer uses this email; refusing to change their role.")
        now = datetime.now(timezone.utc)
        if user is None:
            user = User(email=email, full_name=name, role=Role.admin)
            db.add(user)
            user.password_hash = hash_password(password)
            await db.flush()
            db.add(UserPreferences(user_id=user.id))
        else:
            user.password_hash = hash_password(password)
            user.tokens_valid_after = now
            await sessions.revoke_other_sessions(db, user.id, None)
        user.has_password = True
        user.role = Role.admin
        user.email_verified = True
        user.email_verified_at = now
        user.onboarded_at = now
        audit.record(db, "admin.account_provisioned", actor_id=user.id, subject_id=user.id, source="operator_cli")
        await db.commit()
        print(f"Admin account provisioned: {email}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Clippit Administrator")
    parser.add_argument("--promote-existing", action="store_true", help="Explicitly promote an existing customer account; preserve its records.")
    args = parser.parse_args()
    password = getpass.getpass("Admin password: ") if sys.stdin.isatty() else sys.stdin.readline().rstrip("\r\n")
    try:
        await provision(args.email.strip(), password, args.name, args.promote_existing)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
