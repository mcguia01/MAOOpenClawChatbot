"""One-time setup script — creates and deploys the Vertex AI Vector Search index.

Run this ONCE before first use:
  python scripts/setup_vertex_index.py

The script will:
  1. Create a MatchingEngineIndex (streaming-update, DOT_PRODUCT_DISTANCE, 768 dims)
  2. Wait for the index to become ACTIVE (~10–30 minutes)
  3. Create a MatchingEngineIndexEndpoint (public endpoint)
  4. Deploy the index to the endpoint
  5. Print the three IDs to add to your .env file

Prerequisites
-------------
  - GOOGLE_CLOUD_PROJECT and GOOGLE_SERVICE_ACCOUNT_JSON_PATH set in .env
  - Service account has roles/aiplatform.user and roles/iam.serviceAccountTokenCreator
"""

import logging
import sys
import time
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.oauth2 import service_account
from google.cloud import aiplatform

from config.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DISPLAY_NAME = "openclaw-mao"
_DEPLOYED_INDEX_ID = "openclaw_mao"
_DIMENSIONS = 768
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def main() -> None:
    settings = get_settings()

    credentials = service_account.Credentials.from_service_account_file(
        settings.google_service_account_json_path,
        scopes=_VERTEX_SCOPES,
    )

    aiplatform.init(
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        credentials=credentials,
    )

    # ── Step 1: Create index ───────────────────────────────────────────────
    logger.info("Creating Vertex AI Vector Search index '%s' ...", _DISPLAY_NAME)
    logger.info("This typically takes 10–30 minutes. Please wait.")

    index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=_DISPLAY_NAME,
        dimensions=_DIMENSIONS,
        approximate_neighbors_count=150,
        distance_measure_type="DOT_PRODUCT_DISTANCE",
        index_update_method="STREAM_UPDATE",
        description="OpenClaw MAO process documents — text-embedding-004 768-dim",
    )

    # ── Step 2: Wait for index to become ACTIVE ────────────────────────────
    logger.info("Waiting for index '%s' to become ACTIVE ...", index.resource_name)
    while True:
        index = aiplatform.MatchingEngineIndex(index_name=index.resource_name)
        state = index.gca_resource.state.name  # type: ignore[attr-defined]
        logger.info("  Index state: %s", state)
        if state == "INDEX_STATE_ACTIVE" or state == "ACTIVE":
            break
        if "ERROR" in state.upper():
            logger.error("Index creation failed with state: %s", state)
            sys.exit(1)
        time.sleep(60)

    index_id = index.resource_name.split("/")[-1]
    logger.info("Index ACTIVE. Index ID: %s", index_id)

    # ── Step 3: Create index endpoint ─────────────────────────────────────
    logger.info("Creating index endpoint '%s-endpoint' ...", _DISPLAY_NAME)
    endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=f"{_DISPLAY_NAME}-endpoint",
        public_endpoint_enabled=True,
        description="OpenClaw MAO process documents endpoint",
    )
    endpoint_id = endpoint.resource_name.split("/")[-1]
    logger.info("Endpoint created. Endpoint ID: %s", endpoint_id)

    # ── Step 4: Deploy index to endpoint ──────────────────────────────────
    logger.info("Deploying index to endpoint (deployed_index_id='%s') ...", _DEPLOYED_INDEX_ID)
    endpoint.deploy_index(
        index=index,
        deployed_index_id=_DEPLOYED_INDEX_ID,
        display_name=_DISPLAY_NAME,
        min_replica_count=1,
        max_replica_count=1,
    )
    logger.info("Deployment complete.")

    # ── Step 5: Print IDs for .env ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Setup complete! Add the following to your .env file:")
    print("=" * 60)
    print(f"VERTEX_VECTOR_SEARCH_INDEX_ID={index_id}")
    print(f"VERTEX_VECTOR_SEARCH_ENDPOINT_ID={endpoint_id}")
    print(f"VERTEX_VECTOR_SEARCH_DEPLOYED_INDEX_ID={_DEPLOYED_INDEX_ID}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
