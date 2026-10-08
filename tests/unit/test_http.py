import pytest

from ledenadmin.services.http import validate_https_url
from ledenadmin.services.kvk_service import KvkApiLookup
from ledenadmin.services.payment_service import HttpMollieApi


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com",
        "file:///etc/passwd",
        "https:///missing-host",
        "https://user:password@api.example.com",
    ],
)
def test_validate_https_url_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        validate_https_url(url)


def test_validate_https_url_accepts_absolute_https_url() -> None:
    url = "https://api.example.com/v2"
    assert validate_https_url(url) == url


@pytest.mark.parametrize(
    "api",
    [
        lambda: KvkApiLookup("api-key", "http://api.example.com"),
        lambda: HttpMollieApi("http://api.example.com"),
    ],
)
def test_api_clients_reject_non_https_urls(api) -> None:
    with pytest.raises(ValueError, match="absolute HTTPS URL"):
        api()
