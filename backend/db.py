import logging
import os

from dotenv import load_dotenv
from supabase import create_client, Client

from backend.models import EventData

load_dotenv()

logger = logging.getLogger("db")


def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL og SUPABASE_KEY må være satt")
    return create_client(url, key)


def upsert_events(events: list[EventData], client: Client | None = None) -> int:
    """Upsert hendelser til Supabase. Returnerer antall upserted."""
    if not events:
        return 0

    if client is None:
        client = get_client()

    # Batch i grupper på 500 (Supabase anbefaler < 1000 per request)
    batch_size = 500
    total = 0

    for i in range(0, len(events), batch_size):
        batch = events[i : i + batch_size]
        rows = [e.to_dict() for e in batch]

        result = (
            client.table("events")
            .upsert(rows, on_conflict="source,source_id")
            .execute()
        )
        total += len(result.data)

    logger.info(f"Upserted {total} hendelser til Supabase")
    return total


def delete_stale_events(source: str, current_ids: set[str], client: Client | None = None) -> int:
    """Slett hendelser som ikke lenger finnes i kilden."""
    if client is None:
        client = get_client()

    # Hent alle source_id-er for denne kilden
    result = (
        client.table("events")
        .select("source_id")
        .eq("source", source)
        .execute()
    )

    existing_ids = {row["source_id"] for row in result.data}
    stale_ids = existing_ids - current_ids

    if not stale_ids:
        return 0

    # Slett i batches
    deleted = 0
    for stale_id in stale_ids:
        client.table("events").delete().eq("source", source).eq("source_id", stale_id).execute()
        deleted += 1

    logger.info(f"Slettet {deleted} utdaterte hendelser fra {source}")
    return deleted
