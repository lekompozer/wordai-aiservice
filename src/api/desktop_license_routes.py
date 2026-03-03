"""
Desktop License Routes
======================
API endpoints for WordAI Desktop App licensing:

  Individual (/api/v1/desktop/individual):
    POST /create-payment-order  — Create QR order (SePay)
    GET  /orders                — My order history

  Enterprise (/api/v1/desktop/enterprise):
    POST /create-payment-order  — Buy enterprise plan
    GET  /orders                — My enterprise order history
    GET  /my                    — Enterprises where I am billing_admin
    GET  /config/{key}          — Public: get customization by enterprise_key (Tauri app)
    GET  /{enterprise_id}       — Enterprise detail
    GET  /{enterprise_id}/users — List users
    POST /{enterprise_id}/users — Add users by email
    PATCH/{enterprise_id}/users/{email}/role — Change user role
    DELETE/{enterprise_id}/users/{email} — Remove user
    GET  /{enterprise_id}/customization — Get Security & Customization Settings
    PUT  /{enterprise_id}/customization — Update settings

  License Status (/api/v1/desktop):
    GET  /license/status        — Current user's license status (for Tauri app)

  Internal (/api/v1/desktop):
    POST /orders/grant-access   — Called by Node.js payment-service after SePay confirms

Roles:
  billing_admin — Person who purchased. Manages user list + can configure customization.
  it_admin      — Assigned by billing_admin. Can configure Security & Customization Settings
                  and sees enterprise_key (for per-machine setup).
  member        — Regular employee. Uses app with enterprise settings applied.
"""

import random
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from src.database.db_manager import DBManager
from src.middleware.firebase_auth import get_current_user
from src.models.desktop_license_models import (
    AddUsersRequest,
    AddUsersResponse,
    CreateEnterpriseOrderRequest,
    CreateIndividualOrderRequest,
    CustomizationPublicResponse,
    CustomizationSettings,
    DESKTOP_PRICES_VND,
    DesktopFeatures,
    DesktopLicenseProduct,
    DesktopLicenseStatusResponse,
    ENTERPRISE_MAX_USERS,
    ENTERPRISE_PLAN_DISPLAY,
    EnterpriseDetailResponse,
    EnterpriseListItem,
    EnterpriseListResponse,
    EnterpriseOrderResponse,
    EnterpriseUserItem,
    EnterpriseUserRole,
    EnterpriseUsersResponse,
    GrantLicenseRequest,
    IndividualOrderResponse,
    LicenseStatus,
    ModuleVisibility,
    HeaderNavVisibility,
    AIModelConfig,
    SidebarMode,
    OrderListResponse,
    OrderStatus,
    OrderStatusResponse,
    UpdateCustomizationRequest,
    UpdateUserRoleRequest,
)
from src.utils.logger import setup_logger

logger = setup_logger()

router = APIRouter(prefix="/api/v1/desktop", tags=["Desktop License"])

db_manager = DBManager()
db = db_manager.db


# ==============================================================================
# HELPERS
# ==============================================================================


def _normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _days_remaining(expires_at: Optional[datetime]) -> Optional[int]:
    if not expires_at:
        return None
    exp = _normalize_dt(expires_at)
    now = datetime.now(timezone.utc)
    delta = exp - now
    return max(0, delta.days)


def _generate_key(prefix: str) -> str:
    """Generate a license key like WDI-ABCD-1234-EFGH or ENT-XXXX-XXXX-XXXX."""
    chars = string.ascii_uppercase + string.digits
    parts = ["".join(random.choices(chars, k=4)) for _ in range(3)]
    return f"{prefix}-{'-'.join(parts)}"


def _get_caller_enterprise_role(
    enterprise_id: str, user_id: str, user_email: str
) -> Optional[EnterpriseUserRole]:
    """Return the caller's role in an enterprise (None if not a member)."""
    record = db.enterprise_license_users.find_one(
        {
            "enterprise_id": enterprise_id,
            "user_email": user_email.lower(),
            "status": {"$ne": "removed"},
        }
    )
    if not record:
        # Also check by user_id in case email changed
        record = db.enterprise_license_users.find_one(
            {
                "enterprise_id": enterprise_id,
                "user_id": user_id,
                "status": {"$ne": "removed"},
            }
        )
    if not record:
        return None
    return EnterpriseUserRole(record["role"])


def _is_enterprise_admin(role: Optional[EnterpriseUserRole]) -> bool:
    return role in (EnterpriseUserRole.BILLING_ADMIN, EnterpriseUserRole.IT_ADMIN)


def _customization_from_doc(doc: dict) -> CustomizationSettings:
    """Parse customization settings from a MongoDB document."""
    raw = doc.get("customization") or {}
    mod = raw.get("modules") or {}
    nav = raw.get("header_nav") or {}
    ai = raw.get("ai_models") or {}
    return CustomizationSettings(
        modules=ModuleVisibility(
            documents=mod.get("documents", True),
            online_tests=mod.get("online_tests", True),
            online_books=mod.get("online_books", True),
            studyhub=mod.get("studyhub", True),
            listen_and_learn=mod.get("listen_and_learn", True),
            code_editor=mod.get("code_editor", True),
            software_lab=mod.get("software_lab", True),
        ),
        header_nav=HeaderNavVisibility(
            usage_and_plan=nav.get("usage_and_plan", True),
            community=nav.get("community", True),
            ai_tools=nav.get("ai_tools", True),
            feedback=nav.get("feedback", True),
        ),
        sidebar_mode=SidebarMode(raw.get("sidebar_mode", SidebarMode.FULL.value)),
        ai_models=AIModelConfig(
            gemini=ai.get("gemini", True),
            chatgpt=ai.get("chatgpt", True),
            deepseek=ai.get("deepseek", True),
            qwen=ai.get("qwen", True),
        ),
    )


def _customization_to_dict(c: CustomizationSettings) -> dict:
    return {
        "modules": c.modules.model_dump(),
        "header_nav": c.header_nav.model_dump(),
        "sidebar_mode": c.sidebar_mode.value,
        "ai_models": c.ai_models.model_dump(),
    }


# ==============================================================================
# LICENSE STATUS (works for individual + enterprise)
# ==============================================================================


@router.get(
    "/license/status",
    response_model=DesktopLicenseStatusResponse,
    summary="Get current user's desktop license status",
)
async def get_license_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Check license status for the authenticated user.**

    The Tauri desktop app calls this on startup to determine:
    - Whether the user has a valid license
    - Which features are unlocked
    - Enterprise customization settings (if applicable)
    - Whether the user can see the `enterprise_key` (billing_admin or it_admin only)

    Priority: Enterprise license > Individual license > None
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        now = datetime.now(timezone.utc)

        # ── 1. Check Enterprise membership ─────────────────────────────────
        ent_user = db.enterprise_license_users.find_one(
            {"user_email": user_email, "status": {"$ne": "removed"}}
        )
        # Fallback match by user_id in case email wasn't set when invited
        if not ent_user:
            ent_user = db.enterprise_license_users.find_one(
                {"user_id": user_id, "status": {"$ne": "removed"}}
            )

        if ent_user:
            enterprise_id = ent_user["enterprise_id"]
            role = EnterpriseUserRole(ent_user["role"])

            ent = db.enterprise_licenses.find_one(
                {"enterprise_id": enterprise_id, "status": LicenseStatus.ACTIVE.value}
            )
            if ent:
                expires_at = _normalize_dt(ent.get("expires_at"))
                is_active = expires_at is None or expires_at > now

                if is_active:
                    # Activate user record if pending
                    if ent_user.get("status") == "pending":
                        db.enterprise_license_users.update_one(
                            {"_id": ent_user["_id"]},
                            {
                                "$set": {
                                    "user_id": user_id,
                                    "status": "active",
                                    "activated_at": datetime.utcnow(),
                                }
                            },
                        )

                    is_admin = _is_enterprise_admin(role)

                    customization = _customization_from_doc(ent)

                    return DesktopLicenseStatusResponse(
                        has_license=True,
                        license_type="enterprise",
                        status="active",
                        expires_at=expires_at,
                        days_remaining=_days_remaining(expires_at),
                        features=DesktopFeatures(
                            documents=customization.modules.documents,
                            online_tests=customization.modules.online_tests,
                            online_books=customization.modules.online_books,
                            studyhub=customization.modules.studyhub,
                            code_editor=customization.modules.code_editor,
                            software_lab=customization.modules.software_lab,
                            ai_tools=customization.header_nav.ai_tools,
                            listen_and_learn=customization.modules.listen_and_learn,
                        ),
                        is_enterprise_admin=is_admin,
                        is_billing_admin=(role == EnterpriseUserRole.BILLING_ADMIN),
                        enterprise_id=enterprise_id,
                        organization_name=ent.get("organization_name"),
                        enterprise_key=ent.get("enterprise_key") if is_admin else None,
                        customization=customization,
                    )

        # ── 2. Check Individual license ────────────────────────────────────
        ind = db.desktop_licenses.find_one(
            {"user_id": user_id, "status": LicenseStatus.ACTIVE.value}
        )
        if ind:
            expires_at = _normalize_dt(ind.get("expires_at"))
            is_active = expires_at is None or expires_at > now

            if is_active:
                return DesktopLicenseStatusResponse(
                    has_license=True,
                    license_type="individual",
                    status="active",
                    expires_at=expires_at,
                    days_remaining=_days_remaining(expires_at),
                    features=DesktopFeatures(),
                )

        # ── 3. No valid license ────────────────────────────────────────────
        return DesktopLicenseStatusResponse(
            has_license=False,
            license_type=None,
            status="none",
            features=DesktopFeatures(
                documents=False,
                online_tests=False,
                online_books=False,
                studyhub=False,
                code_editor=False,
                software_lab=False,
                ai_tools=False,
            ),
        )

    except Exception as e:
        logger.error(f"❌ Error checking desktop license status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check license status",
        )


# ==============================================================================
# INDIVIDUAL LICENSE — ORDER MANAGEMENT
# ==============================================================================


@router.post(
    "/individual/create-payment-order",
    response_model=IndividualOrderResponse,
    summary="Create payment order for Individual license (149,000 VND/year)",
)
async def create_individual_order(
    request: CreateIndividualOrderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a SePay payment order for an Individual desktop license.**

    Flow:
    1. Creates `desktop_license_orders` record (status: pending)
    2. Returns `order_id` to frontend
    3. Frontend calls Node.js payment-service with `order_id` to create SePay checkout
    4. User pays via SePay → webhook confirms → `POST /orders/grant-access` activates license
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        base_price = DESKTOP_PRICES_VND[DesktopLicenseProduct.INDIVIDUAL]
        price_vnd = base_price * request.plan_years

        ts = int(datetime.utcnow().timestamp())
        order_id = f"DESK-{ts}-{user_id[:8]}"

        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "user_email": user_email,
            "product": DesktopLicenseProduct.INDIVIDUAL.value,
            "organization_name": None,
            "max_users": 1,
            "custom_user_count": None,
            "plan_years": request.plan_years,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "status": OrderStatus.PENDING.value,
            "transaction_id": None,
            "paid_at": None,
            "access_granted": False,
            "license_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=30),
        }

        db.desktop_license_orders.insert_one(order_doc)
        logger.info(f"💻 Individual desktop order created: {order_id} — {price_vnd:,} VND")

        return IndividualOrderResponse(
            success=True,
            order_id=order_id,
            product="individual",
            price_vnd=price_vnd,
            currency="VND",
            payment_method="SEPAY_BANK_TRANSFER",
            message="Order created. Call payment-service to generate SePay checkout.",
            expires_at=order_doc["expires_at"],
        )

    except Exception as e:
        logger.error(f"❌ Error creating individual order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order",
        )


@router.get(
    "/individual/orders",
    response_model=OrderListResponse,
    summary="My Individual license order history",
)
async def list_individual_orders(
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List payment orders for Individual desktop licenses."""
    user_id = current_user["uid"]
    limit = min(limit, 100)
    skip = (page - 1) * limit

    total = db.desktop_license_orders.count_documents(
        {"user_id": user_id, "product": DesktopLicenseProduct.INDIVIDUAL.value}
    )
    cursor = (
        db.desktop_license_orders.find(
            {"user_id": user_id, "product": DesktopLicenseProduct.INDIVIDUAL.value}
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    orders = [
        OrderStatusResponse(
            order_id=o["order_id"],
            product=o["product"],
            status=OrderStatus(o["status"]),
            price_vnd=o["price_vnd"],
            access_granted=o["access_granted"],
            license_id=o.get("license_id"),
            created_at=o["created_at"],
            expires_at=o["expires_at"],
        )
        for o in cursor
    ]

    return OrderListResponse(orders=orders, total=total)


# ==============================================================================
# ENTERPRISE — ORDER CREATION
# ==============================================================================


@router.post(
    "/enterprise/create-payment-order",
    response_model=EnterpriseOrderResponse,
    summary="Create payment order for Enterprise license",
)
async def create_enterprise_order(
    request: CreateEnterpriseOrderRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Create a SePay payment order for an Enterprise license.**

    Pricing:
    - `enterprise_small_team` (5 users): 499,000 VND/year
    - `enterprise_business` (20 users): 1,499,000 VND/year
    - `enterprise_custom` (N users): 99,000 × N VND/year

    After payment confirms, an `enterprise_licenses` record is created and the
    buyer is added to `enterprise_license_users` with `role=billing_admin`.
    The buyer can then add employee emails and optionally assign `it_admin` roles.
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        product = request.product

        # Calculate price
        max_users = ENTERPRISE_MAX_USERS.get(product)
        if product == DesktopLicenseProduct.ENTERPRISE_CUSTOM:
            max_users = request.custom_user_count
            base_price_per_user = DESKTOP_PRICES_VND[product]
            base_price = base_price_per_user * max_users
        else:
            base_price = DESKTOP_PRICES_VND[product]

        price_vnd = base_price * request.plan_years

        ts = int(datetime.utcnow().timestamp())
        order_id = f"ENT-{ts}-{user_id[:8]}"

        order_doc = {
            "order_id": order_id,
            "user_id": user_id,
            "user_email": user_email,
            "product": product.value,
            "organization_name": request.organization_name,
            "max_users": max_users,
            "custom_user_count": request.custom_user_count,
            "plan_years": request.plan_years,
            "price_vnd": price_vnd,
            "currency": "VND",
            "payment_method": "SEPAY_BANK_TRANSFER",
            "status": OrderStatus.PENDING.value,
            "transaction_id": None,
            "paid_at": None,
            "access_granted": False,
            "license_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(minutes=30),
        }

        db.desktop_license_orders.insert_one(order_doc)
        logger.info(
            f"🏢 Enterprise order created: {order_id} — {request.organization_name} — {price_vnd:,} VND"
        )

        return EnterpriseOrderResponse(
            success=True,
            order_id=order_id,
            product=product.value,
            organization_name=request.organization_name,
            max_users=max_users,
            price_vnd=price_vnd,
            currency="VND",
            payment_method="SEPAY_BANK_TRANSFER",
            message="Order created. Call payment-service to generate SePay checkout.",
            expires_at=order_doc["expires_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating enterprise order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create enterprise order",
        )


@router.get(
    "/enterprise/orders",
    response_model=OrderListResponse,
    summary="My Enterprise license order history",
)
async def list_enterprise_orders(
    page: int = 1,
    limit: int = 20,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List payment orders for Enterprise desktop licenses created by the current user."""
    user_id = current_user["uid"]
    limit = min(limit, 100)
    skip = (page - 1) * limit

    enterprise_products = [
        DesktopLicenseProduct.ENTERPRISE_SMALL_TEAM.value,
        DesktopLicenseProduct.ENTERPRISE_BUSINESS.value,
        DesktopLicenseProduct.ENTERPRISE_CUSTOM.value,
    ]

    total = db.desktop_license_orders.count_documents(
        {"user_id": user_id, "product": {"$in": enterprise_products}}
    )
    cursor = (
        db.desktop_license_orders.find(
            {"user_id": user_id, "product": {"$in": enterprise_products}}
        )
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
    )

    orders = [
        OrderStatusResponse(
            order_id=o["order_id"],
            product=o["product"],
            status=OrderStatus(o["status"]),
            price_vnd=o["price_vnd"],
            access_granted=o["access_granted"],
            license_id=o.get("license_id"),
            created_at=o["created_at"],
            expires_at=o["expires_at"],
        )
        for o in cursor
    ]

    return OrderListResponse(orders=orders, total=total)


# ==============================================================================
# ENTERPRISE — MY ENTERPRISES (as billing admin)
# ⚠️  MUST be declared BEFORE /{enterprise_id} routes
# ==============================================================================


@router.get(
    "/enterprise/my",
    response_model=EnterpriseListResponse,
    summary="Enterprises where I am the billing admin",
)
async def list_my_enterprises(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Returns all enterprise licenses purchased by the current user (billing_admin role).
    The `enterprise_key` is included so the billing admin can share it with IT admins.
    """
    user_id = current_user["uid"]

    try:
        enterprises = list(
            db.enterprise_licenses.find(
                {"billing_admin_user_id": user_id, "status": {"$ne": "deleted"}}
            ).sort("created_at", -1)
        )

        items = []
        for e in enterprises:
            expires_at = _normalize_dt(e.get("expires_at"))
            items.append(
                EnterpriseListItem(
                    enterprise_id=e["enterprise_id"],
                    organization_name=e["organization_name"],
                    plan=e["plan"],
                    max_users=e["max_users"],
                    current_users=e.get("current_users", 0),
                    status=LicenseStatus(e["status"]),
                    expires_at=expires_at,
                    days_remaining=_days_remaining(expires_at),
                    activated_at=e.get("activated_at"),
                    created_at=e["created_at"],
                )
            )

        return EnterpriseListResponse(enterprises=items, total=len(items))

    except Exception as e:
        logger.error(f"❌ Error listing enterprises: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list enterprises",
        )


# ==============================================================================
# ENTERPRISE — PUBLIC CONFIG (no auth — for Tauri app machine setup)
# ⚠️  MUST be declared BEFORE /{enterprise_id} routes
# ==============================================================================


@router.get(
    "/enterprise/config/{enterprise_key}",
    response_model=CustomizationPublicResponse,
    summary="Get enterprise customization settings by enterprise_key (no auth)",
)
async def get_enterprise_config_by_key(enterprise_key: str):
    """
    **Public endpoint — no Firebase authentication required.**

    Returns the Security & Customization Settings for the enterprise identified
    by `enterprise_key`. The Tauri desktop app uses this to apply org-wide
    settings on each user machine without requiring per-machine login.

    The IT admin enters the `enterprise_key` once per machine during setup.
    """
    try:
        ent = db.enterprise_licenses.find_one(
            {"enterprise_key": enterprise_key, "status": LicenseStatus.ACTIVE.value}
        )
        if not ent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Enterprise not found or license is not active",
            )

        # Check expiry
        expires_at = _normalize_dt(ent.get("expires_at"))
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Enterprise license has expired",
            )

        customization = _customization_from_doc(ent)

        return CustomizationPublicResponse(
            enterprise_id=ent["enterprise_id"],
            organization_name=ent["organization_name"],
            customization=customization,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting enterprise config by key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get enterprise config",
        )


# ==============================================================================
# ENTERPRISE — DETAIL + MANAGEMENT (billing_admin / it_admin)
# ==============================================================================


@router.get(
    "/enterprise/{enterprise_id}",
    response_model=EnterpriseDetailResponse,
    summary="Get enterprise detail",
)
async def get_enterprise_detail(
    enterprise_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Get full enterprise detail.

    - **Billing admin / IT admin**: see `enterprise_key` and full customization settings
    - **Member**: sees basic info only (no `enterprise_key`)
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this enterprise",
            )

        is_admin = _is_enterprise_admin(role)
        expires_at = _normalize_dt(ent.get("expires_at"))

        return EnterpriseDetailResponse(
            enterprise_id=enterprise_id,
            organization_name=ent["organization_name"],
            plan=ent["plan"],
            max_users=ent["max_users"],
            current_users=ent.get("current_users", 0),
            status=LicenseStatus(ent["status"]),
            expires_at=expires_at,
            days_remaining=_days_remaining(expires_at),
            activated_at=ent.get("activated_at"),
            created_at=ent["created_at"],
            enterprise_key=ent.get("enterprise_key") if is_admin else None,
            customization=_customization_from_doc(ent) if is_admin else None,
            billing_admin_email=ent.get("billing_admin_email") if is_admin else None,
            caller_role=role.value,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting enterprise detail: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get enterprise detail",
        )


@router.get(
    "/enterprise/{enterprise_id}/users",
    response_model=EnterpriseUsersResponse,
    summary="List enterprise users",
)
async def list_enterprise_users(
    enterprise_id: str,
    include_removed: bool = False,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    List all users assigned to the enterprise.
    Requires `billing_admin` or `it_admin` role.
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if not _is_enterprise_admin(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only billing_admin and it_admin can view user list",
            )

        query: dict = {"enterprise_id": enterprise_id}
        if not include_removed:
            query["status"] = {"$ne": "removed"}

        cursor = db.enterprise_license_users.find(query).sort("invited_at", 1)
        users = []
        for u in cursor:
            users.append(
                EnterpriseUserItem(
                    email=u["user_email"],
                    user_id=u.get("user_id"),
                    role=EnterpriseUserRole(u["role"]),
                    status=u["status"],
                    invited_at=u["invited_at"],
                    activated_at=u.get("activated_at"),
                )
            )

        return EnterpriseUsersResponse(
            enterprise_id=enterprise_id,
            users=users,
            total=len(users),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing enterprise users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list enterprise users",
        )


@router.post(
    "/enterprise/{enterprise_id}/users",
    response_model=AddUsersResponse,
    summary="Add users to enterprise by email list",
)
async def add_enterprise_users(
    enterprise_id: str,
    request: AddUsersRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Add employee emails to the enterprise.**
    Requires `billing_admin` role.

    - Added users get `status=pending` until they log in with that email
    - On next `/license/status` call, their status becomes `active` automatically
    - You can assign `role=it_admin` to grant Security & Customization Settings access

    Behavior:
    - Already-in-enterprise emails are skipped (not duplicated)
    - Cannot exceed `max_users` limit (check `current_users`)
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if role != EnterpriseUserRole.BILLING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only billing_admin can add users",
            )

        # Check capacity
        current_users = ent.get("current_users", 0)
        max_users = ent["max_users"]
        available_slots = max_users - current_users

        if available_slots <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Enterprise is at capacity ({current_users}/{max_users} users). Cannot add more.",
            )

        emails_to_add = request.emails[:available_slots]  # Respect capacity
        emails_skipped_cap = request.emails[available_slots:]

        # Check existing emails
        existing = set(
            r["user_email"]
            for r in db.enterprise_license_users.find(
                {
                    "enterprise_id": enterprise_id,
                    "user_email": {"$in": emails_to_add},
                    "status": {"$ne": "removed"},
                }
            )
        )

        added_emails = []
        skipped_emails = list(emails_skipped_cap)

        for email in emails_to_add:
            if email in existing:
                skipped_emails.append(email)
                continue

            db.enterprise_license_users.insert_one(
                {
                    "id": f"eluser_{uuid.uuid4().hex[:16]}",
                    "enterprise_id": enterprise_id,
                    "user_id": None,
                    "user_email": email,
                    "role": request.role.value,
                    "status": "pending",
                    "invited_at": datetime.utcnow(),
                    "activated_at": None,
                    "removed_at": None,
                }
            )
            added_emails.append(email)

        # Update current_users count
        if added_emails:
            db.enterprise_licenses.update_one(
                {"enterprise_id": enterprise_id},
                {
                    "$inc": {"current_users": len(added_emails)},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

        logger.info(
            f"👥 Enterprise {enterprise_id}: added {len(added_emails)} users, "
            f"skipped {len(skipped_emails)}"
        )

        return AddUsersResponse(
            added=len(added_emails),
            already_in_enterprise=len([e for e in skipped_emails if e in existing]),
            emails_added=added_emails,
            emails_skipped=skipped_emails,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding enterprise users: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add users",
        )


@router.patch(
    "/enterprise/{enterprise_id}/users/{email}/role",
    summary="Change a user's role in the enterprise",
)
async def update_enterprise_user_role(
    enterprise_id: str,
    email: str,
    request: UpdateUserRoleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Change a user's role within the enterprise.**
    Requires `billing_admin` role.

    - Assign `it_admin` to grant IT staff access to Security & Customization Settings
      and the `enterprise_key` (for per-machine setup)
    - Downgrade `it_admin` → `member` to revoke admin privileges
    - Cannot change the `billing_admin`'s role
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()
    target_email = email.lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        caller_role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if caller_role != EnterpriseUserRole.BILLING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only billing_admin can change user roles",
            )

        target = db.enterprise_license_users.find_one(
            {
                "enterprise_id": enterprise_id,
                "user_email": target_email,
                "status": {"$ne": "removed"},
            }
        )
        if not target:
            raise HTTPException(
                status_code=404, detail=f"User {target_email} not found in enterprise"
            )

        if target["role"] == EnterpriseUserRole.BILLING_ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change the billing_admin's role",
            )

        db.enterprise_license_users.update_one(
            {"_id": target["_id"]},
            {"$set": {"role": request.role.value, "updated_at": datetime.utcnow()}},
        )

        logger.info(
            f"🔄 Enterprise {enterprise_id}: {target_email} role → {request.role.value}"
        )

        return {
            "success": True,
            "email": target_email,
            "new_role": request.role.value,
            "message": f"Role updated to {request.role.value}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating user role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user role",
        )


@router.delete(
    "/enterprise/{enterprise_id}/users/{email}",
    summary="Remove a user from the enterprise",
)
async def remove_enterprise_user(
    enterprise_id: str,
    email: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Remove a user from the enterprise (soft delete).**
    Requires `billing_admin` role.

    - Billing admin cannot remove themselves
    - Removed users lose access to enterprise features on next license check
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()
    target_email = email.lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        caller_role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if caller_role != EnterpriseUserRole.BILLING_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only billing_admin can remove users",
            )

        if target_email == user_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="billing_admin cannot remove themselves from the enterprise",
            )

        target = db.enterprise_license_users.find_one(
            {
                "enterprise_id": enterprise_id,
                "user_email": target_email,
                "status": {"$ne": "removed"},
            }
        )
        if not target:
            raise HTTPException(
                status_code=404, detail=f"User {target_email} not found in enterprise"
            )

        if target["role"] == EnterpriseUserRole.BILLING_ADMIN.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the billing_admin from the enterprise",
            )

        db.enterprise_license_users.update_one(
            {"_id": target["_id"]},
            {
                "$set": {
                    "status": "removed",
                    "removed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        # Decrease current_users count
        db.enterprise_licenses.update_one(
            {"enterprise_id": enterprise_id},
            {
                "$inc": {"current_users": -1},
                "$set": {"updated_at": datetime.utcnow()},
            },
        )

        logger.info(f"🗑️  Enterprise {enterprise_id}: removed user {target_email}")

        return {
            "success": True,
            "email": target_email,
            "message": f"User {target_email} removed from enterprise",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing enterprise user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove user",
        )


# ==============================================================================
# ENTERPRISE — SECURITY & CUSTOMIZATION SETTINGS
# ==============================================================================


@router.get(
    "/enterprise/{enterprise_id}/customization",
    response_model=CustomizationSettings,
    summary="Get Security & Customization Settings",
)
async def get_enterprise_customization(
    enterprise_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Get current Security & Customization Settings.**

    - **billing_admin / it_admin**: full access + sees all settings
    - **member**: read-only access (app applies these settings transparently)
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not a member of this enterprise",
            )

        return _customization_from_doc(ent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting customization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get customization settings",
        )


@router.put(
    "/enterprise/{enterprise_id}/customization",
    response_model=CustomizationSettings,
    summary="Update Security & Customization Settings",
)
async def update_enterprise_customization(
    enterprise_id: str,
    request: UpdateCustomizationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    **Update Security & Customization Settings for the enterprise.**

    Requires `billing_admin` or `it_admin` role.
    Changes apply to ALL users in the enterprise on their next license check.

    All fields are optional — only submit the sections you want to update.
    Unsubmitted sections remain unchanged.
    """
    user_id = current_user["uid"]
    user_email = current_user.get("email", "").lower()

    try:
        ent = db.enterprise_licenses.find_one({"enterprise_id": enterprise_id})
        if not ent:
            raise HTTPException(status_code=404, detail="Enterprise not found")

        role = _get_caller_enterprise_role(enterprise_id, user_id, user_email)
        if not _is_enterprise_admin(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only billing_admin and it_admin can update customization settings",
            )

        # Merge with existing settings (partial update)
        current_settings = _customization_from_doc(ent)

        new_modules = request.modules if request.modules is not None else current_settings.modules
        new_header_nav = request.header_nav if request.header_nav is not None else current_settings.header_nav
        new_sidebar_mode = request.sidebar_mode if request.sidebar_mode is not None else current_settings.sidebar_mode
        new_ai_models = request.ai_models if request.ai_models is not None else current_settings.ai_models

        updated = CustomizationSettings(
            modules=new_modules,
            header_nav=new_header_nav,
            sidebar_mode=new_sidebar_mode,
            ai_models=new_ai_models,
        )

        db.enterprise_licenses.update_one(
            {"enterprise_id": enterprise_id},
            {
                "$set": {
                    "customization": _customization_to_dict(updated),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"⚙️  Enterprise {enterprise_id}: customization updated by {user_email} ({role.value})"
        )

        return updated

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating customization: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update customization settings",
        )


# ==============================================================================
# INTERNAL — GRANT LICENSE AFTER PAYMENT (called by Node.js payment-service)
# ==============================================================================


@router.post(
    "/orders/grant-access",
    summary="[Internal] Activate license after SePay payment confirmed",
    include_in_schema=False,  # Hidden from Swagger — internal use only
)
async def grant_license_from_order(request: GrantLicenseRequest):
    """
    **INTERNAL ENDPOINT** — Called by Node.js payment-service after SePay confirms payment.

    For individual orders: creates `desktop_licenses` record.
    For enterprise orders: creates `enterprise_licenses` + adds billing_admin
    to `enterprise_license_users`.
    """
    order_id = request.order_id

    try:
        order = db.desktop_license_orders.find_one({"order_id": order_id})
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        if order["status"] != OrderStatus.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Order status is '{order['status']}', expected 'completed'",
            )

        if order["access_granted"]:
            logger.info(f"⚠️  License already granted for order {order_id}")
            return {"success": True, "message": "License already granted", "order_id": order_id}

        product = order["product"]
        user_id = order["user_id"]
        user_email = order["user_email"]
        plan_years = order.get("plan_years", 1)

        activated_at = order.get("paid_at", datetime.utcnow())
        expires_at = activated_at + timedelta(days=365 * plan_years)

        # ── Individual license ──────────────────────────────────────────────
        if product == DesktopLicenseProduct.INDIVIDUAL.value:
            license_id = f"lic_{uuid.uuid4().hex[:16]}"
            license_key = _generate_key("WDI")

            db.desktop_licenses.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "license_id": license_id,
                        "user_id": user_id,
                        "user_email": user_email,
                        "license_type": "individual",
                        "license_key": license_key,
                        "status": LicenseStatus.ACTIVE.value,
                        "plan_years": plan_years,
                        "price_vnd": order["price_vnd"],
                        "payment_method": "SEPAY_BANK_TRANSFER",
                        "order_id": order_id,
                        "activated_at": activated_at,
                        "expires_at": expires_at,
                        "updated_at": datetime.utcnow(),
                    },
                    "$setOnInsert": {"created_at": datetime.utcnow()},
                },
                upsert=True,
            )

            db.desktop_license_orders.update_one(
                {"order_id": order_id},
                {
                    "$set": {
                        "access_granted": True,
                        "license_id": license_id,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )

            logger.info(f"✅ Individual license activated: {license_id} for {user_email}")

            return {
                "success": True,
                "license_type": "individual",
                "license_id": license_id,
                "license_key": license_key,
                "user_id": user_id,
                "expires_at": expires_at.isoformat(),
            }

        # ── Enterprise license ──────────────────────────────────────────────
        enterprise_id = f"ent_{uuid.uuid4().hex[:16]}"
        enterprise_key = _generate_key("ENT")
        organization_name = order.get("organization_name", "Organization")
        max_users = order["max_users"]
        plan = product  # e.g., "enterprise_small_team"

        default_customization = _customization_to_dict(CustomizationSettings.defaults())

        db.enterprise_licenses.insert_one(
            {
                "enterprise_id": enterprise_id,
                "billing_admin_user_id": user_id,
                "billing_admin_email": user_email,
                "organization_name": organization_name,
                "license_type": "enterprise",
                "enterprise_key": enterprise_key,
                "plan": plan,
                "max_users": max_users,
                "current_users": 1,  # billing_admin counts as 1 user
                "price_vnd": order["price_vnd"],
                "plan_years": plan_years,
                "status": LicenseStatus.ACTIVE.value,
                "customization": default_customization,
                "payment_method": "SEPAY_BANK_TRANSFER",
                "order_id": order_id,
                "activated_at": activated_at,
                "expires_at": expires_at,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        )

        # Add billing_admin as the first user
        db.enterprise_license_users.insert_one(
            {
                "id": f"eluser_{uuid.uuid4().hex[:16]}",
                "enterprise_id": enterprise_id,
                "user_id": user_id,
                "user_email": user_email,
                "role": EnterpriseUserRole.BILLING_ADMIN.value,
                "status": "active",
                "invited_at": activated_at,
                "activated_at": activated_at,
                "removed_at": None,
            }
        )

        db.desktop_license_orders.update_one(
            {"order_id": order_id},
            {
                "$set": {
                    "access_granted": True,
                    "license_id": enterprise_id,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(
            f"✅ Enterprise license activated: {enterprise_id} ({organization_name}) "
            f"for {user_email} — key: {enterprise_key}"
        )

        return {
            "success": True,
            "license_type": "enterprise",
            "enterprise_id": enterprise_id,
            "enterprise_key": enterprise_key,
            "organization_name": organization_name,
            "max_users": max_users,
            "user_id": user_id,
            "expires_at": expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error granting desktop license: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to grant license",
        )
