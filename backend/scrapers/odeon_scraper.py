from backend.models import EventData
from backend.scrapers.base import BaseScraper

# cinema-api.com brukes av Odeon. Ålesund = CityAlias "AL"
SHOWS_URL = "https://services.cinema-api.com/show/stripped/no/1/1024/"
MOVIES_URL = "https://services.cinema-api.com/movie/scheduled/no/1/1024/false"

CITY_ALIAS = "AL"  # Ålesund


class OdeonScraper(BaseScraper):
    source_name = "odeon"

    def scrape(self) -> list[EventData]:
        # Hent filmdata (titler, poster, beskrivelse)
        movies_resp = self._get(MOVIES_URL)
        movies_data = movies_resp.json()
        movie_lookup = self._build_movie_lookup(movies_data.get("items", []))

        # Hent visninger for Ålesund
        shows_resp = self._get(SHOWS_URL, params={
            "CountryAlias": "no",
            "CityAlias": CITY_ALIAS,
            "Channel": "Web",
        })
        shows_data = shows_resp.json()

        events = []
        for show in shows_data.get("items", []):
            movie_id = show.get("mId", "")
            movie = movie_lookup.get(movie_id, {})

            title = movie.get("title", "")
            if not title:
                continue

            show_id = show.get("reId", "")
            screen = show.get("st", "")
            cinema = show.get("ct", "ODEON Ålesund")
            location_name = f"{cinema} – {screen}" if screen else cinema

            # Attributter (LUXE, IMAX, osv.)
            tags = [a.lower() for a in show.get("sa", [])]
            genres = [g.get("name", "") for g in movie.get("genres", []) if g.get("name")]
            tags.extend(g.lower() for g in genres)

            events.append(EventData(
                source="odeon",
                source_id=f"odeon-{show_id}",
                title=title,
                description=movie.get("shortDescription"),
                start_at=show.get("utc"),
                location_name=location_name,
                city="Ålesund",
                image_url=movie.get("posterUrl"),
                url=f"https://www.odeonkino.no/film/{movie.get('slug', '')}/" if movie.get("slug") else None,
                tags=tags,
            ))

        self.logger.info(f"Hentet {len(events)} visninger fra Odeon Ålesund")
        return events

    @staticmethod
    def _build_movie_lookup(movies: list[dict]) -> dict:
        """Bygg oppslag fra ncgId → filmdata."""
        lookup = {}
        for movie in movies:
            ncg_id = movie.get("ncgId", "")
            lookup[ncg_id] = movie
            # Versjon-IDer (NCG123V1) mapper også til filmen
            for version in movie.get("versions", []):
                v_id = version.get("ncgId", "")
                if v_id:
                    lookup[v_id] = movie
        return lookup
