"""License model
================

Represents a software licence key assigned to a specific user.
Licences have a status which controls whether activation and
validation are permitted and a validity period defined by start and
expiry dates. A licence may allow activation on multiple devices up to
``max_devices``.  Licence keys are generated using the helper in
``utils/license_utils.py``.
"""

from datetime import datetime, date, timezone

from extensions import db


class License(db.Model):
    __tablename__ = "licenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    key = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(db.String(50), default="active")  # active, expired, suspended, revoked
    start_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    max_devices = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    # Relationships
    devices = db.relationship("Device", backref="license", lazy=True)
    logs = db.relationship("UsageLog", backref="license", lazy=True)

    @property
    def is_active(self) -> bool:
        """Return True if the licence is currently active and not expired."""
        if self.status not in ("active", "renewed"):
            return False
        if self.expiry_date and date.today() > self.expiry_date:
            return False
        return True

    def __repr__(self) -> str:
        return f"<License {self.key} for user {self.user_id}>"