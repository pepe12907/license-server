"""Organization model
=====================

Represents a company or customer that purchases licences. Each
organisation can have multiple users and one or more organisation
administrators.  Organisations can be deactivated without deleting
their data, preventing all associated licences and users from
authenticating while retaining historical records.
"""

from datetime import datetime, timezone

from extensions import db


class Organization(db.Model):
    __tablename__ = "organizations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(255))
    contact_email = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)

    dashboard_token = db.Column(db.String(128), unique=True, nullable=True)
    dashboard_enabled = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    users = db.relationship("User", backref="organization", lazy=True)
    organization_admins = db.relationship(
        "OrganizationAdmin", backref="organization", lazy=True
    )
    devices = db.relationship("Device", backref="organization", lazy=True)
    # Note: licences are associated via the ``User`` model. To query
    # licences for an organisation join ``License`` through ``User``.

    def __repr__(self) -> str:
        return f"<Org {self.name}>"