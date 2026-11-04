import json
import urllib.request

from config import SERVER, REPS, TIMEOUT


def health():
    url = SERVER.rstrip("/") + "/health"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def measure(code, reps=REPS):
    url = SERVER.rstrip("/") + "/measure"
    body = json.dumps({"code": code, "reps": reps}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"ok": False, "error": str(e)}
