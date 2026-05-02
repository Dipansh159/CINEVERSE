"""
enrich_cache_tmdb.py
--------------------
One-time script to enrich movies_cache.json with director, genres, and overview
using the TMDB API directly. Much faster and more reliable than AI-based enrichment.

Run from the project root:
    python backend/enrich_cache_tmdb.py

After completion, all movie pages will show director/genre/synopsis instantly.
Safe to re-run — skips movies already fully enriched.
"""

import os
import json
import time

import requests
from dotenv import load_dotenv

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
CACHE_PATH   = os.path.join(PROJECT_ROOT, "Home_Page", "movies_cache.json")

TMDB_BASE     = "https://api.themoviedb.org/3"
SLEEP_BETWEEN = 0.25   # TMDB allows 40 requests/sec — 0.25s is very safe
CHECKPOINT    = 50      # save every N movies

session = requests.Session()
session.headers.update({"Accept": "application/json"})


def tmdb_get(path, params=None):
    params = {**(params or {}), "api_key": TMDB_API_KEY}
    try:
        resp = session.get(TMDB_BASE + path, params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None


def enrich_movie(movie):
    """Fetch director, genres, overview from TMDB for a single movie."""
    tmdb_id = movie.get("tmdb_id") or movie.get("id")
    if not tmdb_id:
        return False

    details = tmdb_get(f"/movie/{tmdb_id}", {
        "append_to_response": "credits",
        "language": "en-US"
    })
    if not details or not details.get("id"):
        return False

    # Director
    crew = details.get("credits", {}).get("crew", [])
    director = next((c["name"] for c in crew if c.get("job") == "Director"), "Unknown")

    # Genres
    genres = [g["name"] for g in details.get("genres", [])]

    # Overview
    overview = (details.get("overview") or "").strip() or "No synopsis available."

    movie["director"] = director
    movie["genres"] = genres
    movie["overview"] = overview

    # Also fill in poster/backdrop if missing
    if not movie.get("poster_url") and details.get("poster_path"):
        movie["poster_url"] = "https://image.tmdb.org/t/p/w500" + details["poster_path"]
    if not movie.get("backdrop_url") and details.get("backdrop_path"):
        movie["backdrop_url"] = "https://image.tmdb.org/t/p/w780" + details["backdrop_path"]

    return True


def main():
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY not set in backend/.env")

    print(f"Loading cache: {CACHE_PATH}")
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        movies = json.load(f)
    print(f"Total movies in cache: {len(movies)}")

    needs = [
        m for m in movies
        if not m.get("director") or not m.get("genres") or not m.get("overview")
           or m.get("director") == "Unknown"
    ]
    print(f"Movies needing enrichment: {len(needs)}")
    if not needs:
        print("All movies already enriched! Nothing to do.")
        return

    enriched = 0
    failed = 0

    for i, movie in enumerate(needs):
        title = movie.get("title") or movie.get("name") or "Unknown"
        print(f"[{i+1}/{len(needs)}] {title} … ", end="", flush=True)

        ok = enrich_movie(movie)
        if ok:
            print(f"OK  [{movie['director']} | {', '.join(movie['genres'][:3])}]")
            enriched += 1
        else:
            print("FAILED")
            failed += 1

        if enriched > 0 and enriched % CHECKPOINT == 0:
            print(f"  ↳ Checkpoint: saving {enriched} enriched so far…")
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(movies, f, indent=2, ensure_ascii=False)

        time.sleep(SLEEP_BETWEEN)

    print(f"\nSaving final cache → {CACHE_PATH}")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done!  Enriched: {enriched}  |  Failed/skipped: {failed}")
    print("Refresh the page — data will now appear instantly.")


if __name__ == "__main__":
    main()
