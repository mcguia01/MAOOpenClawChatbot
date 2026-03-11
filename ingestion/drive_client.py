"""Google Drive client — authenticates via service account and provides file
listing + download helpers for the ingestion pipeline.

Supported MIME types:
  - .docx  → application/vnd.openxmlformats-officedocument.wordprocessingml.document
  - .pptx  → application/vnd.openxmlformats-officedocument.presentationml.presentation
  - .xlsx  → application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

TODO: Add Google Drive Push Notifications (webhooks) as an upgrade path to
      trigger re-ingestion automatically on file change instead of polling.
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config.settings import get_settings

logger = logging.getLogger(__name__)

_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

_SUPPORTED_MIME_TYPES: dict[str, str] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}


class DriveClient:
    """Thin wrapper around the Google Drive v3 API."""

    def __init__(self) -> None:
        settings = get_settings()
        credentials = service_account.Credentials.from_service_account_file(
            settings.google_service_account_json_path,
            scopes=_SCOPES,
        )
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        logger.info("DriveClient initialised with service account")

    def list_files(self, folder_id: str) -> list[dict[str, Any]]:
        """Return metadata for all supported files in the given Drive folder.

        Args:
            folder_id: The Google Drive folder ID to list.

        Returns:
            List of dicts with keys: id, name, mimeType, modifiedTime.
            Files with unsupported MIME types are silently skipped.
        """
        query = (
            f"'{folder_id}' in parents "
            "and trashed = false "
            "and ("
            + " or ".join(f"mimeType='{m}'" for m in _SUPPORTED_MIME_TYPES)
            + ")"
        )
        results: list[dict[str, Any]] = []
        page_token: str | None = None

        while True:
            response = (
                self._service.files()
                .list(
                    q=query,
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                    pageToken=page_token,
                    pageSize=100,
                )
                .execute()
            )
            for file in response.get("files", []):
                if file["mimeType"] not in _SUPPORTED_MIME_TYPES:
                    logger.warning(
                        "Skipping unsupported MIME type '%s' for file '%s'",
                        file["mimeType"],
                        file["name"],
                    )
                    continue
                results.append(file)

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        logger.info("Found %d supported files in folder '%s'", len(results), folder_id)
        return results

    def download_file(self, file_id: str, file_name: str) -> Path:
        """Download a Drive file to a system temp directory.

        Args:
            file_id: Google Drive file ID.
            file_name: Original filename (used to infer extension).

        Returns:
            Path to the downloaded local file.
        """
        tmp_dir = Path(tempfile.mkdtemp(prefix="openclaw_"))
        safe_name = Path(file_name).name  # strip any directory components from Drive filename
        dest_path = tmp_dir / safe_name

        request = self._service.files().get_media(fileId=file_id)
        with dest_path.open("wb") as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        logger.info("Downloaded '%s' → '%s'", file_name, dest_path)
        return dest_path
