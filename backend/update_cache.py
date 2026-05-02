import json
import requests
import time

TMDB_API_KEY = "YOUR_TMDB_API_KEY"

# load existing cache
with open("../Home_Page/movies_cache.json", "r", encoding="utf-8") as f:
    movies = json.load(f)
    movies = movies[:300]

updated_movies = []

for i, movie in enumerate(movies):
    tmdb_id = movie.get("tmdb_id")

    try:
        url = f"https://api.themoviedb.org/3/movie/{tmdb_id}?api_key=d4ded1dcd06236100cb440817a7363ae&append_to_response=credits"

        res = requests.get(url, timeout=10)

        if res.status_code != 200:
            print("Failed:", tmdb_id)
            updated_movies.append(movie)
            continue

        data = res.json()
        time.sleep(0.5)
        
    except Exception as e:
        print("Skipped:", tmdb_id)
        updated_movies.append(movie)
        continue

        # extract director
        director = "Unknown"
        for crew in data.get("credits", {}).get("crew", []):
            if crew.get("job") == "Director":
                director = crew.get("name")
                break

        # extract genres
        genres = [g.get("name") for g in data.get("genres", [])]

        # update movie
        movie["overview"] = data.get("overview", "")
        movie["genres"] = genres
        movie["director"] = director

        updated_movies.append(movie)

        print(f"Updated {i+1}/{len(movies)}: {movie.get('title', 'Unknown')}")

        time.sleep(0.2)  # avoid rate limit

    except Exception as e:
        print("Skipped (network issue):", tmdb_id, e)
        updated_movies.append(movie)
        continue

# save updated file
with open("../Home_Page/movies_cache.json", "w", encoding="utf-8") as f:
    json.dump(updated_movies, f, indent=2, ensure_ascii=False)

print("DONE ✅ All movies updated")