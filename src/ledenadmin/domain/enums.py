from enum import StrEnum


class MemberStatus(StrEnum):
    ACTIVE = "actief"
    INACTIVE = "inactief"


class Role(StrEnum):
    BEHEERDER = "beheerder"
    PENNINGMEESTER = "penningmeester"
    BESTUURDER = "bestuurder"
    LID = "lid"


class OrganizationStatus(StrEnum):
    ACTIVE = "actief"
    BLOCKED = "geblokkeerd"
    # Zacht verwijderd: na de bewaartermijn worden alle gegevens definitief gewist.
    DELETED = "verwijderd"


class Permission(StrEnum):
    MEMBERS_READ = "members:read"
    MEMBERS_WRITE = "members:write"
    MEMBERS_DELETE = "members:delete"
    DONATIONS_READ = "donations:read"
    DONATIONS_WRITE = "donations:write"
    # Bestaande donaties corrigeren; elke wijziging wordt met oude en nieuwe waarde vastgelegd.
    DONATIONS_EDIT = "donations:edit"
    DONATIONS_DELETE = "donations:delete"
    CATEGORIES_WRITE = "categories:write"
    REPORTS_READ = "reports:read"
    REPORTS_MEMBER_READ = "reports:member-read"
    INSIGHTS_READ = "insights:read"
    EXPORT = "export"
    AUDIT_READ = "audit:read"
    MEMBER_FIELDS_WRITE = "member-fields:write"
    SELF_READ = "self:read"
    USERS_MANAGE = "users:manage"
    ORGANIZATION_MANAGE = "organization:manage"
    SELF_DONATE = "self:donate"
