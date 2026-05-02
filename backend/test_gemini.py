"""List available Gemini models for this API key."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
GENAI_API_KEY = os.getenv("GENAI_API_KEY", "")

print(f"API key ends with: ...{GENAI_API_KEY[-8:]}\n")

# --- Try REST API directly (v1) ---
import requests
print("=== Testing REST API (v1) ===")
try:
    r = requests.get(
        f"https://generativelanguage.googleapis.com/v1/models?key={GENAI_API_KEY}",
        timeout=10
    )
    if r.ok:
        for m in r.json().get("models", []):
            methods = m.get("supportedGenerationMethods", [])
            if "generateContent" in methods:
                print(f"  USABLE: {m['name']}")
    else:
        print(f"  REST v1 error: {r.status_code} {r.text[:200]}")
except Exception as e:
    print(f"  REST v1 exception: {e}")

print("\n=== Quick test: gemini-1.5-flash via REST v1beta ===")
try:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GENAI_API_KEY}",
        json={"contents": [{"parts": [{"text": "Say hi"}]}]},
        timeout=15
    )
    print(f"  Status: {r.status_code}  Response: {r.text[:300]}")
except Exception as e:
    print(f"  Exception: {e}")

print("\n=== Quick test: gemini-1.5-flash via REST v1 ===")
try:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GENAI_API_KEY}",
        json={"contents": [{"parts": [{"text": "Say hi"}]}]},
        timeout=15
    )
    print(f"  Status: {r.status_code}  Response: {r.text[:300]}")
except Exception as e:
    print(f"  Exception: {e}")

print("\n=== Quick test: gemini-2.0-flash-lite via REST v1beta ===")
try:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite:generateContent?key={GENAI_API_KEY}",
        json={"contents": [{"parts": [{"text": "Say hi"}]}]},
        timeout=15
    )
    print(f"  Status: {r.status_code}  Response: {r.text[:300]}")
except Exception as e:
    print(f"  Exception: {e}")
