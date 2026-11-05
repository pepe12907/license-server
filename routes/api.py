from datetime import datetime, date, timezone

from flask import Blueprint, request, jsonify, current_app

from extensions import db
from models.license import License
from models.device import Device
from models.usage_log import UsageLog

api_bp = Blueprint("api", __name__, url_prefix="/api")


def check_api_key():
    expected_key = current_app.config.get("API_SECRET_KEY")
    received_key = request.headers.get("X-API-KEY")

    if not expected_key:
        return True

    return received_key == expected_key


def get_client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def log_usage(
    action,
    result,
    reason=None,
    license_obj=None,
    system_id=None,
    app_version=None,
):
    log = UsageLog(
        license_id=license_obj.id if license_obj else None,
        user_id=license_obj.user_id if license_obj else None,
        organization_id=license_obj.user.organization_id if license_obj and license_obj.user else None,
        system_id=system_id,
        ip_address=get_client_ip(),
        app_version=app_version,
        action=action,
        result=result,
        reason=reason,
    )
    db.session.add(log)


def error_response(message, status_code=400, license_obj=None, system_id=None, app_version=None, action="validate"):
    log_usage(
        action=action,
        result="fail",
        reason=message,
        license_obj=license_obj,
        system_id=system_id,
        app_version=app_version,
    )
    db.session.commit()

    return jsonify({
        "success": False,
        "valid": False,
        "message": message
    }), status_code


def validate_license_base(license_obj):
    if not license_obj:
        return "License key not found"

    if license_obj.status != "active":
        return f"License is {license_obj.status}"

    if license_obj.expiry_date and date.today() > license_obj.expiry_date:
        license_obj.status = "expired"
        return "License has expired"

    user = license_obj.user
    if not user or not user.is_active:
        return "User is inactive"

    organization = user.organization
    if not organization or not organization.is_active:
        return "Organization is inactive"

    return None


@api_bp.route("/activate", methods=["POST"])
def activate_license():
    if not check_api_key():
        return jsonify({
            "success": False,
            "message": "Unauthorized API request"
        }), 401

    data = request.get_json(silent=True) or {}

    license_key = data.get("license_key")
    system_id = data.get("system_id")
    machine_name = data.get("machine_name")
    app_version = data.get("app_version")

    if not license_key or not system_id:
        return jsonify({
            "success": False,
            "message": "license_key and system_id are required"
        }), 400

    license_obj = License.query.filter_by(key=license_key).first()

    base_error = validate_license_base(license_obj)
    if base_error:
        return error_response(
            message=base_error,
            status_code=403,
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
            action="activate",
        )

    existing_device = Device.query.filter_by(
        license_id=license_obj.id,
        system_id=system_id,
    ).first()

    if existing_device:
        if not existing_device.is_active:
            return error_response(
                message="Device is deactivated",
                status_code=403,
                license_obj=license_obj,
                system_id=system_id,
                app_version=app_version,
                action="activate",
            )

        existing_device.last_check = datetime.now(timezone.utc).replace(tzinfo=None)
        existing_device.ip_address = get_client_ip()
        existing_device.app_version = app_version

        log_usage(
            action="activate",
            result="success",
            reason="Existing device revalidated",
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
        )
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Device already activated",
            "license_status": license_obj.status,
            "expiry_date": license_obj.expiry_date.isoformat() if license_obj.expiry_date else None,
            "devices_used": Device.query.filter_by(license_id=license_obj.id, is_active=True).count(),
            "max_devices": license_obj.max_devices,
        })

    active_device_count = Device.query.filter_by(
        license_id=license_obj.id,
        is_active=True,
    ).count()

    if active_device_count >= license_obj.max_devices:
        return error_response(
            message="Maximum device limit reached",
            status_code=403,
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
            action="activate",
        )

    new_device = Device(
        license_id=license_obj.id,
        user_id=license_obj.user_id,
        organization_id=license_obj.user.organization_id,
        system_id=system_id,
        machine_name=machine_name,
        activation_timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
        last_check=datetime.now(timezone.utc).replace(tzinfo=None),
        ip_address=get_client_ip(),
        app_version=app_version,
        is_active=True,
    )

    db.session.add(new_device)

    log_usage(
        action="activate",
        result="success",
        reason="New device activated",
        license_obj=license_obj,
        system_id=system_id,
        app_version=app_version,
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Activation successful",
        "license_status": license_obj.status,
        "expiry_date": license_obj.expiry_date.isoformat() if license_obj.expiry_date else None,
        "devices_used": active_device_count + 1,
        "max_devices": license_obj.max_devices,
        "offline_grace_minutes": current_app.config.get("OFFLINE_GRACE_MINUTES", 10),
    })


@api_bp.route("/validate", methods=["POST"])
def validate_license():
    if not check_api_key():
        return jsonify({
            "success": False,
            "valid": False,
            "message": "Unauthorized API request"
        }), 401

    data = request.get_json(silent=True) or {}

    license_key = data.get("license_key")
    system_id = data.get("system_id")
    app_version = data.get("app_version")

    if not license_key or not system_id:
        return jsonify({
            "success": False,
            "valid": False,
            "message": "license_key and system_id are required"
        }), 400

    license_obj = License.query.filter_by(key=license_key).first()

    base_error = validate_license_base(license_obj)
    if base_error:
        return error_response(
            message=base_error,
            status_code=403,
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
            action="validate",
        )

    device = Device.query.filter_by(
        license_id=license_obj.id,
        system_id=system_id,
        is_active=True,
    ).first()

    if not device:
        return error_response(
            message="This device is not activated for this license",
            status_code=403,
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
            action="validate",
        )

    device.last_check = datetime.now(timezone.utc).replace(tzinfo=None)
    device.ip_address = get_client_ip()
    device.app_version = app_version

    log_usage(
        action="validate",
        result="success",
        reason="License validated",
        license_obj=license_obj,
        system_id=system_id,
        app_version=app_version,
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "valid": True,
        "message": "License valid",
        "license_status": license_obj.status,
        "expiry_date": license_obj.expiry_date.isoformat() if license_obj.expiry_date else None,
        "offline_grace_minutes": current_app.config.get("OFFLINE_GRACE_MINUTES", 10),
    })


@api_bp.route("/deactivate", methods=["POST"])
def deactivate_device():
    if not check_api_key():
        return jsonify({
            "success": False,
            "message": "Unauthorized API request"
        }), 401

    data = request.get_json(silent=True) or {}

    license_key = data.get("license_key")
    system_id = data.get("system_id")
    app_version = data.get("app_version")

    if not license_key or not system_id:
        return jsonify({
            "success": False,
            "message": "license_key and system_id are required"
        }), 400

    license_obj = License.query.filter_by(key=license_key).first()

    if not license_obj:
        return error_response(
            message="License key not found",
            status_code=404,
            system_id=system_id,
            app_version=app_version,
            action="deactivate",
        )

    device = Device.query.filter_by(
        license_id=license_obj.id,
        system_id=system_id,
    ).first()

    if not device:
        return error_response(
            message="Device not found",
            status_code=404,
            license_obj=license_obj,
            system_id=system_id,
            app_version=app_version,
            action="deactivate",
        )

    device.is_active = False
    device.last_check = datetime.now(timezone.utc).replace(tzinfo=None)

    log_usage(
        action="deactivate",
        result="success",
        reason="Device deactivated",
        license_obj=license_obj,
        system_id=system_id,
        app_version=app_version,
    )

    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Device deactivated successfully"
    })

@api_bp.route("/health", methods=["GET"])
def health():
    return {
        "success": True,
        "status": "healthy"
    }, 200