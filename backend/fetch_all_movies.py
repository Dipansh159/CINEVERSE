import os
import requests
from tmdb_app import db, Movie, app
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies(endpoint, pages=5):
    movies = []
    for page in range(1, pages + 1):
        url = f"{BASE_URL}{endpoint}"
        params = { "api_key": API_KEY, "language": "en-US", "page": page }
        r = requests.get(url, params=params)

        if r.status_code != 200:
            continue

        data = r.json().get("results", [])
        movies.extend(data)

    return movies


def save_to_db(movies):
    print(f"Saving {len(movies)} movies...")

    with app.app_context():
        for m in movies:
            tmdb_id = m.get("id")
            if Movie.query.filter_by(tmdb_id=tmdb_id).first():
                continue

            movie = Movie(
                tmdb_id=tmdb_id,
                title=m.get("title"),
                overview=m.get("overview"),
                release_date=m.get("release_date"),
                poster_url=f"https://image.tmdb.org/t/p/w500{m.get('poster_path')}" if m.get("poster_path") else None,
                backdrop_url=f"https://image.tmdb.org/t/p/w780{m.get('backdrop_path')}" if m.get("backdrop_path") else None
            )
            db.session.add(movie)

        db.session.commit()
        print("Done!")


if __name__ == "__main__":
    popular = fetch_movies("/movie/popular", pages=10)
    trending = fetch_movies("/trending/movie/week", pages=10)
    top_rated = fetch_movies("/movie/top_rated", pages=10)
    upcoming = fetch_movies("/movie/upcoming", pages=5)

    all_movies = popular + trending + top_rated + upcoming
    save_to_db(all_movies)
