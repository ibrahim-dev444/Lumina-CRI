"""Who may do what. Each user gets one role through a Django group; superusers act as administrators.

Rules live here, in one table, so a reviewer can check every permission at a glance.
The API enforces them; the screens only hide buttons the user could not use anyway.
"""

RELATIONSHIP_MANAGER = "relationship_manager"
AGENT = "agent"
STEWARD = "steward"
COMPLIANCE = "compliance"
ADMIN = "admin"

# Group name in Django admin -> role.
GROUPS = {
    "Relationship manager": RELATIONSHIP_MANAGER,
    "Contact centre agent": AGENT,
    "Data steward": STEWARD,
    "Compliance officer": COMPLIANCE,
}
LABELS = {role: name for name, role in GROUPS.items()} | {ADMIN: "Administrator"}

# Capabilities. A role not listed for a capability does not have it.
CAPABILITIES = {
    # See full mobile, email and date of birth. Agents see them masked.
    "view_pii": {RELATIONSHIP_MANAGER, STEWARD, COMPLIANCE, ADMIN},
    # Sync sources, switch them on or off.
    "manage_sources": {STEWARD, ADMIN},
    # See the queue of possible duplicates.
    "view_matches": {STEWARD, COMPLIANCE, ADMIN},
    # Merge or keep apart possible duplicates.
    "decide_matches": {STEWARD, ADMIN},
    # Propose a fix to a customer's field, with evidence.
    "propose_corrections": {RELATIONSHIP_MANAGER, STEWARD, ADMIN},
    # Approve or reject someone else's proposed fix (never your own: maker-checker).
    "approve_corrections": {STEWARD, COMPLIANCE, ADMIN},
    # See a full PAN or CKYC number, with a reason that goes to the audit log.
    "reveal_identity": {COMPLIANCE, ADMIN},
    # Download the customer list as CSV.
    "export": {STEWARD, COMPLIANCE, ADMIN},
    # Read the audit log.
    "view_audit": {COMPLIANCE, ADMIN},
}


def role_of(user):
    """The user's role, or None if they have not been given one yet. Cached on the user object."""
    if not user or not user.is_authenticated:
        return None
    if not hasattr(user, "_lumina_role"):
        role = None
        if user.is_superuser:
            role = ADMIN
        else:
            for name in user.groups.values_list("name", flat=True):
                if name in GROUPS:
                    role = GROUPS[name]
                    break
        user._lumina_role = role
    return user._lumina_role


def can(user, capability):
    return role_of(user) in CAPABILITIES[capability]


def capabilities_of(user):
    role = role_of(user)
    return sorted(c for c, roles in CAPABILITIES.items() if role in roles)
