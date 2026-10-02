from enum import StrEnum


class MemberStatus(StrEnum):
    ACTIVE = "actief"
    INACTIVE = "inactief"


class Role(StrEnum):
    BEHEERDER = "beheerder"
    PENNINGMEESTER = "penningmeester"
    BESTUURDER = "bestuurder"


class Permission(StrEnum):
    MEMBERS_READ = "members:read"
    MEMBERS_WRITE = "members:write"
    DONATIONS_READ = "donations:read"
    DONATIONS_WRITE = "donations:write"
    DONATIONS_DELETE = "donations:delete"
    CATEGORIES_WRITE = "categories:write"
    REPORTS_READ = "reports:read"
    REPORTS_MEMBER_READ = "reports:member-read"
    INSIGHTS_READ = "insights:read"
    EXPORT = "export"
    AUDIT_READ = "audit:read"
