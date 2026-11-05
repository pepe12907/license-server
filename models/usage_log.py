"""Usage log model
=================

Stores an immutable record of every activation and validation attempt
made by client applications. Logging this information assists with
auditing, troubleshooting and understanding how licences are used.
"""

from datetime import datetime, timezone

from extensions import db


class UsageLog(db.Model):
    __tablename__ = "usage_logs"

    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("licenses.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    system_id = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    app_version = db.Column(db.String(50), nullable=True)
    action = db.Column(db.String(20), nullable=False)
    result = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))


    def __repr__(self) -> str:
        return f"<UsageLog {self.action} {self.result} for licence {self.license_id}>"