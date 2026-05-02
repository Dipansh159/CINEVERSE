import os, requests
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
key = os.getenv("GENAI_API_KEY","")
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={key}"
r = requests.post(url, json={"contents":[{"parts":[{"text":"Say hi"}]}]}, timeout=15)
print(f"Status: {r.status_code}")
print(r.text[:300])
