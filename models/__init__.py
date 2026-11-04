"""Model package
================

This package defines the SQLAlchemy models used by the application.
Importing this package will import all individual model modules so
that they can be referenced via ``models.Admin``, ``models.User``, etc.

The models rely on the shared ``db`` instance defined in
``license_server.extensions``.
"""

from .admin import Admin  # noqa: F401
from .organization import Organization  # noqa: F401
from .organization_admin import OrganizationAdmin  # noqa: F401
from .user import User  # noqa: F401
from .license import License  # noqa: F401
from .device import Device  # noqa: F401
from .usage_log import UsageLog  # noqa: F401
from .order import Order  # noqa: F401