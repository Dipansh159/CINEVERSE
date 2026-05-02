"""
enrich_cache.py
---------------
Enriches movies_cache.json with director, genres, and overview
by fetching details from TMDB for each movie that is missing them.

Run once from the backend/ directory:
    python enrich_cache.py

This uses the same TMDB API key and session as tmdb_app.py.
It is safe to re-run — it skips movies that already have all three fields.
"""

import os
import json
import time

try:
    from tmdb_app import tmdb_get
except ImportError:
    from backend.tmdb_app import tmdb_get

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CACHE_PATH = os.path.join(PROJECT_ROOT, "Home_Page", "movies_cache.json")
SLEEP = 0.22   # seconds between TMDB requests (respect rate limit)

print(f"Loading cache from: {CACHE_PATH}")
with open(CACHE_PATH, "r", encoding="utf-8") as f:
    movies = json.load(f)

print(f"Total movies in cache: {len(movies)}")

needs_enrichment = [
    m for m in movies
    if not m.get("director") or not m.get("genres") or not m.get("overview")
]
print(f"Movies needing enrichment: {len(needs_enrichment)}")

enriched = 0
failed = 0

for i, movie in enumerate(needs_enrichment):
    tmdb_id = movie.get("tmdb_id") or movie.get("id")
    if not tmdb_id:
        continue

    title = movie.get("title", "Unknown")
    print(f"[{i+1}/{len(needs_enrichment)}] Enriching: {title} (ID: {tmdb_id})")

    details = tmdb_get(
        f"/movie/{tmdb_id}",
        {"append_to_response": "credits", "language": "en-US"}
    )

    if not details or not details.get("id"):
        print(f"  FAILED — TMDB returned nothing for {title}")
        failed += 1
        time.sleep(SLEEP)
        continue

    # Director
    crew = details.get("credits", {}).get("crew", [])
    director = next((c["name"] for c in crew if c.get("job") == "Director"), "Unknown")

    # Genres
    genres = [g["name"] for g in details.get("genres", [])]

    # Overview
    overview = details.get("overview", "").strip() or "No synopsis available."

    # Patch the movie dict directly in the main list
    movie["director"] = director
    movie["genres"] = genres
    movie["overview"] = overview

    # Also update poster/backdrop if missing
    if not movie.get("poster_url") and details.get("poster_path"):
        movie["poster_url"] = "https://image.tmdb.org/t/p/w500" + details["poster_path"]
    if not movie.get("backdrop_url") and details.get("backdrop_path"):
        movie["backdrop_url"] = "https://image.tmdb.org/t/p/w780" + details["backdrop_path"]

    print(f"  OK — Director: {director}, Genres: {', '.join(genres)}")
    enriched += 1

    # Save every 50 movies as a checkpoint
    if enriched % 50 == 0:
        print(f"  [Checkpoint] Saving {enriched} enriched movies so far...")
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(movies, f, indent=2, ensure_ascii=False)

    time.sleep(SLEEP)

# Final save
print(f"\nFinal save → {CACHE_PATH}")
with open(CACHE_PATH, "w", encoding="utf-8") as f:
    json.dump(movies, f, indent=2, ensure_ascii=False)

print(f"\nDone! Enriched: {enriched} | Failed/skipped: {failed}")
print("Restart your Flask server and reload the page — metadata will now show instantly.")
