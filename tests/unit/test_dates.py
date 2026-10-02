import pytest

from ledenadmin.web.dates import (
    iso_to_nl_date,
    iso_to_nl_datetime,
    nl_date_to_iso,
    nl_datetime_to_iso,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("07-03-2026", "2026-03-07"),
        ("7-3-2026", "2026-03-07"),
        (" 07/03/2026 ", "2026-03-07"),
        ("07.03.2026", "2026-03-07"),
        ("2026-03-07", "2026-03-07"),  # ISO blijft werken
        ("31-02-2026", "31-02-2026"),  # ongeldig: ongewijzigd, validatie meldt de fout
        ("morgen", "morgen"),
    ],
)
def test_nl_date_to_iso(text, expected) -> None:
    assert nl_date_to_iso(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("14-02-2026 10:30", "2026-02-14T10:30"),
        ("14-2-2026 9.05", "2026-02-14T09:05"),
        ("2026-02-14T10:30", "2026-02-14T10:30"),
        ("14-02-2026 25:00", "14-02-2026 25:00"),
        ("14-02-2026", "14-02-2026"),  # tijd is verplicht
    ],
)
def test_nl_datetime_to_iso(text, expected) -> None:
    assert nl_datetime_to_iso(text) == expected


def test_iso_to_nl_for_display() -> None:
    assert iso_to_nl_date("2026-03-07") == "07-03-2026"
    assert iso_to_nl_date("07-03-2026") == "07-03-2026"
    assert iso_to_nl_date("7-3-2026") == "07-03-2026"
    assert iso_to_nl_date("31-02-2026") == "31-02-2026"
    assert iso_to_nl_date("") == ""
    assert iso_to_nl_datetime("2026-02-14T10:30") == "14-02-2026 10:30"
    assert iso_to_nl_datetime("14-2-2026 9.05") == "14-02-2026 09:05"
    assert iso_to_nl_datetime("2026-02-14T10:30:59") == "14-02-2026 10:30"
    assert iso_to_nl_datetime("fout") == "fout"
