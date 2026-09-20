import traceback
try:
    from fastapi.testclient import TestClient
    import backend
    c = TestClient(backend.app)
    r = c.get("/")
    print("status:", r.status_code)
    body = r.text
    print("body[:400]:", repr(body[:400]))
    print("has bootstrap:", "__LEGAL_VISION_BACKEND__" in body, "| has theme head script:", "lv-theme" in body)
except Exception:
    traceback.print_exc()
