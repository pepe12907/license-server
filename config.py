"""Application configuration."""

import os


class Config:
    SECRET_KEY=os.environ.get("SECRET_KEY","change-this-secret")
    db_url=os.environ.get("DATABASE_URL")
    if db_url and db_url.startswith("postgres://"):
        db_url=db_url.replace("postgres://","postgresql://",1)
    SQLALCHEMY_DATABASE_URI=db_url or f"sqlite:///{os.path.join(os.getcwd(),'license_server.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS=False
    ADMIN_EMAIL=os.environ.get("ADMIN_EMAIL","admin@example.com")
    ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD","admin123")
    API_SECRET_KEY=os.environ.get("API_SECRET_KEY","api-secret-key")
    OFFLINE_GRACE_MINUTES=int(os.environ.get("OFFLINE_GRACE_MINUTES",10))

    # Lemon Squeezy: keep test mode enabled until live credentials are configured.
    LEMONSQUEEZY_API_KEY=os.environ.get("LEMONSQUEEZY_API_KEY")
    LEMONSQUEEZY_STORE_ID=os.environ.get("LEMONSQUEEZY_STORE_ID")
    LEMONSQUEEZY_VARIANT_60=os.environ.get("LEMONSQUEEZY_VARIANT_60")
    LEMONSQUEEZY_VARIANT_120=os.environ.get("LEMONSQUEEZY_VARIANT_120")
    LEMONSQUEEZY_WEBHOOK_SECRET=os.environ.get("LEMONSQUEEZY_WEBHOOK_SECRET")
    LEMONSQUEEZY_TEST_MODE=os.environ.get("LEMONSQUEEZY_TEST_MODE","true").lower()=="true"

    # Resend and post-payment redirect.
    RESEND_API_KEY=os.environ.get("RESEND_API_KEY")
    RESEND_FROM_EMAIL=os.environ.get("RESEND_FROM_EMAIL")
    PAYMENT_SUCCESS_URL=os.environ.get("PAYMENT_SUCCESS_URL")
