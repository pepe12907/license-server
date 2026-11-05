"""Device model
===============

Represents a physical or virtual machine on which a licence key has
been activated. Each device is associated with a licence, user and
organisation. Devices record identifying information such as system
ID, machine name, IP address and the app version. The `last_check`
field is updated whenever the client validates its licence with the
server.
"""

from datetime import datetime, timezone

from extensions import db


class Device(db.Model):
    __tablename__ = "devices"

    id = db.Column(db.Integer, primary_key=True)
    license_id = db.Column(db.Integer, db.ForeignKey("licenses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    system_id = db.Column(db.String(255), nullable=False)
    machine_name = db.Column(db.String(255), nullable=True)
    activation_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    last_check = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    app_version = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self) -> str:
        return f"<Device {self.system_id} for licence {self.license_id}>"