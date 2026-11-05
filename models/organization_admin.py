"""Organisation administrator model
====================================

Organisation administrators can log into their organisation's
dashboard and manage the users and licences belonging to their own
organisation. They have limited privileges compared to super
administrators and cannot see or modify data belonging to other
organisations.
"""

from datetime import datetime, timezone

from extensions import db


class OrganizationAdmin(db.Model):
    __tablename__ = "organization_admins"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def __repr__(self) -> str:
        return f"<OrgAdmin {self.email}>"