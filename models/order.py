"""Order model for one-time purchases."""

from datetime import datetime, timezone

from extensions import db


# Keep timestamps as naive UTC to match the existing database columns.
def _utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Order(db.Model):
    __tablename__="orders"

    id=db.Column(db.Integer,primary_key=True)
    customer_name=db.Column(db.String(255),nullable=False)
    customer_email=db.Column(db.String(255),nullable=False,index=True)
    product_code=db.Column(db.String(100),nullable=False)
    duration_days=db.Column(db.Integer,nullable=False)
    amount_minor=db.Column(db.Integer,nullable=False)
    currency=db.Column(db.String(3),nullable=False,default="ARS")
    status=db.Column(db.String(30),nullable=False,default="pending")
    payment_provider=db.Column(db.String(50),nullable=False,default="mercadopago")
    external_reference=db.Column(db.String(100),unique=True,nullable=False)
    provider_preference_id=db.Column(db.String(100),unique=True,nullable=True)
    provider_payment_id=db.Column(db.String(100),unique=True,nullable=True)
    license_id=db.Column(db.Integer,db.ForeignKey("licenses.id"),nullable=True)
    created_at=db.Column(db.DateTime,nullable=False,default=_utc_now)
    updated_at=db.Column(db.DateTime,nullable=False,default=_utc_now,onupdate=_utc_now)
    paid_at=db.Column(db.DateTime,nullable=True)
    email_sent_at=db.Column(db.DateTime,nullable=True)

    license=db.relationship("License",backref=db.backref("order",uselist=False))

    def __repr__(self):
        return f"<Order {self.external_reference} ({self.status})>"
