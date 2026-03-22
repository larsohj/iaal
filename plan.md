# Kulturapp Ålesund – Prosjektplan

> Hobbyprosjekt. Sist oppdatert: 20. mars 2026.
> Bruk dette dokumentet til å gjenoppta arbeidet i en ny sesjon.

---

## Prosjektbeskrivelse

Mobilapp som aggregerer kulturtilbud i Ålesund og omegn (Ålesund inkl. Ørskog, Sula, Giske). Viser konserter, teater, museum-arrangement, bibliotekhendelser, friluftsliv og lokale aktiviteter i én feed. Støtter push-varsler. Ikke-kommersielt hobbyprosjekt.

---

## [BESLUTTET] Teknologistack

| Lag | Valg | Begrunnelse |
|---|---|---|
| Mobilapp | React Native + Expo | Én kodebase → iOS + Android |
| iOS-bygging | EAS Build (Expo) | Cloud-basert, ingen Mac nødvendig |
| Database/API | Supabase (gratis tier) | Postgres + REST + realtime |
| Backend/scraper | Python på Render.com (gratis tier) | Enkel deploy, gratis |
| Push-varsler | Expo Push Notifications / FCM | Integrert i Expo |
| Driftskostnad | Nær null i oppstartsfasen | — |

**Arkitektur (tre lag):**
1. Python-scraper/aggregator kjøres på Render.com (cron, f.eks. hver 6. time)
2. Supabase-database med `events`-tabell
3. React Native/Expo-app leser fra Supabase

---

## [BESLUTTET] Datakilder og status

### ✅ Ferdig kartlagt og scraper skrevet

#### 1. Friskus (Ålesund, Sula, Giske)
- **Type:** Åpent REST-API, ingen autentisering
- **URL:** `https://api.friskus.com/api/v1/events?municipalities[]=<UUID>&page=1`
- **Paginering:** `meta.last_page` i JSON-svaret
- **Kommune-UUID-er:**
  - Ålesund (inkl. Ørskog): `58057c8b-b578-4082-8c11-97bfe366e5ab`
  - Sula: `db3b7632-82c3-4895-8c18-d24a559a42ad`
  - Giske: `5900890d-0709-4ea3-bc16-f853e28aaacb`
- **Felt:** `id`, `name`, `start_at`, `end_at`, `is_free`, `is_recurring`, `organization.name`, `age_group[]`, `thumbnail_url`, `slug`, `event_source` (kan være `"dnt"` — inkluderer DNT Sunnmøre automatisk)
- **Innhold:** Frivilligaktiviteter, kulturskole, bibliotek, DNT-turer, Borgund Dyreklubb
- **Scraper:** `friskus_scraper.py` ✅

#### 2. Viti museene
- **Type:** Next.js statisk JSON (Sanity CMS bak)
- **URL:** `https://www.vitimusea.no/_next/data/<buildId>/no/arrangement.json`
- **OBS:** `buildId` endres ved ny deploy — scraperen henter den dynamisk fra HTML (`__NEXT_DATA__`-scriptet)
- **Felt:** `name`, `slug.current`, `exhibitionFacts.dates[]` (startDate/endDate), `exhibitionFacts.selectMuseumArray[]`, `exhibitionFacts.exhibitionAbstract`, `exhibitionFacts.museumTag[]`, `exhibitionImage.asset.url`, `isArchived`, `_lang`
- **Filter:** kun `_lang == "no"` og `isArchived == false` og `dates` ikke tom
- **Dekker:** Jugendstilsenteret & KUBE, Sunnmøre Museum, Fiskerimuseet, Middelaldermuseet, Storeggen av Aalesund m.fl.
- **Scraper:** `viti_scraper.py` ✅

### 🔲 Kartlagt, scraper ikke skrevet ennå

#### 3. Tikkio
- **Type:** HTML-scraping, JSON-LD strukturdata i `<script type="application/ld+json">`
- **URL:** `https://tikkio.com/locations/151197-alesund`
- **Metode:**
  ```python
  soup.find("script", {"type": "application/ld+json"})
  data["itemListElement"]  # liste over alle arrangement
  ```
- **Felt per arrangement:** `name`, `startDate`, `endDate`, `location` (inkl. `geo`-koordinater), `offers` (pris), `organizer`, `image`, `url`
- **Dekker:** Terminalen Byscene, Løvenvold Theater, Fabrikken kulturscene, Sobra, Dampsentralen, Jazzsirkelen, Alnes Fyr m.m. — svært bred dekning
- **Steds-ID 151197** = Ålesund. Tilsvarende ID-er finnes trolig for Sula/Giske (ikke kartlagt)
- **Prioritet:** ⭐⭐⭐ HØY — dekker de fleste konsertscenene

#### 4. Parken kulturhus
- **Type:** HTML-scraping, server-side rendret WordPress/ASP.NET
- **URL:** `https://www.parkenkulturhus.no/program/`
- **Billettsystem:** tix.no (ikke Tikkio — derfor nødvendig separat kilde)
- **Metode:** To-stegs scraping
  1. Hent programlista — inneholder dato, tittel, undertittel, scene, status (Utsolgt / Få billetter igjen), sjanger-tags
  2. Følg lenke til hvert arrangement for klokkeslett og pris
- **Innhold:** Parken er Ålesunds største kulturscene (~500 plasser), ca. 50+ arrangement i sesongen
- **Prioritet:** ⭐⭐⭐ HØY

#### 5. Ålesund bibliotek
- **Type:** HTML-scraping, server-side rendret ASP.NET
- **URL:** `https://alesundsbiblioteka.no/` (forsiden har "Kva skjer?"-seksjon)
- **URL-mønster arrangement:** `/Kalender/CalendarEvent.aspx?Id=XXXXX&lang=1&MId1=18377`
- **Metode:** To-stegs scraping (liste → detaljer)
- **Felt:** dato (`dd.mm.yyyy`), klokkeslett (`kl. HH:MM`), tittel, sted (Ålesund bibliotek / Moa bibliotek), bilde
- **Innhold:** Bokbad, foredrag, forfattertreff, påskeverkstad, lekehjelp — genuint tillegg
- **Prioritet:** ⭐⭐ MIDDELS

#### 6. Ticketmaster
- **Type:** Offisiell REST-API
- **Registrering:** https://developer.ticketmaster.com — gratis API-nøkkel
- **Eksempel-URL:** `https://app.ticketmaster.com/discovery/v2/events.json?apikey=<KEY>&latlong=62.4723,6.1549&radius=50&unit=km&locale=no`
- **Koordinater Ålesund:** `62.4723, 6.1549`
- **Innhold:** Større konserter/shows — Ticketmaster brukes for de store navnene
- **Prioritet:** ⭐⭐ MIDDELS

#### 7. Bypatrioten
- **Type:** HTML-scraping
- **URL:** `https://bypatrioten.com/kalender/`
- **Innhold:** Åpen kalender der alle kan legge inn arrangement — bred lokal dekning
- **Metode:** BeautifulSoup, strukturert HTML
- **Prioritet:** ⭐⭐ MIDDELS (delvis overlapp med Tikkio)

### ⏸️ Vurdert og valgt bort / lavprioritert

| Kilde | Grunn |
|---|---|
| Facebook Events | Mot ToS, teknisk vanskelig, GDPR-begrenset API |
| Sunnmørsposten | Bak betalingsmur |
| Atlanterhavsparken | Smalt innhold, faste repeterende aktiviteter |
| Visit Ålesund | Mye overlapp med andre kilder |
| ODEON Kino | Kommersielle filmvisninger, ikke kulturarrangement |
| Songkick | API stengt for nye utviklere |
| Sentrumsforeningen | Dekkes av Bypatrioten |

---

## [NESTE STEG] Hva gjenstår

### Prioritert rekkefølge

1. **Skriv Tikkio-scraper** — JSON-LD, ingen autentisering, høyest prioritet
2. **Skriv Parken kulturhus-scraper** — to-stegs HTML
3. **Design Supabase-databaseskjema** — `events`-tabell med felt for alle kilder
4. **Sett opp Supabase-prosjekt** — gratis tier, hent URL og anon key
5. **Skriv bibliotek-scraper** — ASP.NET kalenderside
6. **Sett opp Ticketmaster API-nøkkel** og skriv scraper
7. **Bygg aggregator-script** som kjører alle scrapere og upsert-er til Supabase
8. **Deploy aggregator til Render.com** med cron (f.eks. `0 */6 * * *`)
9. **Start React Native/Expo-app** — liste + detaljvisning
10. **Legg til push-varsler** via Expo

---

## Supabase-skjema (forslag — ikke implementert ennå)

```sql
CREATE TABLE events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source          TEXT NOT NULL,          -- 'tikkio', 'parken', 'friskus', 'viti', 'bibliotek', 'ticketmaster'
  source_id       TEXT NOT NULL,          -- unik ID fra kilden
  title           TEXT NOT NULL,
  description     TEXT,
  start_at        TIMESTAMPTZ,
  end_at          TIMESTAMPTZ,
  is_free         BOOLEAN,
  price_text      TEXT,                   -- f.eks. "Kr 350 / Student 250"
  location_name   TEXT,                   -- f.eks. "Terminalen Byscene"
  address         TEXT,
  city            TEXT DEFAULT 'Ålesund',
  latitude        FLOAT,
  longitude       FLOAT,
  organizer       TEXT,
  image_url       TEXT,
  url             TEXT,
  tags            TEXT[],                 -- f.eks. ['konsert', 'jazz']
  age_groups      TEXT[],                 -- fra Friskus: ['children', 'family']
  is_recurring    BOOLEAN DEFAULT FALSE,
  scraped_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (source, source_id)              -- hindrer duplikater ved re-scraping
);

-- Indekser for vanlige spørringer
CREATE INDEX ON events (start_at);
CREATE INDEX ON events (city);
CREATE INDEX ON events (source);

-- Automatisk slett gamle arrangement
-- (vurder: vil du beholde historikk?)
```

**Upsert-strategi** (ved re-scraping):
```sql
INSERT INTO events (...) VALUES (...)
ON CONFLICT (source, source_id)
DO UPDATE SET
  title = EXCLUDED.title,
  start_at = EXCLUDED.start_at,
  scraped_at = EXCLUDED.scraped_at;
```

---

## Scrapere skrevet (filer)

| Fil | Kilde | Status |
|---|---|---|
| `friskus_scraper.py` | Friskus (Ålesund + Sula + Giske) | ✅ Klar |
| `viti_scraper.py` | Viti museene | ✅ Klar |
| `tikkio_scraper.py` | Tikkio | 🔲 Ikke skrevet |
| `parken_scraper.py` | Parken kulturhus | 🔲 Ikke skrevet |
| `bibliotek_scraper.py` | Ålesund bibliotek | 🔲 Ikke skrevet |
| `ticketmaster_scraper.py` | Ticketmaster API | 🔲 Ikke skrevet |
| `bypatrioten_scraper.py` | Bypatrioten | 🔲 Ikke skrevet |
| `aggregator.py` | Kjører alle og skriver til Supabase | 🔲 Ikke skrevet |

---

## Nyttige lenker og ressurser

- Tikkio Ålesund: https://tikkio.com/locations/151197-alesund
- Friskus Ålesund: https://alesund.friskus.com/events
- Friskus API: `https://api.friskus.com/api/v1/events`
- Viti museene: https://www.vitimusea.no/arrangement
- Parken kulturhus: https://www.parkenkulturhus.no/program/
- Ålesund bibliotek: https://alesundsbiblioteka.no/
- Ticketmaster Developer: https://developer.ticketmaster.com
- Bypatrioten kalender: https://bypatrioten.com/kalender/
- Supabase: https://supabase.com
- Expo / EAS Build: https://expo.dev

---

## Tekniske notater

### Friskus — viktige detaljer
- `event_source`-feltet kan være `"dnt"` → DNT Sunnmøre-turer inkluderes automatisk
- Gjentakende aktiviteter har `is_recurring: true` og `rrule`-objekt — vurder om du vil eksplodere disse til individuelle datoer eller vise dem som gjentakende
- `age_group[]` verdier: `"children"`, `"teenager"`, `"family"`, `"senior"`, `"pensioner"`

### Viti — viktige detaljer
- Build-ID hentes dynamisk fra `__NEXT_DATA__` i HTML — regex: `"buildId"\s*:\s*"([^"]+)"`
- Ett arrangement kan ha flere datoer i `exhibitionFacts.dates[]` — scraperen lager én rad per dato
- Filtrer på `_lang == "no"` (engelske kopier finnes med `_lang == "en_GB"`)
- Filtrer på `isArchived != true`
- Filtrer bort arrangement med tom `dates[]` (evergreen-innhold)

### Tikkio — fremgangsmåte (ikke implementert)
```python
import requests
from bs4 import BeautifulSoup
import json

url = "https://tikkio.com/locations/151197-alesund"
html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}).text
soup = BeautifulSoup(html, "html.parser")
ld_json = soup.find("script", {"type": "application/ld+json"})
data = json.loads(ld_json.string)
events = data["itemListElement"]
# Hvert element har: name, startDate, endDate, location (geo), offers, organizer, image, url
```

### Render.com deploy
- Gratis tier: 750 timer/måned, spinner ned etter inaktivitet
- For cron-scraper: bruk Render Cron Jobs (ikke web service)
- Miljøvariabler: `SUPABASE_URL`, `SUPABASE_KEY`
- Krav: `requirements.txt` med `requests`, `beautifulsoup4`, `supabase`

### React Native / Expo oppstart
```bash
npx create-expo-app kulturapp-alesund
cd kulturapp-alesund
npx expo install @supabase/supabase-js
npx expo install expo-notifications
```

---

## App-funksjoner (MVP)

1. **Hendelsesliste** — sortert på dato, filtrering på kategori/sted
2. **Detaljvisning** — tittel, dato, sted, pris, bilde, lenke til billettkjøp
3. **Push-varsler** — brukeren abonnerer på kategorier eller steder
4. **«Tips oss»** — enkel innmelding av arrangement som mangler (Facebook-gap)

## App-funksjoner (v2, etter MVP)

- Kartvisning
- Lagre favoritter
- Søk
- Kalenderintegrering (legg til i kalender)
- Filter på gratis/betalt
- Aldersfilter (barn, familie, etc.)
