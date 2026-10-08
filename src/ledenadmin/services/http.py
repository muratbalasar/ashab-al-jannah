from urllib.parse import urlsplit


def validate_https_url(url: str) -> str:
    """Require absolute HTTPS URLs for outbound API requests."""
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise ValueError("API URL must be an absolute HTTPS URL") from exc

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("API URL must be an absolute HTTPS URL without embedded credentials")
    return url
