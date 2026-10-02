from dataclasses import dataclass

from ledenadmin.domain.enums import Permission, Role

# Startpunt voor de rolverdeling; definitieve rechten worden met het bestuur afgestemd.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.BEHEERDER: frozenset(
        {
            Permission.MEMBERS_READ,
            Permission.MEMBERS_WRITE,
            Permission.DONATIONS_READ,
            Permission.REPORTS_READ,
            Permission.REPORTS_MEMBER_READ,
        }
    ),
    Role.PENNINGMEESTER: frozenset(
        {
            Permission.MEMBERS_READ,
            Permission.DONATIONS_READ,
            Permission.DONATIONS_WRITE,
            Permission.CATEGORIES_WRITE,
            Permission.REPORTS_READ,
            Permission.REPORTS_MEMBER_READ,
            Permission.INSIGHTS_READ,
            Permission.EXPORT,
        }
    ),
    Role.BESTUURDER: frozenset({Permission.REPORTS_READ, Permission.INSIGHTS_READ}),
}


@dataclass(frozen=True)
class Principal:
    name: str
    roles: frozenset[Role]

    @property
    def permissions(self) -> frozenset[Permission]:
        granted: set[Permission] = set()
        for role in self.roles:
            granted |= ROLE_PERMISSIONS.get(role, frozenset())
        return frozenset(granted)

    def can(self, permission: Permission) -> bool:
        return permission in self.permissions


def parse_roles(values) -> frozenset[Role]:
    """Zet ruwe rolnamen om naar bekende rollen; onbekende waarden worden genegeerd."""
    known = {role.value: role for role in Role}
    return frozenset(
        known[value.strip().lower()] for value in values if value.strip().lower() in known
    )
