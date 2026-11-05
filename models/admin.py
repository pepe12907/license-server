"""Admin model
================

Defines the super administrator account which has full access to
manage the entire system. Only a small number of such accounts
should exist. Credentials are set via environment variables on
startup and hashed for storage.
"""

from datetime import datetime, timezone

from extensions import db


class Admin(db.Model):
    """Super administrator.

    Super administrators can log into the `/admin` section of the
    application and manage all organisations, users, licences and
    devices. The application automatically creates one admin on
    startup using the credentials specified in the environment.
    """

    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def __repr__(self) -> str:
        return f"<Admin {self.email}>"