"""Ingestion pipeline orchestrator.

Full pipeline steps for a single run:
  1. List all supported files in the Google Drive folder
  2. For each file:
     a. Download to a temp directory
     b. Parse by file extension (.docx / .pptx / .xlsx)
     c. Chunk the parsed items
     d. Embed + upsert chunks to Pinecone
     e. Delete the temp file
  3. Log a summary of results

Run as a module:
  python -m ingestion.pipeline
"""

import logging
import shutil
from pathlib import Path

from config.settings import get_settings
from embeddings.vector_store import upsert_chunks
from ingestion.chunker import chunk
from ingestion.drive_client import DriveClient
from ingestion.parsers import parse_docx, parse_pptx, parse_xlsx

logger = logging.getLogger(__name__)

_PARSER_MAP = {
    ".docx": parse_docx,
    ".pptx": parse_pptx,
    ".xlsx": parse_xlsx,
}


def run_ingestion(folder_id: str | None = None) -> dict[str, int]:
    """Execute the full ingestion pipeline for the configured Drive folder.

    Args:
        folder_id: Override the folder ID from settings (useful for testing).

    Returns:
        Summary dict: {"total": int, "succeeded": int, "failed": int}
    """
    settings = get_settings()
    target_folder = folder_id or settings.google_drive_folder_id

    logger.info("=== Starting OpenClaw ingestion run (folder: %s) ===", target_folder)
    client = DriveClient()

    files = client.list_files(target_folder)
    logger.info("Found %d files to process", len(files))

    succeeded = 0
    failed = 0
    tmp_paths: list[Path] = []

    for file_meta in files:
        file_id: str = file_meta["id"]
        file_name: str = file_meta["name"]
        suffix = Path(file_name).suffix.lower()
        parser = _PARSER_MAP.get(suffix)

        if parser is None:
            logger.warning("No parser for extension '%s' on file '%s', skipping", suffix, file_name)
            continue

        local_path: Path | None = None
        try:
            logger.info("Processing '%s' ...", file_name)

            # Step 1 — Download
            local_path = client.download_file(file_id, file_name)
            tmp_paths.append(local_path)

            # Step 2 — Parse
            parsed = parser(local_path)
            logger.info("  Parsed %d items from '%s'", len(parsed), file_name)

            # Step 3 — Chunk
            chunks = chunk(parsed)
            logger.info("  Chunked into %d chunks", len(chunks))

            # Step 4 — Embed + Upsert
            upsert_chunks(chunks)
            logger.info("  Upserted %d chunks to Pinecone", len(chunks))

            succeeded += 1

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to process '%s': %s", file_name, exc, exc_info=True)
            failed += 1

        finally:
            # Step 5 — Cleanup temp file
            if local_path is not None and local_path.exists():
                try:
                    shutil.rmtree(local_path.parent, ignore_errors=True)
                except Exception:  # noqa: BLE001
                    pass

    summary = {"total": len(files), "succeeded": succeeded, "failed": failed}
    logger.info(
        "=== Ingestion complete: %d total, %d succeeded, %d failed ===",
        summary["total"],
        summary["succeeded"],
        summary["failed"],
    )
    return summary


if __name__ == "__main__":
    import logging as _logging

    _logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_ingestion()
