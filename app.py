"""Flask application entry point."""

import os

from flask import Flask
from flask_migrate import Migrate

from config import Config
from extensions import db
from models.admin import Admin
from utils.auth import generate_password_hash
from routes import admin_bp, org_bp, api_bp, payments_bp


def create_app():
    app=Flask(__name__,template_folder="templates",static_folder="static")
    app.config.from_object(Config)
    db.init_app(app)
    Migrate(app,db)

    @app.route("/health")
    def health():
        return {"status":"ok"},200

    app.register_blueprint(admin_bp)
    app.register_blueprint(org_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(payments_bp)
    return app


app=create_app()


@app.cli.command("create-admin")
def create_admin():
    admin_email=app.config.get("ADMIN_EMAIL")
    admin_password=app.config.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        print("ADMIN_EMAIL or ADMIN_PASSWORD is not configured.")
        return
    existing=Admin.query.filter_by(email=admin_email).first()
    if not existing:
        admin=Admin(email=admin_email,password_hash=generate_password_hash(admin_password))
        db.session.add(admin)
        db.session.commit()
        print("Administrator created.")
    else:
        print("Administrator already exists.")


if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
