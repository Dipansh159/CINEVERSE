import os
import re
import json
import concurrent.futures
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from requests.adapters import HTTPAdapter, Retry
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
GENAI_API_KEY = os.getenv("GENAI_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")

# Gemini via direct REST API (SDK routing is broken for available models)
# Available models confirmed via ListModels: gemini-2.0-flash-lite, gemini-2.5-flash
GEMINI_MODEL = "gemini-2.5-flash-lite"  # confirmed available via ListModels
GEMINI_REST_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GENAI_API_KEY}"
)
_gemini_available = bool(GENAI_API_KEY)
if _gemini_available:
    print(f"Gemini REST ready ({GEMINI_MODEL}).")
else:
    print("GENAI_API_KEY not set — will use Ollama fallback.")

TMDB_BASE = "https://api.themoviedb.org/3"
POSTER_BASE = "https://image.tmdb.org/t/p/w500"
BACKDROP_BASE = "https://image.tmdb.org/t/p/w780"

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

_session = requests.Session()
_retries = Retry(total=3, backoff_factor=0.6, status_forcelist=[429, 500, 502, 503, 504])
_session.mount("https://", HTTPAdapter(max_retries=_retries))

EMOTION_MODEL_AVAILABLE = None
emotion_model = None


def tmdb_get(path, params=None):
    """Make a TMDB API call using the shared global session."""
    if not TMDB_API_KEY:
        print(f"TMDB error [{path}]: TMDB_API_KEY is not configured.")
        return {}

    params = {**(params or {}), "api_key": TMDB_API_KEY}
    try:
        response = _session.get(TMDB_BASE + path, params=params, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"TMDB error [{path}]: {exc}")
        return {}


def quick_movie(movie):
    """Return a compact movie payload from list endpoints without extra TMDB calls."""
    if not movie or not movie.get("id"):
        return None

    return {
        "tmdb_id": movie["id"],
        "title": movie.get("title"),
        "release_date": movie.get("release_date"),
        "rating": round(movie.get("vote_average") or 0, 1),
        "overview": movie.get("overview"),
        "poster_url": POSTER_BASE + movie["poster_path"] if movie.get("poster_path") else None,
        "backdrop_url": BACKDROP_BASE + movie["backdrop_path"] if movie.get("backdrop_path") else None,
    }


def clean_movie(movie):
    """Return the full movie payload used by the detail page."""
    if not movie or not movie.get("id"):
        return None

    details = tmdb_get(f"/movie/{movie['id']}", {"append_to_response": "credits", "language": "en-US"})
    if not details:
        return None

    director = next(
        (crew["name"] for crew in details.get("credits", {}).get("crew", []) if crew.get("job") == "Director"),
        "Unknown",
    )

    return {
        "tmdb_id": movie["id"],
        "title": details.get("title"),
        "release_date": details.get("release_date"),
        "rating": round(details.get("vote_average") or 0, 1),
        "overview": details.get("overview"),
        "director": director,
        "genres": [genre["name"] for genre in details.get("genres", [])],
        "poster_url": POSTER_BASE + details["poster_path"] if details.get("poster_path") else None,
        "backdrop_url": BACKDROP_BASE + details["backdrop_path"] if details.get("backdrop_path") else None,
    }


def fetch_list(path, extra=None, max_items=20):
    """Fetch a movie list without triggering extra per-movie detail requests."""
    movies = []
    page = 1

    while len(movies) < max_items and page <= 5:
        data = tmdb_get(path, {"language": "en-US", "page": page, **(extra or {})})
        results = data.get("results", [])
        if not results:
            break

        for movie in results:
            cleaned = quick_movie(movie)
            if cleaned:
                movies.append(cleaned)
            if len(movies) >= max_items:
                break

        page += 1

    return movies


CINEBOT_SYSTEM = """You are CineBot, an elite AI film expert built into the CineVerse platform. You are deeply knowledgeable about cinema but you are STRICTLY FACTUAL.

YOUR EXPERTISE:
- Deep, accurate knowledge of movies, directors, actors, cinematographers, writers, and production history.
- Precise plot analysis, character arcs, symbolism, and thematic breakdowns based on what actually happens in the film.
- Logical, well-reasoned "what-if" scenarios grounded entirely in the film's actual established canon and real character motivations.
- Accurate movie trivia, box office facts, awards history, and behind-the-scenes production details.

STRICT ACCURACY RULES — THIS IS CRITICAL:
- You MUST NEVER invent, guess, or hallucinate facts. If you are not 100% certain about a director's name, character's name, plot point, or any other detail, say "I'm not certain about that specific detail" rather than making something up.
- NEVER mix up characters, plot points, or facts from different films. Each film is distinct.
- ALWAYS use the correct IN-UNIVERSE CHARACTER NAMES when discussing a film's plot. For example: say 'Andrew Neiman' (not 'Miles Teller'), say 'Miles Morales' (not 'Shameik Moore'), say 'Tony Stark' (not 'Robert Downey Jr.'). Only mention actor names when the user specifically asks who played a role.
- NEVER mix a character from one film into the plot of another film.
- If movie context (title, director, genres, synopsis) is provided AND looks trustworthy, use it as the factual baseline. If the synopsis seems wrong or generic, rely on your own training knowledge instead.
- Label speculation clearly: use phrases like 'Speculatively:' to distinguish analysis from confirmed canon.
- If the user asks about anything outside of cinema, politely decline and steer the conversation back to films.

FOR "WHAT-IF" QUESTIONS:
- Start from CONFIRMED canon facts about the specific film.
- Reason logically through consequences based on actual character personalities and real story events.
- Be creative but stay grounded in the actual film's world.

STYLE:
- Enthusiastic, intelligent, and concise.
- Use bullet points for lists. Short paragraphs for analysis.
- Prefer accuracy over length.
"""


def normalize_history(history):
    """Accept frontend history in either {content: ...} or legacy {text: ...} format."""
    normalized = []
    if not isinstance(history, list):
        return normalized

    for turn in history[-8:]:
        if not isinstance(turn, dict):
            continue

        role = (turn.get("role") or "").strip()
        content = turn.get("content")
        if content is None:
            content = turn.get("text")

        if role not in ("user", "assistant"):
            continue
        if content is None:
            continue

        content = str(content).strip()
        if not content:
            continue

        normalized.append({"role": role, "content": content})

    return normalized


def build_movie_context(movie_context):
    """Build the movie context block injected into each chatbot call.
    Only passes verified metadata (title, year, director, genres).
    NEVER passes the synopsis — Gemini's own training knowledge is always
    more reliable than a Gemini-generated synopsis (which can hallucinate)."""
    if not isinstance(movie_context, dict) or not movie_context.get("title"):
        return None

    PLACEHOLDERS = {
        "fetching...", "fetching synopsis...", "loading...",
        "no synopsis available.", "synopsis unavailable.",
        "unknown", "n/a", ""
    }

    title = movie_context.get("title", "").strip()
    if not title:
        return None

    lines = [f"The user is currently viewing the film: {title}"]

    release_date = movie_context.get("release_date") or movie_context.get("year", "")
    year = str(release_date)[:4] if release_date else ""
    if year:
        lines[0] += f" ({year})"

    director = (movie_context.get("director") or "").strip()
    if director and director.lower() not in PLACEHOLDERS:
        lines.append(f"Director: {director}")

    genres = movie_context.get("genres")
    if isinstance(genres, list) and genres:
        lines.append(f"Genres: {', '.join(str(g) for g in genres if g)}")
    elif isinstance(genres, str) and genres.strip().lower() not in PLACEHOLDERS:
        lines.append(f"Genres: {genres.strip()}")

    lines.append(
        "Use your OWN verified training knowledge about this film for all plot details, "
        "character names, and story events. Do not invent anything."
    )

    return lines


def clean_ollama_output(text):
    if not text:
        return ""

    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return cleaned.strip()


def is_what_if_question(question):
    text = (question or "").strip().lower()
    return (
        "what if" in text
        or "what would've happened" in text
        or "what would have happened" in text
        or "what happens if" in text
        or "what would happen if" in text
    )


def build_user_prompt(question, movie_context=None):
    context_lines = build_movie_context(movie_context) or []
    prompt_parts = []

    if context_lines:
        prompt_parts.extend(context_lines)

    if is_what_if_question(question):
        prompt_parts.extend([
            "[Answer Mode]",
            "- Treat this as an in-universe, in-story, or in-history scenario by default.",
            "- Do not explain how the movie script, narrative, or filmmaking would change unless the user explicitly asks that.",
            "- Focus on the most logical chain of consequences inside the world of the story or event.",
            "- Keep the answer direct, interesting, and concise.",
        ])

    prompt_parts.append(f"[User Question]\n{question}")
    return "\n".join(prompt_parts)


def _gemini_rest(prompt, temperature=0.2, max_tokens=300):
    """Call Gemini via direct REST API. Returns response text or raises."""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
    }
    resp = _session.post(GEMINI_REST_URL, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def ask_gemini(question, movie_context=None, history=None):
    """Call Gemini 2.0 Flash Lite via REST API."""
    if not _gemini_available:
        raise RuntimeError("Gemini not available")

    parts = [CINEBOT_SYSTEM, "\n\n"]
    ctx_lines = build_movie_context(movie_context)
    if ctx_lines:
        parts.append("\n".join(ctx_lines) + "\n\n")
    for turn in normalize_history(history):
        role_label = "User" if turn["role"] == "user" else "CineBot"
        parts.append(f"{role_label}: {turn['content']}\n")
    parts.append(f"User: {question}\nCineBot:")
    full_prompt = "".join(parts)

    return _gemini_rest(full_prompt, temperature=0.2, max_tokens=300)


def ask_ollama(question, movie_context=None, history=None):
    """Call local Ollama model (fallback when Gemini is unavailable)."""
    messages = normalize_history(history)
    messages.append({"role": "user", "content": build_user_prompt(question, movie_context=movie_context)})

    try:
        response = _session.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": OLLAMA_MODEL,
                "think": False,
                "stream": False,
                "messages": [{"role": "system", "content": CINEBOT_SYSTEM}, *messages],
                "options": {
                    "temperature": 0.1,
                    "num_predict": 512,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message", {})
        content = clean_ollama_output(message.get("content") or "")
        if not content:
            return "Sorry, I could not generate a response."
        return content
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(
            f"Ollama is not running. Start Ollama first, then run `ollama pull {OLLAMA_MODEL}` and try again."
        ) from exc
    except requests.exceptions.HTTPError as exc:
        details = ""
        try:
            details = response.json().get("error", "")
        except Exception:
            details = response.text[:200]

        if response.status_code == 404:
            raise RuntimeError(
                f"Ollama model `{OLLAMA_MODEL}` is not installed. Run `ollama pull {OLLAMA_MODEL}` first."
            ) from exc
        raise RuntimeError(f"Ollama request failed: {details or response.status_code}") from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("The local Ollama model took too long to respond.") from exc
    except Exception as exc:
        print(f"Ollama API error: {exc}")
        return "Sorry, I could not process that right now. Please try again."


def ask_cinebot(question, movie_context=None, history=None):
    """Try Gemini first with a hard timeout. Fast-fail on error — no Ollama wait."""
    if _gemini_available:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(ask_gemini, question, movie_context, history)
                return fut.result(timeout=20)
        except concurrent.futures.TimeoutError:
            print("Gemini timed out (>20s).")
            return "I'm taking a bit too long right now — please try sending your message again."
        except Exception as exc:
            print(f"Gemini error: {exc}")
            return "I ran into a connection issue. Please try again — it usually resolves quickly."
    # Ollama: only used when Gemini API key is not set at all
    try:
        return ask_ollama(question, movie_context=movie_context, history=history)
    except RuntimeError as exc:
        return f"❌ {exc}"


def load_emotion_model():
    global EMOTION_MODEL_AVAILABLE, emotion_model

    if EMOTION_MODEL_AVAILABLE is not None:
        return EMOTION_MODEL_AVAILABLE

    print("Loading Emotion AI model...")
    try:
        from transformers import pipeline as hf_pipeline

        emotion_model = hf_pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            return_all_scores=True,
        )
        EMOTION_MODEL_AVAILABLE = True
        print("Emotion model loaded successfully.")
    except Exception as exc:
        EMOTION_MODEL_AVAILABLE = False
        print(f"Emotion model could not load (server will still run): {exc}")

    return EMOTION_MODEL_AVAILABLE


@app.route("/")
def root():
    return jsonify({
        "message": "CineVerse backend running",
        "status": "ok",
        "chat_provider": "ollama",
        "chat_model": OLLAMA_MODEL,
    })


@app.route("/api/home_top")
def home_top():
    return jsonify({"results": fetch_list("/discover/movie", {
        "sort_by": "vote_average.desc",
        "vote_count.gte": 2000,
        "include_adult": False,
    })})


@app.route("/api/section/trending")
def section_trending():
    return jsonify({"results": fetch_list("/trending/movie/week")})


@app.route("/api/section/top_rated")
def section_top_rated():
    return jsonify({"results": fetch_list("/discover/movie", {
        "sort_by": "vote_average.desc",
        "vote_count.gte": 3000,
        "include_adult": False,
    })})


@app.route("/api/section/popular")
def section_popular():
    return jsonify({"results": fetch_list("/discover/movie", {
        "sort_by": "popularity.desc",
        "vote_count.gte": 500,
        "include_adult": False,
    })})


@app.route("/api/section/imdb_top")
def section_imdb_top():
    return jsonify({"results": fetch_list("/discover/movie", {
        "sort_by": "vote_average.desc",
        "vote_count.gte": 25000,
        "include_adult": False,
    })})


@app.route("/api/movie/<int:tmdb_id>")
def movie_details(tmdb_id):
    details = tmdb_get(
        f"/movie/{tmdb_id}",
        {"append_to_response": "credits,videos,similar", "language": "en-US"},
    )
    if not details:
        return jsonify({"error": "Movie not found"}), 404

    director = next(
        (crew["name"] for crew in details.get("credits", {}).get("crew", []) if crew.get("job") == "Director"),
        "Unknown",
    )
    cast = [
        {
            "name": cast_member["name"],
            "character": cast_member.get("character"),
            "profile_url": POSTER_BASE + cast_member["profile_path"] if cast_member.get("profile_path") else None,
        }
        for cast_member in details.get("credits", {}).get("cast", [])[:10]
    ]
    similar = [
        quick_movie(movie)
        for movie in details.get("similar", {}).get("results", [])[:6]
        if movie.get("id")
    ]
    trailer = next(
        (
            f"https://www.youtube.com/watch?v={video['key']}"
            for video in details.get("videos", {}).get("results", [])
            if video.get("type") == "Trailer" and video.get("site") == "YouTube"
        ),
        None,
    )

    return jsonify({
        "tmdb_id": tmdb_id,
        "title": details.get("title"),
        "tagline": details.get("tagline"),
        "release_date": details.get("release_date"),
        "overview": details.get("overview"),
        "director": director,
        "cast": cast,
        "genres": [genre["name"] for genre in details.get("genres", [])],
        "rating": round(details.get("vote_average") or 0, 1),
        "runtime": details.get("runtime"),
        "poster_url": POSTER_BASE + details["poster_path"] if details.get("poster_path") else None,
        "backdrop_url": BACKDROP_BASE + details["backdrop_path"] if details.get("backdrop_path") else None,
        "trailer_url": trailer,
        "similar": [item for item in similar if item],
    })


@app.route("/api/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Missing search query 'q'"}), 400

    data = tmdb_get("/search/movie", {
        "query": query,
        "language": "en-US",
        "include_adult": False,
    })
    results = [quick_movie(movie) for movie in data.get("results", [])[:20]]
    return jsonify({"results": [item for item in results if item]})


# Genre → emotion profile weights (used as fallback when transformers unavailable)
_GENRE_EMOTIONS = {
    "Action":      {"joy": 30, "sadness": 10, "fear": 20, "anger": 30, "surprise": 25, "disgust": 10},
    "Adventure":   {"joy": 45, "sadness": 10, "fear": 20, "anger": 10, "surprise": 40, "disgust": 5},
    "Animation":   {"joy": 60, "sadness": 20, "fear": 10, "anger": 5,  "surprise": 35, "disgust": 5},
    "Comedy":      {"joy": 75, "sadness": 10, "fear": 5,  "anger": 5,  "surprise": 25, "disgust": 5},
    "Crime":       {"joy": 10, "sadness": 25, "fear": 30, "anger": 45, "surprise": 20, "disgust": 20},
    "Documentary": {"joy": 20, "sadness": 30, "fear": 15, "anger": 20, "surprise": 25, "disgust": 10},
    "Drama":       {"joy": 20, "sadness": 50, "fear": 15, "anger": 20, "surprise": 15, "disgust": 5},
    "Fantasy":     {"joy": 40, "sadness": 20, "fear": 25, "anger": 10, "surprise": 50, "disgust": 5},
    "History":     {"joy": 15, "sadness": 35, "fear": 20, "anger": 25, "surprise": 20, "disgust": 10},
    "Horror":      {"joy": 5,  "sadness": 20, "fear": 80, "anger": 15, "surprise": 40, "disgust": 40},
    "Music":       {"joy": 55, "sadness": 25, "fear": 5,  "anger": 5,  "surprise": 20, "disgust": 5},
    "Mystery":     {"joy": 15, "sadness": 20, "fear": 35, "anger": 15, "surprise": 55, "disgust": 10},
    "Romance":     {"joy": 50, "sadness": 35, "fear": 5,  "anger": 10, "surprise": 20, "disgust": 5},
    "Science Fiction": {"joy": 25, "sadness": 15, "fear": 30, "anger": 15, "surprise": 60, "disgust": 10},
    "Thriller":    {"joy": 10, "sadness": 20, "fear": 55, "anger": 30, "surprise": 45, "disgust": 15},
    "War":         {"joy": 10, "sadness": 55, "fear": 40, "anger": 40, "surprise": 20, "disgust": 25},
    "Western":     {"joy": 20, "sadness": 25, "fear": 20, "anger": 40, "surprise": 20, "disgust": 10},
}


def genre_based_emotions(genres):
    """Blend emotion weights from a list of genre strings."""
    totals = {"joy": 0, "sadness": 0, "fear": 0, "anger": 0, "surprise": 0, "disgust": 0}
    matched = 0
    for g in (genres or []):
        w = _GENRE_EMOTIONS.get(g)
        if w:
            for k in totals:
                totals[k] += w[k]
            matched += 1
    if matched:
        for k in totals:
            totals[k] = round(totals[k] / matched)
    else:
        # Flat generic profile
        totals = {"joy": 25, "sadness": 25, "fear": 25, "anger": 25, "surprise": 25, "disgust": 25}
    return totals


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
@app.route("/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json(silent=True)
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    # Try Gemini REST for deep story-based emotional analysis
    if _gemini_available:
        try:
            prompt = (
                f"Analyze the emotional profile of this film based on its story: {data['text']}\n"
                "Return ONLY a JSON object with scores (0-100) for: joy, sadness, fear, anger, surprise, disgust. "
                "The scores should reflect the specific narrative weight of these emotions in this movie."
            )
            raw = _gemini_rest(prompt, temperature=0.1, max_tokens=200)
            json_match = re.search(r'\{[\s\S]*\}', raw)
            if json_match:
                return jsonify(json.loads(json_match.group()))
        except Exception as e:
            print(f"Gemini analysis failed, falling back: {e}")

    # Fallback: derive emotion profile from genres if provided
    genres = data.get("genres", [])
    if isinstance(genres, str):
        genres = [g.strip() for g in genres.split(",")]
    return jsonify(genre_based_emotions(genres))


@app.route("/api/movie_info", methods=["POST", "OPTIONS"])
def movie_info():
    """Get accurate movie metadata (director, genres, synopsis) via Gemini when TMDB is blocked."""
    if request.method == "OPTIONS":
        return jsonify({}), 200
    if not _gemini_available:
        return jsonify({"error": "Gemini not available"}), 503

    data = request.get_json(silent=True)
    title = (data or {}).get("title", "").strip()
    year  = str((data or {}).get("year", "")).strip()
    if not title:
        return jsonify({"error": "Missing title"}), 400

    prompt = (
        f'You are a film database. Return ONLY a valid JSON object (no markdown, no explanation) '
        f'for the film "{title}" ({year}). '
        'Use your precise training knowledge. '
        'Required JSON keys:\n'
        '  "director": the real director\'s full name (string)\n'
        '  "genres": list of genres as an array of strings (e.g. ["Drama", "Music"])\n'
        '  "overview": a 2-3 sentence plot synopsis using the correct IN-UNIVERSE CHARACTER NAMES '
        '(NOT the actors\' real names). Must be accurate to the actual film. '
        'If you are not confident about any field, use null.'
    )
    try:
        raw = _gemini_rest(prompt, temperature=0.0, max_tokens=350)
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            raise ValueError(f"No JSON object found in Gemini response: {raw[:200]}")
        info = json.loads(json_match.group())
        info.setdefault("director", "Unknown")
        info.setdefault("genres", [])
        info.setdefault("overview", "No synopsis available.")
        return jsonify(info)
    except Exception as exc:
        print(f"movie_info Gemini error: {exc}")
        return jsonify({"error": str(exc)}), 500


@app.route("/api/cinebot", methods=["POST", "OPTIONS"])
@app.route("/cinebot", methods=["POST", "OPTIONS"])
def cinebot():
    if request.method == "OPTIONS":
        return jsonify({}), 200

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    question = (data.get("question") or data.get("message") or "").strip()
    movie = data.get("movie") or {}
    history = normalize_history(data.get("history") or [])

    if not question:
        return jsonify({"error": "Missing 'question' field"}), 400

    try:
        reply = ask_cinebot(question, movie_context=movie, history=history)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    return jsonify({"reply": reply})


@app.route('/mood')
def mood():
    return render_template("moodmatcher.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
