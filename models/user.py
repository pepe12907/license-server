"""User model
==============

Represents an end user who is assigned one or more licences under a
particular organisation. Users cannot log into the web interface but
their licences can be activated by the client application. Each user
belongs to exactly one organisation.
"""

from datetime import datetime, timezone

from extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    licenses = db.relationship("License", backref="user", lazy=True)
    devices = db.relationship("Device", backref="user", lazy=True)
    logs = db.relationship("UsageLog", backref="user", lazy=True)

    def __repr__(self) -> str:
        return f"<User {self.email}>"