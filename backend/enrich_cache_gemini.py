"""
enrich_cache_gemini.py
----------------------
One-time script to enrich movies_cache.json with director, genres, and overview.
Uses Gemini REST API directly (bypasses SDK routing issues).

Run once from the project root:
    python backend/enrich_cache_gemini.py

After completion, all movie pages will show director/genre/synopsis instantly.
Safe to re-run — skips movies already fully enriched.
"""

import os
import re
import json
import time

import requests
from dotenv import load_dotenv

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))

GENAI_API_KEY    = os.getenv("GENAI_API_KEY", "")
CACHE_PATH       = os.path.join(PROJECT_ROOT, "Home_Page", "movies_cache.json")

# gemini-2.5-flash-lite confirmed available via ListModels for this key
GEMINI_MODEL     = "gemini-2.5-flash-lite"
GEMINI_REST_URL  = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GENAI_API_KEY}"
)

SLEEP_BETWEEN    = 4.5   # 15 RPM free tier → 4 s gap keeps us safely under
CHECKPOINT_EVERY = 10    # save to disk every N enriched movies

# ---------------------------------------------------------------------------

def extract_json(text):
    """Robustly extract the first {...} JSON block from model output."""
    m = re.search(r'\{[\s\S]*\}', text)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


def get_movie_info(title, year, retries=3):
    """Return {director, genres, overview} for a film via Gemini REST API."""
    prompt = (
        f'You are a film database. Return ONLY a valid JSON object (no extra text) '
        f'for the film "{title}" ({year}). '
        'Required keys:\n'
        '  "director": real director full name (string)\n'
        '  "genres": list of genres e.g. ["Drama", "Thriller"] (array)\n'
        '  "overview": 2-3 sentence plot synopsis using correct in-universe '
        'CHARACTER NAMES (not actor names). Accurate to the actual film.\n'
        'If truly unknown, use null for that field.'
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "maxOutputTokens": 300}
    }

    for attempt in range(retries):
        try:
            resp = requests.post(GEMINI_REST_URL, json=payload, timeout=20)
            if resp.status_code == 429:
                wait = 35 * (attempt + 1)
                print(f"\n  [Rate limit 429] Waiting {wait}s before retry {attempt+1}/{retries}…",
                      end="", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            text_out = data["candidates"][0]["content"]["parts"][0]["text"]
            return extract_json(text_out)
        except requests.exceptions.HTTPError as exc:
            raise
        except Exception as exc:
            if attempt < retries - 1:
                time.sleep(5)
                continue
            raise
    raise RuntimeError(f"Failed after {retries} retries")


# ---------------------------------------------------------------------------

def main():
    if not GENAI_API_KEY:
        raise RuntimeError("GENAI_API_KEY not set in backend/.env")

    print(f"Loading cache: {CACHE_PATH}")
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        movies = json.load(f)
    print(f"Total movies in cache: {len(movies)}")

    needs = [
        m for m in movies
        if not m.get("director") or not m.get("genres") or not m.get("overview")
    ]
    print(f"Movies needing enrichment: {len(needs)}")
    if not needs:
        print("All movies already enriched! Nothing to do.")
        return

    print(f"Using model: {GEMINI_MODEL}\n")

    enriched = 0
    failed   = 0

    for i, movie in enumerate(needs):
        title = movie.get("title") or movie.get("name") or "Unknown"
        year  = str(movie.get("release_date", ""))[:4]

        print(f"[{i+1}/{len(needs)}] {title} ({year}) … ", end="", flush=True)

        try:
            info = get_movie_info(title, year)
        except Exception as exc:
            print(f"ERROR: {exc}")
            failed += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        if not info:
            print("no JSON returned — skipping")
            failed += 1
            time.sleep(SLEEP_BETWEEN)
            continue

        movie["director"] = info.get("director") or "Unknown"
        movie["genres"]   = info.get("genres")   or []
        movie["overview"] = info.get("overview")  or "No synopsis available."

        print(f"OK  [{movie['director']} | {', '.join(movie['genres'][:2])}]")
        enriched += 1

        if enriched % CHECKPOINT_EVERY == 0:
            print(f"  ↳ Checkpoint: saving {enriched} enriched so far…")
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(movies, f, indent=2, ensure_ascii=False)

        time.sleep(SLEEP_BETWEEN)

    print(f"\nSaving final cache → {CACHE_PATH}")
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done!  Enriched: {enriched}  |  Failed/skipped: {failed}")
    print("Restart Flask and refresh the page — data will now appear instantly.")


if __name__ == "__main__":
    main()
