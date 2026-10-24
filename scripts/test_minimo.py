"""Test mínimo de conectividad con la API."""

import requests

try:
    r = requests.get("http://localhost:8502/health", timeout=10)
    print(f"Status code: {r.status_code}")
    print(f"Headers: {dict(r.headers)}")
    print(f"Texto crudo: {r.text[:200]!r}")
    print(f"JSON: {r.json()}")
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")