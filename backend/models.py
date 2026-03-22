from dataclasses import dataclass, field, asdict


@dataclass
class EventData:
    """Felles skjema for alle scrapers. Matcher events-tabellen i Supabase."""

    source: str
    source_id: str
    title: str
    description: str | None = None
    start_at: str | None = None  # ISO 8601
    end_at: str | None = None  # ISO 8601
    is_free: bool | None = None
    price_text: str | None = None
    location_name: str | None = None
    address: str | None = None
    city: str = "Ålesund"
    latitude: float | None = None
    longitude: float | None = None
    organizer: str | None = None
    image_url: str | None = None
    url: str | None = None
    tags: list[str] = field(default_factory=list)
    age_groups: list[str] = field(default_factory=list)
    is_recurring: bool = False

    def to_dict(self) -> dict:
        """Konverter til dict for Supabase upsert. Fjerner None-verdier."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}
