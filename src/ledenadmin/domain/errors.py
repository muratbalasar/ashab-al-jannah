class DomainError(Exception):
    """Basisfout voor bedrijfsregels; de boodschap is geschikt voor eindgebruikers."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.field = field


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class BusinessRuleError(DomainError):
    pass
