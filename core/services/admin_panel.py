"""Admin panel domain logic for SSU 5.4 (user management + monitoring logs)."""

from datetime import date

from django.db import transaction
from django.db.models import Count, Q
from django.utils.dateparse import parse_date

from core.models import (
    AdminActionLog,
    BeachBar,
    Reservation,
    ReservationStatus,
    User,
    UserRole,
)

VALID_ROLES = {UserRole.REGISTERED, UserRole.OWNER, UserRole.ADMIN}
MIN_PASSWORD_LENGTH = 8


class AdminError(Exception):
    def __init__(self, message, code="admin_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def assert_admin(user):
    if not user or not user.is_authenticated or user.role != UserRole.ADMIN:
        raise AdminError("Admin access required.", "forbidden")
    if not user.is_active:
        raise AdminError("Admin access required.", "forbidden")


def _clean_required(value, field, max_length=None):
    text = (value or "").strip()
    if not text:
        raise AdminError(f"{field} is required.", "invalid_data")
    if max_length and len(text) > max_length:
        raise AdminError(f"{field} is too long.", "invalid_data")
    return text


def _normalize_email(email):
    email = _clean_required(email, "email", max_length=255).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise AdminError("Email format is invalid.", "invalid_data")
    return email


def _validate_role(role):
    role = (role or "").strip()
    if role not in VALID_ROLES:
        raise AdminError("Invalid role.", "invalid_data")
    return role


def _validate_password(password, required=True):
    if password is None or password == "":
        if required:
            raise AdminError("Password is required.", "invalid_data")
        return None
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AdminError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            "invalid_data",
        )
    return password


def _log_action(admin, action, target=None, detail=""):
    target_type = ""
    target_id = None
    if target is not None:
        target_type = target.__class__.__name__.lower()
        target_id = getattr(target, "id", None)
    AdminActionLog.objects.create(
        admin=admin,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=(detail or "")[:512],
    )


def serialize_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "is_active": user.is_active,
        "status": "active" if user.is_active else "blocked",
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def list_users(admin, q="", role="", status=""):
    assert_admin(admin)
    users = User.objects.all().order_by("email")
    q = (q or "").strip()
    if q:
        users = users.filter(
            Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )
    role = (role or "").strip()
    if role:
        if role not in VALID_ROLES:
            raise AdminError("Invalid role filter.", "invalid_data")
        users = users.filter(role=role)
    status = (status or "").strip().lower()
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "blocked":
        users = users.filter(is_active=False)
    elif status:
        raise AdminError("Invalid status filter.", "invalid_data")
    return [serialize_user(user) for user in users]


@transaction.atomic
def create_user(admin, first_name, last_name, email, password, role):
    assert_admin(admin)
    first_name = _clean_required(first_name, "first_name", max_length=80)
    last_name = _clean_required(last_name, "last_name", max_length=80)
    email = _normalize_email(email)
    password = _validate_password(password, required=True)
    role = _validate_role(role)

    if User.objects.filter(email=email).exists():
        raise AdminError("A user with this email already exists.", "user_exists")

    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=role,
        is_active=True,
    )
    _log_action(
        admin,
        "user.create",
        target=user,
        detail=f"Created {role} user {email}",
    )
    return serialize_user(user)


@transaction.atomic
def update_user(
    admin,
    user_id,
    first_name=None,
    last_name=None,
    email=None,
    role=None,
    password=None,
    is_active=None,
):
    assert_admin(admin)
    user = User.objects.filter(id=user_id).first()
    if user is None:
        raise AdminError("User not found.", "not_found")

    updates = []
    if first_name is not None:
        user.first_name = _clean_required(first_name, "first_name", max_length=80)
        updates.append("first_name")
    if last_name is not None:
        user.last_name = _clean_required(last_name, "last_name", max_length=80)
        updates.append("last_name")
    if email is not None:
        new_email = _normalize_email(email)
        if (
            User.objects.filter(email=new_email).exclude(id=user.id).exists()
        ):
            raise AdminError("A user with this email already exists.", "user_exists")
        user.email = new_email
        updates.append("email")
    if role is not None:
        new_role = _validate_role(role)
        if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
            if (
                User.objects.filter(role=UserRole.ADMIN, is_active=True)
                .exclude(id=user.id)
                .count()
                == 0
            ):
                raise AdminError(
                    "Cannot demote the last active admin.",
                    "last_admin",
                )
        user.role = new_role
        updates.append("role")
    if is_active is not None:
        if not isinstance(is_active, bool):
            raise AdminError("Invalid status.", "invalid_data")
        if user.id == admin.id and is_active is False:
            raise AdminError("You cannot block your own account.", "forbidden")
        if (
            user.role == UserRole.ADMIN
            and user.is_active
            and is_active is False
            and User.objects.filter(role=UserRole.ADMIN, is_active=True)
            .exclude(id=user.id)
            .count()
            == 0
        ):
            raise AdminError("Cannot block the last active admin.", "last_admin")
        user.is_active = is_active
        updates.append("is_active")

    password = _validate_password(password, required=False)
    if password:
        user.set_password(password)

    if not updates and not password:
        raise AdminError("No changes provided.", "invalid_data")

    if updates:
        user.save(update_fields=updates)
    elif password:
        user.save()

    action = "user.update"
    if updates == ["is_active"]:
        action = "user.unblock" if user.is_active else "user.block"
    _log_action(
        admin,
        action,
        target=user,
        detail=f"Updated user {user.email}: {', '.join(updates) or 'password'}",
    )
    return serialize_user(user)


@transaction.atomic
def delete_user(admin, user_id):
    assert_admin(admin)
    user = User.objects.filter(id=user_id).first()
    if user is None:
        raise AdminError("User not found.", "not_found")
    if user.role == UserRole.ADMIN:
        remaining = (
            User.objects.filter(role=UserRole.ADMIN, is_active=True)
            .exclude(id=user.id)
            .count()
        )
        if remaining == 0:
            raise AdminError("Cannot delete the last active admin.", "last_admin")
    if user.id == admin.id:
        raise AdminError("You cannot delete your own account.", "forbidden")
    if BeachBar.objects.filter(owner=user).exists():
        raise AdminError(
            "Cannot delete an owner who still has a beach bar.",
            "has_beach_bar",
        )
    if Reservation.objects.filter(user=user).exists():
        raise AdminError(
            "Cannot delete a user who has reservations. Block the account instead.",
            "has_reservations",
        )

    email = user.email
    user_pk = user.id
    user.delete()
    _log_action(
        admin,
        "user.delete",
        detail=f"Deleted user {email} (id={user_pk})",
    )
    return {"deleted": True, "id": user_pk}


def get_overview(admin):
    assert_admin(admin)
    today = date.today()
    user_counts = User.objects.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        blocked=Count("id", filter=Q(is_active=False)),
        owners=Count("id", filter=Q(role=UserRole.OWNER)),
        admins=Count("id", filter=Q(role=UserRole.ADMIN)),
        guests=Count("id", filter=Q(role=UserRole.REGISTERED)),
    )
    reservations_today = Reservation.objects.filter(
        reservation_date=today,
        status=ReservationStatus.ACTIVE,
    ).count()
    recent_logins = User.objects.filter(last_login__isnull=False).count()
    return {
        "system_status": "ok",
        "users_total": user_counts["total"],
        "users_active": user_counts["active"],
        "users_blocked": user_counts["blocked"],
        "users_owners": user_counts["owners"],
        "users_admins": user_counts["admins"],
        "users_registered": user_counts["guests"],
        "beach_bars": BeachBar.objects.count(),
        "reservations_today": reservations_today,
        "users_with_login": recent_logins,
        "logs_total": AdminActionLog.objects.count(),
    }


def serialize_log(entry):
    return {
        "id": entry.id,
        "admin_id": entry.admin_id,
        "admin_email": entry.admin.email if entry.admin_id else None,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": entry.target_id,
        "detail": entry.detail,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def list_logs(admin, action="", date_from="", date_to=""):
    assert_admin(admin)
    logs = AdminActionLog.objects.select_related("admin").order_by("-created_at")
    action = (action or "").strip()
    if action:
        logs = logs.filter(action=action)

    parsed_from = parse_date(date_from) if date_from else None
    parsed_to = parse_date(date_to) if date_to else None
    if date_from and parsed_from is None:
        raise AdminError("Invalid from date.", "invalid_data")
    if date_to and parsed_to is None:
        raise AdminError("Invalid to date.", "invalid_data")
    if parsed_from:
        logs = logs.filter(created_at__date__gte=parsed_from)
    if parsed_to:
        logs = logs.filter(created_at__date__lte=parsed_to)

    return [serialize_log(entry) for entry in logs[:200]]
