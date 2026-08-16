import base64

import pytest

from app.services.html_parser import HtmlParser
from tests.helpers import navisworks_html


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("-0.062", -0.062),
        ("-62 mm", -0.062),
        ("-6.2 cm", -0.062),
        ("-2 in", -0.0508),
        ("-1 ft", -0.3048),
    ],
)
def test_normalizes_distance_units(raw: str, expected: float) -> None:
    assert HtmlParser("navisworks-v1").parse_distance(raw) == pytest.approx(expected)


def test_parses_all_trusted_fields_and_embedded_image(tmp_path) -> None:
    png = b"\x89PNG\r\n\x1a\n" + b"test-image"
    source = "data:image/png;base64," + base64.b64encode(png).decode()
    html_path = tmp_path / "report.html"
    html_path.write_bytes(navisworks_html(source))

    result = HtmlParser("navisworks-v1").parse(html_path, tmp_path)

    assert not result.errors
    assert len(result.clashes) == 1
    clash = result.clashes[0]
    assert clash.clash_id == "cd-test-001"
    assert clash.distance_m == pytest.approx(-0.062)
    assert clash.grid == "D-6 : Level 2"
    assert clash.clash_point == "1.0, 2.0, 3.0"
    assert clash.elements[0].element_id == "123"
    assert clash.elements[0].layer == "Level 2"
    assert clash.elements[1].size == "300 x 600 mm"
    assert clash.embedded_image == png


def test_records_unsafe_image_as_row_error(tmp_path) -> None:
    html_path = tmp_path / "report.html"
    html_path.write_bytes(navisworks_html("../../outside.jpg"))

    result = HtmlParser("navisworks-v1").parse(html_path, tmp_path)

    assert not result.clashes
    assert "Unsafe image path" in result.errors[0].message
