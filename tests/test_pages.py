"""Every page route renders an HTML page."""
import pytest

from app import CONVERSIONS, MAX_FILE_SIZE

PAGE_ROUTES = ["/", "/jpgtopng", "/pngtojpg", "/webptopng", "/bmptopng", "/pngtopdf"]


@pytest.mark.parametrize("route", PAGE_ROUTES)
def test_page_renders_html(client, route):
    response = client.get(route)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<html" in response.data.lower()


@pytest.mark.parametrize("name", list(CONVERSIONS))
def test_converter_page_uses_api_rules(client, name):
    """The client-side checks are rendered from the same table the API enforces."""
    html = client.get(f"/{name}").get_data(as_text=True)
    rules = CONVERSIONS[name]

    assert f'data-endpoint="/api/{name}"' in html
    assert f'data-extensions="{",".join(rules.extensions)}"' in html
    assert f'data-output-ext="{rules.output_ext[1:]}"' in html
    assert f'data-max-bytes="{MAX_FILE_SIZE}"' in html
