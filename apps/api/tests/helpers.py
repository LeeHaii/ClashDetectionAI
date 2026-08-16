from __future__ import annotations


def navisworks_html(image_source: str | None = None, *, distance: str = "-0.062") -> bytes:
    values = [""] * 20
    values[1] = "cd-test-001"
    values[2] = "New"
    values[3] = distance
    values[4] = "D-6 : Level 2"
    values[5] = "2026-08-16"
    values[6] = "Mechanical vs Structural"
    values[7] = "1.0, 2.0, 3.0"
    values[8] = "Element ID: 123"
    values[9] = "Level 2"
    values[10] = "50 mm"
    values[14] = "Element ID: 456"
    values[15] = "Level 1"
    values[16] = "300 x 600 mm"
    cells = []
    for index, value in enumerate(values):
        if index == 0 and image_source:
            cells.append(f'<td><img src="{image_source}"></td>')
        else:
            cells.append(f"<td>{value}</td>")
    return (
        '<!doctype html><html><body><table><tr class="contentRow">'
        + "".join(cells)
        + "</tr></table></body></html>"
    ).encode()
