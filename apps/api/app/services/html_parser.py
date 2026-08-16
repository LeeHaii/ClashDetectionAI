from __future__ import annotations

import base64
import binascii
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Tag

from app.schemas.analysis import ElementMetadata, ParsedClash, ParseResult, RowError


class HtmlParser:
    _distance_pattern = re.compile(
        r"(?P<value>[-+]?\d+(?:[.,]\d+)?)\s*(?P<unit>mm|cm|m|in|inch|inches|ft|feet)?",
        re.IGNORECASE,
    )
    _unit_factors = {
        None: 1.0,
        "m": 1.0,
        "mm": 0.001,
        "cm": 0.01,
        "in": 0.0254,
        "inch": 0.0254,
        "inches": 0.0254,
        "ft": 0.3048,
        "feet": 0.3048,
    }

    def __init__(self, parser_version: str, *, max_embedded_image_bytes: int = 20 * 1024 * 1024):
        self.parser_version = parser_version
        self.max_embedded_image_bytes = max_embedded_image_bytes

    def parse(self, html_path: Path, source_root: Path) -> ParseResult:
        if not html_path.resolve().is_relative_to(source_root.resolve()):
            raise ValueError("HTML report is outside its isolated source directory")
        soup = BeautifulSoup(html_path.read_bytes(), "lxml")
        result = ParseResult(parser_version=self.parser_version)
        rows = soup.find_all("tr", class_="contentRow")
        data_row_index = 0
        for source_index, row in enumerate(rows, start=1):
            cells = row.find_all("td", recursive=False)
            if len(cells) < 20:
                continue
            data_row_index += 1
            try:
                result.clashes.append(
                    self._parse_row(
                        row_index=data_row_index,
                        cells=cells,
                        html_path=html_path,
                        source_root=source_root,
                    )
                )
            except (ValueError, KeyError) as error:
                result.errors.append(RowError(row_index=source_index, message=str(error)))
        if not result.clashes and not result.errors:
            result.errors.append(RowError(row_index=0, message="No Navisworks clash rows found"))
        return result

    def _parse_row(
        self,
        *,
        row_index: int,
        cells: list[Tag],
        html_path: Path,
        source_root: Path,
    ) -> ParsedClash:
        clash_id = self._text(cells[1])
        if not clash_id:
            raise ValueError("Clash name is empty")
        distance_raw = self._text(cells[3]) or None
        distance_m = self.parse_distance(distance_raw) if distance_raw else None
        image_reference, image_data, image_type = self._image(
            cells[0], html_path=html_path, source_root=source_root
        )
        return ParsedClash(
            row_index=row_index,
            clash_id=clash_id,
            image_reference=image_reference,
            embedded_image=image_data,
            embedded_media_type=image_type,
            distance_raw=distance_raw,
            distance_m=distance_m,
            grid=self._text(cells[4]) or None,
            clash_point=self._text(cells[7]) or None,
            elements=[
                ElementMetadata(
                    element_id=self._element_id(cells[8]),
                    layer=self._text(cells[9]) or None,
                    size=self._text(cells[10]) or None,
                ),
                ElementMetadata(
                    element_id=self._element_id(cells[14]),
                    layer=self._text(cells[15]) or None,
                    size=self._text(cells[16]) or None,
                ),
            ],
            source_metadata={
                "status": self._text(cells[2]),
                "date_found": self._text(cells[5]),
                "clash_group": self._text(cells[6]),
            },
        )

    def parse_distance(self, raw: str) -> float:
        match = self._distance_pattern.search(raw.strip())
        if not match:
            raise ValueError(f"Unrecognized distance: {raw!r}")
        value = float(match.group("value").replace(",", "."))
        unit = match.group("unit")
        factor = self._unit_factors[unit.lower() if unit else None]
        return value * factor

    def _image(
        self, cell: Tag, *, html_path: Path, source_root: Path
    ) -> tuple[str | None, bytes | None, str | None]:
        image = cell.find("img")
        if image is None or not image.get("src"):
            return None, None, None
        source = str(image["src"]).strip()
        if source.lower().startswith("data:"):
            return self._embedded_image(source)

        parsed = urlparse(unquote(source).replace("\\", "/"))
        if parsed.scheme or parsed.netloc:
            raise ValueError("Remote or absolute image references are not allowed")
        relative = PurePosixPath(parsed.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe image path in report")
        candidate = (html_path.parent / Path(*relative.parts)).resolve()
        if not candidate.is_relative_to(source_root.resolve()):
            raise ValueError("Image path escaped the report directory")
        if not candidate.is_file():
            raise ValueError(f"Referenced image was not found: {source}")
        if candidate.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            raise ValueError("Referenced image is not JPG or PNG")
        return candidate.relative_to(source_root.resolve()).as_posix(), None, None

    def _embedded_image(self, source: str) -> tuple[None, bytes, str]:
        match = re.fullmatch(
            r"data:(image/(?:png|jpeg));base64,([A-Za-z0-9+/=\s]+)", source, re.IGNORECASE
        )
        if not match:
            raise ValueError("Embedded image must be a base64 PNG or JPEG")
        try:
            data = base64.b64decode(match.group(2), validate=True)
        except binascii.Error as error:
            raise ValueError("Embedded image contains invalid base64") from error
        if len(data) > self.max_embedded_image_bytes:
            raise ValueError("Embedded image exceeds the size limit")
        media_type = match.group(1).lower()
        valid = (media_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or (
            media_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff")
        )
        if not valid:
            raise ValueError("Embedded image content does not match its media type")
        return None, data, media_type

    @staticmethod
    def _text(cell: Tag) -> str:
        return cell.get_text(" ", strip=True)

    @classmethod
    def _element_id(cls, cell: Tag) -> str | None:
        value = re.sub(r"^Element\s+ID\s*:\s*", "", cls._text(cell), flags=re.IGNORECASE)
        return value or None
