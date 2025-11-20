from flask import Flask, request, jsonify
from flask_cors import CORS
import tmdb_app

app = Flask(__name__)
CORS(app)   # allow frontend to call backend

@app.route("/search_movie", methods=["GET"])
def search_movie():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify([])

    results = tmdb_app.search_movies(query)
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)


