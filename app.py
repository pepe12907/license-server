"""Flask application entry point
===============================

Defines the application factory which instantiates and configures
Flask. It initialises the database, registers blueprints and creates
a super administrator on the first run using the credentials set via
environment variables.

The module exposes a global ``app`` instance so that `gunicorn
app:app` will work out of the box. When running under Flask's
development server you can also set ``FLASK_APP=app.py``.
"""

import os
from datetime import datetime

from sqlalchemy import inspect

from flask import Flask
from flask_migrate import Migrate

from config import Config
from extensions import db
from models.admin import Admin
from utils.auth import generate_password_hash
from routes import admin_bp, org_bp, api_bp


def create_app() -> Flask:
    """Application factory.

    Creates and configures a new Flask application. The app
    configuration is loaded from the ``Config`` class. It initialises
    the SQLAlchemy extension, runs database migrations and registers
    blueprints for the admin interface, organisation interface and API.

    Returns:
        A configured Flask application.
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    # Register blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(org_bp)
    app.register_blueprint(api_bp)



    return app


# Create the application instance for gunicorn
app = create_app()
@app.cli.command("create-admin")
def create_admin():
    """Create the initial administrator if it does not exist."""
    admin_email = app.config.get("ADMIN_EMAIL")
    admin_password = app.config.get("ADMIN_PASSWORD")

    if not admin_email or not admin_password:
        print("ADMIN_EMAIL or ADMIN_PASSWORD is not configured.")
        return

    existing = Admin.query.filter_by(email=admin_email).first()

    if not existing:
        admin = Admin(
            email=admin_email,
            password_hash=generate_password_hash(admin_password)
        )
        db.session.add(admin)
        db.session.commit()
        print("Administrator created.")
    else:
        print("Administrator already exists.")

if __name__ == "__main__":
    # When running directly, start the development server
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
