from __future__ import annotations

import hashlib
import re
import shutil
import stat
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from fastapi import UploadFile


class UnsafeUploadError(ValueError):
    pass


@dataclass(frozen=True)
class StoredFile:
    original_filename: str
    media_type: str
    storage_path: str
    sha256: str
    size_bytes: int


class StorageService:
    allowed_extensions = {".html", ".htm", ".zip", ".jpg", ".jpeg", ".png"}

    def __init__(
        self,
        root: Path,
        *,
        max_upload_bytes: int,
        max_archive_entries: int,
        max_archive_uncompressed_bytes: int,
    ) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes
        self.max_archive_entries = max_archive_entries
        self.max_archive_uncompressed_bytes = max_archive_uncompressed_bytes
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile) -> StoredFile:
        original_name = Path(upload.filename or "upload").name
        safe_name = self._safe_filename(original_name)
        extension = Path(safe_name).suffix.lower()
        if extension not in self.allowed_extensions:
            raise UnsafeUploadError(f"Unsupported file extension: {extension or '(none)'}")

        directory = self.root / "uploads" / str(uuid.uuid4())
        directory.mkdir(parents=True, exist_ok=False)
        target = directory / safe_name
        digest = hashlib.sha256()
        size = 0
        prefix = bytearray()
        try:
            with target.open("wb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise UnsafeUploadError(
                            f"Upload exceeds the {self.max_upload_bytes}-byte limit"
                        )
                    if len(prefix) < 512:
                        prefix.extend(chunk[: 512 - len(prefix)])
                    digest.update(chunk)
                    destination.write(chunk)
            media_type = self._validate_signature(extension, bytes(prefix))
        except Exception:
            if target.exists():
                target.unlink()
            raise
        finally:
            await upload.close()

        return StoredFile(
            original_filename=original_name,
            media_type=media_type,
            storage_path=self.relative(target),
            sha256=digest.hexdigest(),
            size_bytes=size,
        )

    def absolute(self, storage_path: str) -> Path:
        candidate = (self.root / storage_path).resolve()
        if not candidate.is_relative_to(self.root):
            raise UnsafeUploadError("Storage path escaped the configured root")
        return candidate

    def relative(self, path: Path) -> str:
        resolved = path.resolve()
        if not resolved.is_relative_to(self.root):
            raise UnsafeUploadError("File is outside the configured storage root")
        return resolved.relative_to(self.root).as_posix()

    def prepare_report_source(self, report_id: str, source: Path) -> tuple[Path, Path]:
        report_root = self.root / "reports" / report_id
        source_root = report_root / "source"
        source_root.mkdir(parents=True, exist_ok=False)
        if source.suffix.lower() == ".zip":
            self._extract_archive(source, source_root)
            html_files = sorted(
                path for path in source_root.rglob("*") if path.suffix.lower() in {".html", ".htm"}
            )
            if not html_files:
                raise UnsafeUploadError("ZIP does not contain an HTML report")
            if len(html_files) > 1:
                raise UnsafeUploadError("ZIP must contain exactly one HTML report")
            return source_root, html_files[0]

        target = source_root / source.name
        shutil.copy2(source, target)
        return source_root, target

    def write_report_image(
        self, report_id: str, clash_id: str, data: bytes, media_type: str
    ) -> str:
        extension = ".png" if media_type == "image/png" else ".jpg"
        safe_clash_id = self._safe_filename(clash_id).removesuffix(Path(clash_id).suffix)
        target = self.root / "reports" / report_id / "images" / f"{safe_clash_id}{extension}"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self.relative(target)

    def write_artifact(self, artifact_id: str, data: bytes) -> str:
        target = self.root / "artifacts" / f"{artifact_id}.pdf"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return self.relative(target)

    def _extract_archive(self, archive: Path, destination: Path) -> None:
        with zipfile.ZipFile(archive) as file:
            entries = file.infolist()
            if len(entries) > self.max_archive_entries:
                raise UnsafeUploadError("ZIP contains too many entries")
            total_size = sum(entry.file_size for entry in entries)
            if total_size > self.max_archive_uncompressed_bytes:
                raise UnsafeUploadError("ZIP expands beyond the configured size limit")

            validated: list[tuple[zipfile.ZipInfo, Path]] = []
            for entry in entries:
                unix_mode = entry.external_attr >> 16
                if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                    raise UnsafeUploadError("ZIP symbolic links are not allowed")
                archive_path = PurePosixPath(entry.filename.replace("\\", "/"))
                if archive_path.is_absolute() or ".." in archive_path.parts:
                    raise UnsafeUploadError(f"Unsafe ZIP path: {entry.filename}")
                if any(":" in part for part in archive_path.parts):
                    raise UnsafeUploadError(f"Unsafe ZIP path: {entry.filename}")
                if entry.file_size > 10 * 1024 * 1024 and entry.compress_size == 0:
                    raise UnsafeUploadError("Suspicious ZIP compression metadata")
                if entry.compress_size and entry.file_size / entry.compress_size > 200:
                    raise UnsafeUploadError("Suspicious ZIP compression ratio")
                target = (destination / Path(*archive_path.parts)).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise UnsafeUploadError(f"Unsafe ZIP path: {entry.filename}")
                validated.append((entry, target))

            for entry, target in validated:
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with file.open(entry) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)

    @staticmethod
    def _safe_filename(filename: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(filename).name).strip(".-")
        return cleaned[:200] or "upload"

    @staticmethod
    def _validate_signature(extension: str, prefix: bytes) -> str:
        lowered = prefix.lstrip().lower()
        if extension in {".html", ".htm"} and (
            lowered.startswith(b"<!doctype html")
            or lowered.startswith(b"<html")
            or b"<table" in lowered
        ):
            return "text/html"
        if extension == ".zip" and prefix.startswith(b"PK\x03\x04"):
            return "application/zip"
        if extension == ".png" and prefix.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if extension in {".jpg", ".jpeg"} and prefix.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        raise UnsafeUploadError("File content does not match its extension")
