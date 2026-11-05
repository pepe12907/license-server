import hashlib
import hmac
import json
from datetime import date

import pytest

from app import create_app
from extensions import db
from models import License, Order, Organization, User
import routes.payments as payments


SECRET="test-webhook-secret"


@pytest.fixture
def app():
    app=create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite://",
        LEMONSQUEEZY_WEBHOOK_SECRET=SECRET,
        LEMONSQUEEZY_STORE_ID="12345",
        LEMONSQUEEZY_VARIANT_60="6001",
        LEMONSQUEEZY_VARIANT_120="12001",
        LEMONSQUEEZY_TEST_MODE=True,
        LEMONSQUEEZY_API_KEY="test-api-key",
    )
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def create_order(app,duration_days=60,email="buyer@example.com"):
    with app.app_context():
        tx_order=Order(
            customer_name="Test Buyer",
            customer_email=email,
            product_code="throne",
            duration_days=duration_days,
            amount_minor=0,
            currency="USD",
            status="pending",
            payment_provider="lemonsqueezy",
            external_reference=f"order-{duration_days}-{email}",
        )
        db.session.add(tx_order)
        db.session.commit()
        return tx_order.external_reference


def send_webhook(client,tx_reference,event="order_created",status="paid",variant_id="6001"):
    tx_payload={
        "meta":{
            "event_name":event,
            "custom_data":{"order_reference":tx_reference},
        },
        "data":{
            "type":"orders",
            "id":"987654",
            "attributes":{
                "store_id":12345,
                "test_mode":True,
                "status":status,
                "total":1200,
                "currency":"USD",
                "user_email":"buyer@example.com",
                "user_name":"Test Buyer",
                "first_order_item":{"variant_id":variant_id},
                "created_at":"2026-11-05T12:00:00Z",
            },
        },
    }
    tx_raw=json.dumps(tx_payload).encode("utf-8")
    tx_signature=hmac.new(SECRET.encode("utf-8"),tx_raw,hashlib.sha256).hexdigest()
    return client.post(
        "/payments/webhook",
        data=tx_raw,
        content_type="application/json",
        headers={"X-Signature":tx_signature,"X-Event-Name":event},
    )


def test_paid_webhook_creates_one_license_and_sends_email(app,client,monkeypatch):
    tx_reference=create_order(app)
    ls_sent=[]
    monkeypatch.setattr(payments,"_send_license_email",lambda tx_order,tx_license:ls_sent.append(tx_license.key))

    tx_response=send_webhook(client,tx_reference)

    assert tx_response.status_code==200
    with app.app_context():
        tx_order=Order.query.filter_by(external_reference=tx_reference).one()
        assert tx_order.status=="paid"
        assert tx_order.license_id is not None
        assert tx_order.email_sent_at is not None
        assert License.query.count()==1
        assert User.query.count()==1
        assert Organization.query.count()==1
        assert tx_order.license.status=="active"
        assert (tx_order.license.expiry_date-tx_order.license.start_date).days==59
    assert len(ls_sent)==1


def test_repeated_paid_webhook_does_not_duplicate_license_or_email(app,client,monkeypatch):
    tx_reference=create_order(app)
    ls_sent=[]
    monkeypatch.setattr(payments,"_send_license_email",lambda tx_order,tx_license:ls_sent.append(tx_license.key))

    assert send_webhook(client,tx_reference).status_code==200
    assert send_webhook(client,tx_reference).status_code==200

    with app.app_context():
        tx_order=Order.query.filter_by(external_reference=tx_reference).one()
        assert License.query.count()==1
        assert tx_order.license_id==License.query.one().id
        assert tx_order.status=="paid"
    assert len(ls_sent)==1


def test_unpaid_order_does_not_create_license(app,client):
    tx_reference=create_order(app)

    tx_response=send_webhook(client,tx_reference,status="pending")

    assert tx_response.status_code==200
    with app.app_context():
        tx_order=Order.query.filter_by(external_reference=tx_reference).one()
        assert tx_order.status=="pending"
        assert tx_order.license_id is None
        assert License.query.count()==0


def test_wrong_variant_is_rejected(app,client):
    tx_reference=create_order(app)

    tx_response=send_webhook(client,tx_reference,variant_id="9999")

    assert tx_response.status_code==400
    with app.app_context():
        assert License.query.count()==0
        assert Order.query.filter_by(external_reference=tx_reference).one().license_id is None


def test_invalid_webhook_signature_is_rejected(app,client):
    tx_reference=create_order(app)
    tx_response=client.post(
        "/payments/webhook",
        data=json.dumps({"meta":{"custom_data":{"order_reference":tx_reference}}}),
        content_type="application/json",
        headers={"X-Signature":"invalid"},
    )
    assert tx_response.status_code==401


def test_failed_email_can_be_retried_without_new_license(app,client,monkeypatch):
    tx_reference=create_order(app)
    nr_attempts={"count":0}

    def send_email(tx_order,tx_license):
        nr_attempts["count"]+=1
        if nr_attempts["count"]==1:
            raise RuntimeError("Temporary Resend failure")

    monkeypatch.setattr(payments,"_send_license_email",send_email)

    assert send_webhook(client,tx_reference).status_code==500
    assert send_webhook(client,tx_reference).status_code==200

    with app.app_context():
        tx_order=Order.query.filter_by(external_reference=tx_reference).one()
        assert License.query.count()==1
        assert tx_order.status=="paid"
        assert tx_order.email_sent_at is not None
    assert nr_attempts["count"]==2


@pytest.mark.parametrize("duration_days,variant_id,expected_days",[(60,"6001",59),(120,"12001",119)])
def test_license_duration_matches_purchased_variant(app,client,monkeypatch,duration_days,variant_id,expected_days):
    tx_reference=create_order(app,duration_days=duration_days)
    monkeypatch.setattr(payments,"_send_license_email",lambda tx_order,tx_license:None)

    tx_response=send_webhook(client,tx_reference,variant_id=variant_id)

    assert tx_response.status_code==200
    with app.app_context():
        tx_license=Order.query.filter_by(external_reference=tx_reference).one().license
        assert tx_license.status=="active"
        assert (tx_license.expiry_date-tx_license.start_date).days==expected_days


def test_order_status_hides_license_until_payment(app,client,monkeypatch):
    tx_reference=create_order(app)

    tx_pending=client.get(f"/payments/order/{tx_reference}")
    assert tx_pending.status_code==200
    assert tx_pending.get_json()["status"]=="pending"
    assert "license_key" not in tx_pending.get_json()

    monkeypatch.setattr(payments,"_send_license_email",lambda tx_order,tx_license:None)
    assert send_webhook(client,tx_reference).status_code==200

    tx_paid=client.get(f"/payments/order/{tx_reference}")
    assert tx_paid.status_code==200
    assert tx_paid.get_json()["status"]=="paid"
    assert tx_paid.get_json()["license_key"]


def test_checkout_creates_pending_order_and_returns_provider_url(app,client,monkeypatch):
    app.config.update(
        LEMONSQUEEZY_STORE_ID="12345",
        LEMONSQUEEZY_VARIANT_60="6001",
        LEMONSQUEEZY_API_KEY="test-api-key",
    )
    ls_payloads=[]
    monkeypatch.setattr(
        payments,
        "_lemonsqueezy_request",
        lambda tx_payload:(ls_payloads.append(tx_payload) or {
            "data":{"id":"checkout-123","attributes":{"url":"https://checkout.example/test"}}
        }),
    )

    tx_response=client.post("/payments/checkout",json={
        "name":"Test Buyer",
        "email":"BUYER@example.com",
        "duration_days":60,
    })

    assert tx_response.status_code==200
    tx_data=tx_response.get_json()
    assert tx_data["checkout_url"]=="https://checkout.example/test"
    assert tx_data["order_reference"]
    with app.app_context():
        tx_order=Order.query.filter_by(external_reference=tx_data["order_reference"]).one()
        assert tx_order.status=="pending"
        assert tx_order.customer_email=="buyer@example.com"
        assert tx_order.provider_preference_id=="checkout-123"
    assert ls_payloads[0]["data"]["relationships"]["variant"]["data"]["id"]=="6001"


@pytest.mark.parametrize("duration_days",[30,90,180])
def test_checkout_rejects_unsupported_duration(client,duration_days):
    tx_response=client.post("/payments/checkout",json={
        "name":"Test Buyer",
        "email":"buyer@example.com",
        "duration_days":duration_days,
    })
    assert tx_response.status_code==400


def test_checkout_rejects_missing_provider_configuration(app,client):
    app.config["LEMONSQUEEZY_API_KEY"]=None
    tx_response=client.post("/payments/checkout",json={
        "name":"Test Buyer",
        "email":"buyer@example.com",
        "duration_days":60,
    })
    assert tx_response.status_code==503


def test_checkout_cors_allows_public_site_preflight(client):
    tx_response=client.options(
        "/payments/checkout",
        headers={
            "Origin":"https://mmovision.uk",
            "Access-Control-Request-Method":"POST",
            "Access-Control-Request-Headers":"content-type",
        },
    )
    assert tx_response.status_code==200
    assert tx_response.headers["Access-Control-Allow-Origin"]=="https://mmovision.uk"
    assert "POST" in tx_response.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in tx_response.headers["Access-Control-Allow-Headers"]


def test_checkout_cors_rejects_unlisted_origin(client):
    tx_response=client.options(
        "/payments/checkout",
        headers={
            "Origin":"https://example.com",
            "Access-Control-Request-Method":"POST",
        },
    )
    assert "Access-Control-Allow-Origin" not in tx_response.headers
