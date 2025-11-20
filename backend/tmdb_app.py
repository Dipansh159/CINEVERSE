# backend/tmdb_app.py
import os
import datetime
import random
import requests
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_cors import CORS
from requests.adapters import HTTPAdapter, Retry

load_dotenv()

# TMDB Keys
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
if not TMDB_API_KEY:
    raise RuntimeError("TMDB_API_KEY not set in .env")

TMDB_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE = "https://image.tmdb.org/t/p/w780"

# Flask App
app = Flask(__name__)
CORS(app)

db_path = os.path.join(os.path.dirname(__file__), "movies.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------- MOVIE MODEL (Minimal) ----------------
class Movie(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tmdb_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    release_date = db.Column(db.String)
    poster_url = db.Column(db.String)
    backdrop_url = db.Column(db.String)

    def to_dict(self):
        return {
            "tmdb_id": self.tmdb_id,
            "title": self.title,
            "release_date": self.release_date,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url
        }

# TMDB helper
def tmdb_get(path, params=None):
    if params is None:
        params = {}
    params["api_key"] = TMDB_API_KEY

    try:
        session = requests.Session()
        retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retries))

        response = session.get(f"{TMDB_BASE}{path}", params=params, timeout=20)
        response.raise_for_status()
        return response.json()

    except Exception as e:
        print("TMDB ERROR:", e)
        return {}

# ---------------- Fetch & Cache SINGLE Movie ----------------
def fetch_and_cache_movie(tmdb_id):
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()
    if movie:
        return movie

    details = tmdb_get(f"/movie/{tmdb_id}", params={"language": "en-US"})
    if not details:
        return None

    movie = Movie(
        tmdb_id=tmdb_id,
        title=details.get("title"),
        release_date=details.get("release_date"),
        poster_url=(POSTER_BASE + details.get("poster_path")) if details.get("poster_path") else None,
        backdrop_url=(BACKDROP_BASE + details.get("backdrop_path")) if details.get("backdrop_path") else None,
    )

    db.session.add(movie)
    db.session.commit()
    return movie

# ---------------- CREATE DB ----------------
@app.before_request
def create_db_once():
    if not hasattr(app, 'db_initialized'):
        db.create_all()
        app.db_initialized = True

# ---------------- LOAD POPULAR MOVIES INTO DB ----------------
@app.route("/api/load_movies")
def load_movies():
    """Fetch MANY movies from TMDB and store in DB (like Letterboxd)."""
    added = 0

    for page in range(1, 6):  # 5 pages × 20 = 100 movies
        data = tmdb_get("/discover/movie", params={
            "sort_by": "popularity.desc",
            "page": page,
            "include_adult": False,
            "language": "en-US"
        })

        for m in data.get("results", []):
            tmdb_id = m["id"]

            if Movie.query.filter_by(tmdb_id=tmdb_id).first():
                continue

            movie = Movie(
                tmdb_id=tmdb_id,
                title=m.get("title"),
                release_date=m.get("release_date"),
                poster_url=POSTER_BASE + m["poster_path"] if m.get("poster_path") else None,
                backdrop_url=BACKDROP_BASE + m["backdrop_path"] if m.get("backdrop_path") else None,
            )

            db.session.add(movie)
            added += 1

    db.session.commit()
    return jsonify({"status": "success", "added": added})

# ---------------- POPULAR MOVIES (Homepage) ----------------
@app.route("/api/popular")
def popular():
    """Return movies like Letterboxd (NO cast/crew), shuffled every refresh."""

    import random

    movies = Movie.query.all()

    # DB EMPTY → try TMDB fetch
    if not movies:
        try:
            page = random.randint(1, 40)
            data = tmdb_get("/discover/movie", params={
                "sort_by": "popularity.desc",
                "page": page,
                "include_adult": False,
                "language": "en-US"
            })

            fresh = []
            for m in data.get("results", []):
                fresh.append({
                    "tmdb_id": m["id"],
                    "title": m.get("title"),
                    "release_date": m.get("release_date"),
                    "poster_url": POSTER_BASE + m["poster_path"] if m.get("poster_path") else None,
                    "backdrop_url": BACKDROP_BASE + m["backdrop_path"] if m.get("backdrop_path") else None,
                })

            # If TMDB returns something → send it
            if fresh:
                return jsonify({"results": fresh})

            # If TMDB returns nothing → failover
            print("TMDB empty result — using fallback movies")

        except Exception as e:
            print("TMDB POPULAR ERROR:", e)

        # ---- FALLBACK so frontend never breaks ----
        return jsonify({"results": []})

    # DB not empty → shuffle movies like Letterboxd
    shuffled = [m.to_dict() for m in movies]
    random.shuffle(shuffled)

    return jsonify({"results": shuffled})


# ---------------- SEARCH API ----------------
@app.route("/api/search")
def search_movies():
    q = request.args.get("q", "")
    page = int(request.args.get("page", 1))

    if not q:
        return jsonify({"results": []})

    data = tmdb_get("/search/movie", params={
        "query": q,
        "page": page,
        "include_adult": False,
        "language": "en-US"
    })

    today = datetime.date.today().isoformat()
    results = []

    for item in data.get("results", []):
        rd = item.get("release_date") or ""
        if rd == "" or rd > today:
            continue

        results.append({
            "tmdb_id": item["id"],
            "title": item.get("title"),
            "release_date": rd,
            "poster_url": POSTER_BASE + item["poster_path"] if item.get("poster_path") else None,
            "backdrop_url": BACKDROP_BASE + item["backdrop_path"] if item.get("backdrop_path") else None,
        })

    return jsonify({
        "results": results,
        "page": data.get("page", 1),
        "total_pages": data.get("total_pages", 1)
    })

# ---------------- MOVIE DETAILS ----------------
@app.route("/api/movie/<int:tmdb_id>")
def movie_detail(tmdb_id):
    movie = Movie.query.filter_by(tmdb_id=tmdb_id).first()

    if movie is None:
        movie = fetch_and_cache_movie(tmdb_id)

    if movie is None:
        return jsonify({"error": "movie not found"}), 404

    return jsonify(movie.to_dict())

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
