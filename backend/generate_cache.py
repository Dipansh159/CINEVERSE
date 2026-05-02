import os
import time
import json
from collections import OrderedDict

# Import existing helpers from your backend (tmdb_get handles retries)
try:
    from tmdb_app import tmdb_get
except ImportError:
    from backend.tmdb_app import tmdb_get

# CONFIG
TARGET_COUNT = 20000         # target number of unique movies to collect
CHECKPOINT_EVERY = 500       # write an incremental checkpoint every N new movies
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
OUTPUT_PATH = os.path.join(PROJECT_ROOT, "Home_Page", "movies_cache.json")
TMP_CHECKPOINT = os.path.join(PROJECT_ROOT, "Home_Page", "movies_cache_checkpoint.json")
SLEEP_BETWEEN_REQUESTS = 0.25  # seconds (tweak if you receive 429s)

# Helper: normalize movie dict to a compact object we store
def normalize(m):
    poster_base = "https://image.tmdb.org/t/p/w500"
    backdrop_base = "https://image.tmdb.org/t/p/w780"
    return {
        "tmdb_id": m.get("id") or m.get("tmdb_id"),
        "title": m.get("title"),
        "release_date": m.get("release_date"),
        "poster_url": (poster_base + m["poster_path"]) if m.get("poster_path") else m.get("poster_url"),
        "backdrop_url": (backdrop_base + m["backdrop_path"]) if m.get("backdrop_path") else m.get("backdrop_url"),
    }

# Load existing checkpoint if present (resume capability)
movies_map = OrderedDict()
if os.path.exists(TMP_CHECKPOINT):
    print("Found checkpoint file — loading...")
    with open(TMP_CHECKPOINT, "r", encoding="utf-8") as f:
        arr = json.load(f)
        for it in arr:
            movies_map[it["tmdb_id"]] = it
    print(f"Resumed from checkpoint: {len(movies_map)} movies already loaded.")

# Small helper to save checkpoint / final
def save_checkpoint(path):
    arr = list(movies_map.values())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(arr, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(arr)} movies -> {path}")

# Function to add list of movies (dicts from TMDB) into map
def add_movies_from_results(results):
    added = 0
    for m in results:
        tid = m.get("id")
        if not tid:
            continue
        if tid in movies_map:
            continue
        norm = normalize(m)
        movies_map[tid] = norm
        added += 1
    return added

# Strategy:
# 1) Crawl discover/movie pages sequentially (range of pages). Discover tends to have the broadest set.
# 2) Crawl top_rated, now_playing, upcoming
# 3) Crawl discover by year ranges to capture older movies and smaller titles
# 4) Stop when TARGET_COUNT reached (or when pages exhausted)
# The script pauses slightly between requests; adjust SLEEP_BETWEEN_REQUESTS if you hit API limits.

def crawl_discover_pages(start_page=1, end_page=500, sort_by="popularity.desc"):
    total_added = 0
    for page in range(start_page, end_page + 1):
        if len(movies_map) >= TARGET_COUNT:
            break
        print(f"Discover: page {page}/{end_page} (collected {len(movies_map)})")
        params = {
            "sort_by": sort_by,
            "page": page,
            "include_adult": False,
            "language": "en-US"
        }
        data = tmdb_get("/discover/movie", params=params)
        results = data.get("results", [])
        added = add_movies_from_results(results)
        total_added += added
        if added:
            print(f"  +{added} new movies (total {len(movies_map)})")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        # checkpoint
        if len(movies_map) % CHECKPOINT_EVERY < added:
            save_checkpoint(TMP_CHECKPOINT)
    return total_added

def crawl_endpoint_with_pages(endpoint, max_pages=50, extra_params=None):
    total_added = 0
    for page in range(1, max_pages + 1):
        if len(movies_map) >= TARGET_COUNT:
            break
        print(f"{endpoint}: page {page}/{max_pages} (collected {len(movies_map)})")
        params = {"page": page, "language": "en-US"}
        if extra_params:
            params.update(extra_params)
        data = tmdb_get(endpoint, params=params)
        results = data.get("results", [])
        added = add_movies_from_results(results)
        total_added += added
        if added:
            print(f"  +{added} new movies (total {len(movies_map)})")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if len(movies_map) % CHECKPOINT_EVERY < added:
            save_checkpoint(TMP_CHECKPOINT)
    return total_added

def crawl_by_year_ranges(start_year=1900, end_year=None, step=5):
    if end_year is None:
        from datetime import datetime
        end_year = datetime.now().year
    total_added = 0
    for y in range(end_year, start_year-1, -step):
        if len(movies_map) >= TARGET_COUNT:
            break
        start = max(start_year, y - step + 1)
        end = y
        print(f"Discover by year range: {start}-{end} (collected {len(movies_map)})")
        page = 1
        while True:
            if len(movies_map) >= TARGET_COUNT:
                break
            params = {
                "sort_by": "popularity.desc",
                "page": page,
                "include_adult": False,
                "language": "en-US",
                "primary_release_date.gte": f"{start}-01-01",
                "primary_release_date.lte": f"{end}-12-31"
            }
            data = tmdb_get("/discover/movie", params=params)
            results = data.get("results", [])
            if not results:
                break
            added = add_movies_from_results(results)
            if added:
                print(f"  page {page} +{added} new (total {len(movies_map)})")
            page += 1
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            # checkpoint
            if len(movies_map) % CHECKPOINT_EVERY < added:
                save_checkpoint(TMP_CHECKPOINT)
    return total_added

# Main crawl routine
def main():
    print("Starting large cache build (target:", TARGET_COUNT, "movies)")

    # 1) Discover popular pages (broad sweep)
    crawl_discover_pages(start_page=1, end_page=500, sort_by="popularity.desc")
    print("After discover (popularity):", len(movies_map))

    if len(movies_map) < TARGET_COUNT:
        # 2) Top rated
        crawl_endpoint_with_pages("/movie/top_rated", max_pages=250)
        print("After top_rated:", len(movies_map))

    if len(movies_map) < TARGET_COUNT:
        # 3) Now playing + upcoming
        crawl_endpoint_with_pages("/movie/now_playing", max_pages=50)
        crawl_endpoint_with_pages("/movie/upcoming", max_pages=100)
        print("After now_playing/upcoming:", len(movies_map))

    if len(movies_map) < TARGET_COUNT:
        # 4) Discover by year windows to capture older/less-popular titles
        crawl_by_year_ranges(start_year=1900, end_year=None, step=5)
        print("After discover by year ranges:", len(movies_map))

    print("Crawl finished main passes. Collected:", len(movies_map))

    # Final dedupe (already deduped by id) and save final file
    save_checkpoint(TMP_CHECKPOINT)  # save checkpoint
    save_checkpoint(OUTPUT_PATH)     # final save to movies_cache.json
    print("Done. Final cache saved to:", OUTPUT_PATH)

if __name__ == "__main__":
    main()
