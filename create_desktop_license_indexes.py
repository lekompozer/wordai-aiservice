"""
Create MongoDB indexes for desktop license collections.
Run once after deploying the Desktop License feature.

Usage (on server):
    docker cp create_desktop_license_indexes.py ai-chatbot-rag:/app/
    docker exec ai-chatbot-rag python3 /app/create_desktop_license_indexes.py
"""

import sys

sys.path.insert(0, "/app")

from src.database.db_manager import DBManager

db_manager = DBManager()
db = db_manager.db


def create_indexes():
    print("Creating indexes for desktop_licenses (individual) collection...")

    # Unique license_id
    db.desktop_licenses.create_index(
        "license_id", unique=True, name="license_id_unique"
    )
    print("  ✅ license_id (unique)")

    # One license per user
    db.desktop_licenses.create_index(
        "user_id", unique=True, name="user_id_unique"
    )
    print("  ✅ user_id (unique)")

    # Unique license key
    db.desktop_licenses.create_index(
        "license_key", unique=True, name="license_key_unique"
    )
    print("  ✅ license_key (unique)")

    # Active license lookup
    db.desktop_licenses.create_index(
        [("status", 1), ("expires_at", 1)], name="status_expires_at"
    )
    print("  ✅ (status, expires_at)")

    print("\nCreating indexes for enterprise_licenses collection...")

    # Unique enterprise_id
    db.enterprise_licenses.create_index(
        "enterprise_id", unique=True, name="enterprise_id_unique"
    )
    print("  ✅ enterprise_id (unique)")

    # Unique enterprise_key (used for public config fetch)
    db.enterprise_licenses.create_index(
        "enterprise_key", unique=True, name="enterprise_key_unique"
    )
    print("  ✅ enterprise_key (unique)")

    # Billing admin lookup (GET /enterprise/my)
    db.enterprise_licenses.create_index(
        "billing_admin_user_id", name="billing_admin_user_id"
    )
    print("  ✅ billing_admin_user_id")

    # Status + expiry for active license checks
    db.enterprise_licenses.create_index(
        [("status", 1), ("expires_at", 1)], name="status_expires_at"
    )
    print("  ✅ (status, expires_at)")

    print("\nCreating indexes for enterprise_license_users collection...")

    # Unique: one record per email per enterprise
    db.enterprise_license_users.create_index(
        [("enterprise_id", 1), ("user_email", 1)],
        unique=True,
        name="enterprise_email_unique",
    )
    print("  ✅ (enterprise_id, user_email) — unique")

    # Lookup by Firebase UID (for users who logged in after being invited)
    db.enterprise_license_users.create_index(
        "user_id", name="user_id", sparse=True
    )
    print("  ✅ user_id (sparse)")

    # Lookup by email across all enterprises (for license/status endpoint)
    db.enterprise_license_users.create_index(
        [("user_email", 1), ("status", 1)], name="user_email_status"
    )
    print("  ✅ (user_email, status)")

    print("\nCreating indexes for desktop_license_orders collection...")

    # Unique order_id
    db.desktop_license_orders.create_index(
        "order_id", unique=True, name="order_id_unique"
    )
    print("  ✅ order_id (unique)")

    # User + date (list my orders)
    db.desktop_license_orders.create_index(
        [("user_id", 1), ("created_at", -1)], name="user_created_at"
    )
    print("  ✅ (user_id, created_at)")

    # Status + expiry (auto-expire pending orders)
    db.desktop_license_orders.create_index(
        [("status", 1), ("expires_at", 1)], name="status_expires_at"
    )
    print("  ✅ (status, expires_at)")

    print("\n✅ All desktop license indexes created successfully.")


if __name__ == "__main__":
    create_indexes()
