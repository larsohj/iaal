# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**iaal** (Kultur i Ålesund og omland) — hobbyprosjekt. Mobilapp som aggregerer kulturtilbud i Ålesund-regionen (Ålesund inkl. Ørskog, Sula, Giske) i én feed.

### Architecture (three layers)

1. **Python scrapers** — henter arrangementsdata fra ulike kilder (Friskus API, Viti museene, Tikkio, Parken kulturhus, bibliotek, Ticketmaster, Bypatrioten). Kjøres som cron på Render.com.
2. **Supabase** (gratis tier) — Postgres-database med `events`-tabell. Scraperne upsert-er hit.
3. **React Native / Expo app** — leser fra Supabase, viser hendelser, push-varsler.

### Data sources

Se `plan.md` for komplett oversikt over datakilder, API-detaljer, scraper-status og tekniske notater per kilde.

## Development Environment

- **R 4.5.1** med renv for pakkehåndtering (kun renv selv installert foreløpig)
- **Package repo:** Posit Package Manager på `packagemanager.posit.sbm.no` (bruk binaries, ikke kompiler fra source)
- **Python** brukes for scraperne (requests, beautifulsoup4, supabase)

### Common Commands

```bash
# Restore R environment
Rscript -e "renv::restore()"

# Install new R package and snapshot
Rscript -e "renv::install('pakkenavn'); renv::snapshot()"

# Run Python scraper (eksempel)
python friskus_scraper.py
python viti_scraper.py
```

## Key Files

| Fil | Beskrivelse |
|---|---|
| `plan.md` | Prosjektplan med teknologivalg, datakilder, DB-skjema og prioritert gjenstående arbeid |
| `renv.lock` | R dependency lockfile |
| `.Rprofile` | Aktiverer renv ved oppstart |
