"""Managing the people of one organization: create logins, change roles, deactivate, reset passwords.

Only the organization's administrators call these (see the manage_users capability). Everything here runs
inside the organization's own schema, so an administrator can only ever see and change their own staff.
"""

import re
import secrets

from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AccountProfile
from .roles import ADMIN, GROUPS, LABELS, role_of

ROLE_GROUP = {role: name for name, role in GROUPS.items()}  # "steward" -> "Data steward"
ASSIGNABLE_ROLES = list(ROLE_GROUP) + [ADMIN]
USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,39}$")


class UserAdminError(ValueError):
    pass


def temporary_password():
    """A random password that passes Django's password rules. Shown to the administrator once, never stored."""
    while True:
        candidate = secrets.token_urlsafe(10)
        try:
            validate_password(candidate)
            return candidate
        except ValidationError:
            continue


def user_json(user):
    role = role_of(user)
    profile = getattr(user, "lumina_profile", None)
    return {
        "id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "name": user.get_full_name() or user.username,
        "role": role,
        "role_label": LABELS.get(role, "No role"),
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "date_joined": user.date_joined.isoformat(),
        "must_change_password": bool(profile and profile.must_change_password),
    }


def list_users():
    return User.objects.select_related("lumina_profile").prefetch_related("groups").order_by("username")


def _set_role(user, role):
    if role not in ASSIGNABLE_ROLES:
        raise UserAdminError(f"Unknown role: {role}.")
    user.is_superuser = role == ADMIN
    user.is_staff = role == ADMIN
    user.save(update_fields=["is_superuser", "is_staff"])
    user.groups.set([] if role == ADMIN else [Group.objects.get(name=ROLE_GROUP[role])])
    if hasattr(user, "_lumina_role"):
        del user._lumina_role


def _active_admins():
    return User.objects.filter(is_superuser=True, is_active=True)


def _end_sessions(user):
    """Sign the person out everywhere: delete their sessions in this organization."""
    for session in Session.objects.filter(expire_date__gt=timezone.now()):
        if str(session.get_decoded().get("_auth_user_id")) == str(user.pk):
            session.delete()


@transaction.atomic
def create_user(actor, username, first_name, last_name, role):
    """Returns (user, temporary_password). The person must change the password at first sign-in."""
    username = (username or "").strip().lower()
    if not USERNAME.match(username):
        raise UserAdminError("Username: 3 to 40 characters, lowercase letters, numbers, dots, dashes or underscores.")
    if User.objects.filter(username=username).exists():
        raise UserAdminError(f"There is already a login called {username}.")
    if role not in ASSIGNABLE_ROLES:
        raise UserAdminError("Choose a role.")
    password = temporary_password()
    user = User.objects.create_user(
        username, password=password, first_name=(first_name or "").strip()[:150], last_name=(last_name or "").strip()[:150]
    )
    _set_role(user, role)
    AccountProfile.objects.create(user=user, must_change_password=True, created_by=actor.get_username())
    return user, password


@transaction.atomic
def update_user(actor, user, role=None, is_active=None, first_name=None, last_name=None):
    """Change a person's role, status or name. Returns {field: [old, new]} for the audit log."""
    changes = {}
    if user.pk == actor.pk and (role not in (None, role_of(user)) or is_active is False):
        raise UserAdminError("You cannot change your own role or deactivate yourself. Ask another administrator.")

    losing_admin = role_of(user) == ADMIN and ((role is not None and role != ADMIN) or is_active is False)
    if losing_admin and _active_admins().exclude(pk=user.pk).count() == 0:
        raise UserAdminError("This is the last active administrator. Make someone else an administrator first.")

    if first_name is not None and first_name.strip() != user.first_name:
        changes["first_name"] = [user.first_name, first_name.strip()[:150]]
        user.first_name = first_name.strip()[:150]
    if last_name is not None and last_name.strip() != user.last_name:
        changes["last_name"] = [user.last_name, last_name.strip()[:150]]
        user.last_name = last_name.strip()[:150]
    if changes:
        user.save(update_fields=["first_name", "last_name"])

    if role is not None and role != role_of(user):
        changes["role"] = [role_of(user), role]
        _set_role(user, role)

    if is_active is not None and is_active != user.is_active:
        changes["is_active"] = [user.is_active, is_active]
        user.is_active = is_active
        user.save(update_fields=["is_active"])
        if not is_active:
            _end_sessions(user)
    return changes


@transaction.atomic
def reset_password(actor, user):
    """Give the person a new temporary password and sign them out everywhere. Returns the password."""
    if user.pk == actor.pk:
        raise UserAdminError("Change your own password from your account, not here.")
    password = temporary_password()
    user.set_password(password)
    user.save(update_fields=["password"])
    AccountProfile.objects.update_or_create(user=user, defaults={"must_change_password": True})
    _end_sessions(user)
    return password


def change_own_password(user, current, new):
    """The person sets their own password (required after a temporary one)."""
    if not user.check_password(current or ""):
        raise UserAdminError("Your current password is not right.")
    if current == new:
        raise UserAdminError("Choose a password different from the current one.")
    try:
        validate_password(new or "", user)
    except ValidationError as exc:
        raise UserAdminError(" ".join(exc.messages)) from exc
    user.set_password(new)
    user.save(update_fields=["password"])
    AccountProfile.objects.update_or_create(user=user, defaults={"must_change_password": False})
