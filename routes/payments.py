"""Lemon Squeezy checkout and webhook integration."""

import hashlib
import hmac
import html
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from sqlalchemy import text

from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models.license import License
from models.order import Order
from models.user import User
from utils.license_utils import generate_license_key

payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.after_request
def add_checkout_cors_headers(tx_response):
    # Allow the public MMOVision site to call checkout and order-status endpoints.
    tx_origin=request.headers.get("Origin")
    if tx_origin in ("https://mmovision.uk","https://www.mmovision.uk"):
        tx_response.headers["Access-Control-Allow-Origin"]=tx_origin
        tx_response.headers["Access-Control-Allow-Methods"]="GET, POST, OPTIONS"
        tx_response.headers["Access-Control-Allow-Headers"]="Content-Type"
        tx_response.headers["Vary"]="Origin"
    return tx_response


def _lemonsqueezy_request(tx_payload):
    tx_api_key=current_app.config.get("LEMONSQUEEZY_API_KEY")
    if not tx_api_key:
        raise RuntimeError("LEMONSQUEEZY_API_KEY is not configured")
    tx_request=Request(
        "https://api.lemonsqueezy.com/v1/checkouts",
        data=json.dumps(tx_payload).encode("utf-8"),
        headers={
            "Accept":"application/vnd.api+json",
            "Content-Type":"application/vnd.api+json",
            "Authorization":f"Bearer {tx_api_key}",
        },
        method="POST",
    )
    with urlopen(tx_request,timeout=20) as tx_response:
        return json.loads(tx_response.read().decode("utf-8"))


def _send_license_email(tx_order,tx_license):
    tx_api_key=current_app.config.get("RESEND_API_KEY")
    tx_from=current_app.config.get("RESEND_FROM_EMAIL")
    if not tx_api_key or not tx_from:
        raise RuntimeError("RESEND_API_KEY or RESEND_FROM_EMAIL is not configured")
    tx_name=html.escape(tx_order.customer_name)
    tx_key=html.escape(tx_license.key)
    tx_html=f"""
    <h2>Tu licencia de Throne está lista</h2>
    <p>Hola {tx_name},</p>
    <p>El pago fue confirmado. Esta es tu clave de licencia:</p>
    <p style="font-size:20px;font-weight:bold;letter-spacing:2px">{tx_key}</p>
    <p>Vencimiento: {tx_license.expiry_date.isoformat()}</p>
    <p>Guardá esta clave para activar Throne.</p>
    """
    tx_body=json.dumps({
        "from":tx_from,
        "to":[tx_order.customer_email],
        "subject":"Tu licencia de Throne",
        "html":tx_html,
    }).encode("utf-8")
    tx_request=Request(
        "https://api.resend.com/emails",
        data=tx_body,
        headers={
            "Authorization":f"Bearer {tx_api_key}",
            "Content-Type":"application/json",
            "User-Agent":"MmoVision-LicenseServer/1.0",
        },
        method="POST",
    )
    with urlopen(tx_request,timeout=20) as tx_response:
        return json.loads(tx_response.read().decode("utf-8"))


@payments_bp.route("/checkout",methods=["POST"])
def create_checkout():
    tx_data=request.get_json(silent=True) or {}
    tx_name=(tx_data.get("name") or "").strip()
    tx_email=(tx_data.get("email") or "").strip().lower()
    tx_duration=tx_data.get("duration_days")
    if not tx_name or len(tx_name)>255 or not tx_email or len(tx_email)>255 or "@" not in tx_email:
        return jsonify({"success":False,"message":"A valid name and email are required"}),400
    try:
        tx_duration=int(tx_duration)
    except (TypeError,ValueError):
        return jsonify({"success":False,"message":"duration_days must be 30, 60 or 120"}),400
    if tx_duration not in (30,60,120):
        return jsonify({"success":False,"message":"duration_days must be 60 or 120"}),400

    tx_variant_id=current_app.config.get(f"LEMONSQUEEZY_VARIANT_{tx_duration}")
    tx_store_id=current_app.config.get("LEMONSQUEEZY_STORE_ID")
    if not tx_variant_id or not tx_store_id or not current_app.config.get("LEMONSQUEEZY_API_KEY"):
        return jsonify({"success":False,"message":"Lemon Squeezy is not fully configured"}),503

    tx_reference=secrets.token_urlsafe(24)
    tx_order=Order(
        customer_name=tx_name,
        customer_email=tx_email,
        product_code="throne",
        duration_days=tx_duration,
        amount_minor=0,
        currency="USD",
        status="pending",
        payment_provider="lemonsqueezy",
        external_reference=tx_reference,
    )
    db.session.add(tx_order)
    db.session.commit()

    try:
        tx_variant_id=int(tx_variant_id)
    except (TypeError,ValueError):
        return jsonify({"success":False,"message":"Invalid Lemon Squeezy variant configuration"}),503

    tx_attributes={
        "checkout_data":{
            "name":tx_name,
            "email":tx_email,
            "custom":{"order_reference":tx_reference},
        },
        "product_options":{
            "enabled_variants":[int(tx_variant_id)],
        },
        "test_mode":current_app.config.get("LEMONSQUEEZY_TEST_MODE",True),
    }
    tx_success_url=current_app.config.get("PAYMENT_SUCCESS_URL")
    if tx_success_url:
        tx_attributes["product_options"]["redirect_url"]=f"{tx_success_url}?order={tx_reference}"

    tx_payload={
        "data":{
            "type":"checkouts",
            "attributes":tx_attributes,
            "relationships":{
                "store":{"data":{"type":"stores","id":str(tx_store_id)}},
                "variant":{"data":{"type":"variants","id":str(tx_variant_id)}},
            },
        },
    }
    try:
        tx_result=_lemonsqueezy_request(tx_payload)
        tx_checkout=tx_result["data"]
        tx_order.provider_preference_id=tx_checkout["id"]
        db.session.commit()
        return jsonify({
            "success":True,
            "checkout_url":tx_checkout["attributes"]["url"],
            "order_reference":tx_reference,
        }),200
    except (HTTPError,URLError,TimeoutError,RuntimeError,KeyError,ValueError) as tx_error:
        current_app.logger.exception("Lemon Squeezy checkout creation failed")
        tx_order.status="checkout_failed"
        db.session.commit()
        return jsonify({"success":False,"message":"Could not create checkout"}),502


@payments_bp.route("/order/<tx_reference>",methods=["GET"])
def get_order_status(tx_reference):
    tx_order=Order.query.filter_by(external_reference=tx_reference,payment_provider="lemonsqueezy").first()
    if not tx_order:
        return jsonify({"success":False,"message":"Order not found"}),404
    tx_result={"success":True,"status":tx_order.status}
    if tx_order.status=="paid" and tx_order.license:
        tx_result.update({
            "license_key":tx_order.license.key,
            "expiry_date":tx_order.license.expiry_date.isoformat() if tx_order.license.expiry_date else None,
            "email_sent":tx_order.email_sent_at is not None,
        })
    return jsonify(tx_result),200


@payments_bp.route("/webhook",methods=["POST"])
def lemonsqueezy_webhook():
    tx_secret=current_app.config.get("LEMONSQUEEZY_WEBHOOK_SECRET")
    tx_signature=request.headers.get("X-Signature","")
    tx_raw=request.get_data()
    if not tx_secret:
        current_app.logger.error("LEMONSQUEEZY_WEBHOOK_SECRET is not configured")
        return jsonify({"success":False}),503
    tx_digest=hmac.new(tx_secret.encode("utf-8"),tx_raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(tx_digest,tx_signature):
        return jsonify({"success":False,"message":"Invalid signature"}),401

    tx_payload=request.get_json(silent=True) or {}
    tx_event=(tx_payload.get("meta") or {}).get("event_name")
    tx_header_event=request.headers.get("X-Event-Name")
    if tx_header_event and tx_event and tx_header_event!=tx_event:
        return jsonify({"success":False,"message":"Event name mismatch"}),400
    tx_attributes=((tx_payload.get("data") or {}).get("attributes") or {})
    tx_custom=((tx_payload.get("meta") or {}).get("custom_data") or {})
    tx_reference=tx_custom.get("order_reference")
    if not tx_reference:
        return jsonify({"success":False,"message":"Missing order_reference"}),400

    tx_order=Order.query.filter_by(external_reference=tx_reference,payment_provider="lemonsqueezy").with_for_update().first()
    if not tx_order:
        return jsonify({"success":False,"message":"Order not found"}),404

    tx_store_id=current_app.config.get("LEMONSQUEEZY_STORE_ID")
    if tx_store_id and str(tx_attributes.get("store_id"))!=str(tx_store_id):
        return jsonify({"success":False,"message":"Unexpected store"}),400
    if "test_mode" in tx_attributes and bool(tx_attributes["test_mode"])!=bool(current_app.config.get("LEMONSQUEEZY_TEST_MODE",True)):
        return jsonify({"success":False,"message":"Unexpected test mode"}),400

    tx_provider_order_id=str((tx_payload.get("data") or {}).get("id") or "")
    if tx_event=="order_created":
        if tx_order.status in ("refunded","partial_refund","fraudulent"):
            return jsonify({"success":True,"ignored":True}),200
        tx_status=tx_attributes.get("status")
        tx_order.provider_payment_id=tx_provider_order_id or tx_order.provider_payment_id
        tx_order.amount_minor=int(Decimal(str(tx_attributes.get("total") or 0)))
        tx_order.currency=(tx_attributes.get("currency") or "USD")[:3]
        if tx_status!="paid":
            if tx_order.status!="paid":
                tx_order.status=tx_status or "pending"
                db.session.commit()
            return jsonify({"success":True}),200

        tx_item=tx_attributes.get("first_order_item") or {}
        tx_expected_variant=current_app.config.get(f"LEMONSQUEEZY_VARIANT_{tx_order.duration_days}")
        if not tx_expected_variant or str(tx_item.get("variant_id"))!=str(tx_expected_variant):
            return jsonify({"success":False,"message":"Unexpected product variant"}),400

        if not tx_order.license_id:
            tx_email=(tx_attributes.get("user_email") or tx_order.customer_email).strip().lower()
            tx_name=(tx_attributes.get("user_name") or tx_order.customer_name).strip()
            # Serialize purchases using the same email; a missing user row cannot be locked.
            if db.engine.dialect.name=="postgresql":
                db.session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:tx_email))"),{"tx_email":tx_email})
            tx_user=User.query.filter_by(email=tx_email).first()
            if not tx_user:
                tx_user=User(
                    organization_id=1,
                    name=tx_name,
                    email=tx_email,
                    is_active=True,
                )
                db.session.add(tx_user)
                db.session.flush()

            tx_purchase_date=date.today()
            tx_created_at=tx_attributes.get("created_at")
            if tx_created_at:
                try:
                    tx_purchase_date=datetime.fromisoformat(tx_created_at.replace("Z","+00:00")).astimezone(ZoneInfo("America/Argentina/Buenos_Aires")).date()
                except (ValueError,TypeError):
                    pass
            tx_license=License(
                user_id=tx_user.id,
                key=generate_license_key()[:16],
                status="active",
                start_date=tx_purchase_date,
                expiry_date=tx_purchase_date+timedelta(days=tx_order.duration_days-1),
                max_devices=1,
            )
            db.session.add(tx_license)
            db.session.flush()
            tx_order.license_id=tx_license.id
            tx_order.customer_name=tx_name
            tx_order.customer_email=tx_email
        tx_order.status="paid"
        tx_order.paid_at=datetime.now(timezone.utc).replace(tzinfo=None)
        db.session.commit()

        # Reacquire the order lock after committing the license.
        tx_order=Order.query.filter_by(id=tx_order.id).with_for_update().first()
        if tx_order.status=="paid" and tx_order.email_sent_at is None:
            try:
                _send_license_email(tx_order,tx_order.license)
                tx_order.email_sent_at=datetime.now(timezone.utc).replace(tzinfo=None)
                db.session.commit()
            except HTTPError as tx_error:
                tx_error_body=tx_error.read().decode("utf-8",errors="replace")
                db.session.rollback()
                current_app.logger.error("License email delivery failed: Resend HTTP %s: %s",tx_error.code,tx_error_body)
                return jsonify({"success":False,"message":"License email delivery failed"}),500
            except (URLError,TimeoutError,RuntimeError,ValueError):
                db.session.rollback()
                current_app.logger.exception("License email delivery failed")
                return jsonify({"success":False,"message":"License email delivery failed"}),500
        return jsonify({"success":True}),200

    if tx_event=="order_refunded":
        tx_order.status=tx_attributes.get("status") or ("refunded" if tx_attributes.get("refunded") else "partial_refund")
        if tx_order.license and tx_attributes.get("refunded"):
            tx_order.license.status="revoked"
        db.session.commit()
        return jsonify({"success":True}),200

    return jsonify({"success":True,"ignored":True}),200
