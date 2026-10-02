class NotAuthenticatedError(Exception):
    pass


class PermissionDeniedError(Exception):
    def __init__(self, message: str = "Je hebt geen rechten voor deze actie") -> None:
        super().__init__(message)
        self.message = message
