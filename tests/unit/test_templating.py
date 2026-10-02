import os

from ledenadmin.web import templating
from ledenadmin.web.templating import asset_version


def test_static_assets_get_content_version_in_url(client) -> None:
    html = client.get("/").text

    assert f'/static/app.css?v={asset_version("app.css")}"' in html
    assert f'/static/app.js?v={asset_version("app.js")}"' in html


def test_asset_version_changes_with_content(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(templating, "STATIC_DIR", tmp_path)
    css = tmp_path / "app.css"
    css.write_text("a{}")
    first = asset_version("app.css")

    css.write_text("b{}")
    stat = css.stat()
    os.utime(css, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))

    assert asset_version("app.css") != first
    assert asset_version("bestaat-niet.css") == "0"
