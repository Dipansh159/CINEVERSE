import os
from dotenv import load_dotenv
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
print('TMDB key', os.getenv('TMDB_API_KEY'))


try:
    r = requests.get('http://127.0.0.1:5000/api/movie/299534', timeout=10)
    print('status', r.status_code)
    print('body', r.text[:400])
except Exception as e:
    print('request failed:', e)

