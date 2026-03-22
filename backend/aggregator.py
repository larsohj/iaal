import logging
import os
import sys
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify

from backend.db import upsert_events
from backend.scrapers.friskus_scraper import FriskusScraper
from backend.scrapers.viti_scraper import VitiScraper
from backend.scrapers.tikkio_scraper import TikkioScraper
from backend.scrapers.parken_scraper import ParkenScraper
from backend.scrapers.bibliotek_scraper import BibliotekScraper
from backend.scrapers.bypatrioten_scraper import BypatriotenScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("aggregator")

last_run = {"time": None, "events": 0, "failed": []}


def run_scrapers():
    scrapers = [
        FriskusScraper(),
        VitiScraper(),
        TikkioScraper(),
        ParkenScraper(),
        BibliotekScraper(),
        BypatriotenScraper(),
    ]

    all_events = []
    failed = []

    for scraper in scrapers:
        try:
            events = scraper.scrape()
            logger.info(f"{scraper.source_name}: {len(events)} hendelser")
            all_events.extend(events)
        except Exception as e:
            logger.error(f"{scraper.source_name} feilet: {e}")
            failed.append(scraper.source_name)

    if all_events:
        upsert_events(all_events)

    last_run["time"] = datetime.now().isoformat()
    last_run["events"] = len(all_events)
    last_run["failed"] = failed

    logger.info(f"Ferdig. Totalt: {len(all_events)} hendelser fra {len(scrapers) - len(failed)}/{len(scrapers)} kilder")


# Flask-app for health check (Render krever en HTTP-server)
app = Flask(__name__)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok", "last_run": last_run})


@app.route("/run", methods=["POST"])
def trigger_run():
    run_scrapers()
    return jsonify({"status": "done", "last_run": last_run})


if __name__ == "__main__":
    # Kjør scraperne én gang ved oppstart
    run_scrapers()

    # Sett opp scheduler: kjør hver 6. time
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_scrapers, "interval", hours=6)
    scheduler.start()

    # Start webserver
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
