from dataclasses import dataclass

from ledenadmin.domain.enums import Permission, Role

# Startpunt voor de rolverdeling; definitieve rechten worden met het bestuur afgestemd.
# De beheerder krijgt alle rechten, ook rechten die later aan Permission worden toegevoegd.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.BEHEERDER: frozenset(Permission),
    Role.PENNINGMEESTER: frozenset(
        {
            Permission.MEMBERS_READ,
            Permission.DONATIONS_READ,
            Permission.DONATIONS_WRITE,
            Permission.REPORTS_READ,
            Permission.REPORTS_MEMBER_READ,
            Permission.INSIGHTS_READ,
            Permission.EXPORT,
        }
    ),
    Role.BESTUURDER: frozenset({Permission.REPORTS_READ, Permission.INSIGHTS_READ}),
    # Een lid ziet alleen eigen gegevens op /mijn.
    Role.LID: frozenset({Permission.SELF_READ}),
}


@dataclass(frozen=True)
class Identity:
    """Wie er is aangemeld, los van een organisatie; komt van de identity provider."""

    issuer: str
    subject: str
    name: str
    email: str | None = None
    # Rollen uit het token/de dev-headers; alleen gebruikt om de standaardorganisatie te vullen.
    claimed_roles: frozenset[Role] = frozenset()

    @property
    def key(self) -> str:
        return f"{self.issuer}|{self.subject}"


@dataclass(frozen=True)
class Principal:
    name: str
    roles: frozenset[Role]
    user_id: int | None = None
    organization_id: int | None = None
    is_superadmin: bool = False
    # Het eigen ledenrecord (rol lid); alleen hiermee zijn /mijn-gegevens zichtbaar.
    member_id: int | None = None

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
