from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db.models import ClashItem, UploadedReport
from app.services.storage import StorageService


class PdfUnavailableError(RuntimeError):
    pass


class ReportRenderer:
    def __init__(self, storage: StorageService) -> None:
        self.storage = storage
        template_root = Path(__file__).parents[1] / "templates" / "pdf"
        self.templates = Environment(
            loader=FileSystemLoader(template_root),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render(
        self,
        *,
        report: UploadedReport,
        clashes: list[ClashItem],
        results: dict[str, dict[str, Any]],
        model_version: str,
    ) -> bytes:
        try:
            from weasyprint import HTML, default_url_fetcher  # type: ignore[import-untyped]
        except (ImportError, OSError) as error:
            raise PdfUnavailableError(
                "WeasyPrint and its native libraries are unavailable"
            ) from error

        rows = []
        for clash in clashes:
            rows.append(
                {
                    "clash": clash,
                    "analysis": results.get(clash.id),
                    "image": self._image_data_url(clash.image_path),
                }
            )
        html = self.templates.get_template("report.html").render(
            report=report,
            rows=rows,
            model_version=model_version,
        )

        def safe_fetcher(url: str, *args: object, **kwargs: object) -> dict[str, object]:
            if urlparse(url).scheme != "data":
                raise ValueError("PDF rendering blocks non-data URLs")
            return default_url_fetcher(url, *args, **kwargs)

        return HTML(string=html, url_fetcher=safe_fetcher).write_pdf()

    def _image_data_url(self, storage_path: str | None) -> str | None:
        if not storage_path:
            return None
        path = self.storage.absolute(storage_path)
        media_type = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        return f"data:{media_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
