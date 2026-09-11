"""Check the built Compose stack through its public frontend, using only the stdlib."""

import json
from io import BytesIO
from urllib.request import Request, urlopen
from zipfile import ZipFile

BASE_URL = "http://127.0.0.1:8080"


def request(path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    with urlopen(Request(BASE_URL + path, data=data, headers=headers), timeout=30) as response:
        return response.read(), response.headers


def main():
    html, _ = request("/")
    assert '<div id="root">' in html.decode("utf-8"), "Frontend HTML is missing"
    health, _ = request("/api/health")
    assert json.loads(health)["status"] == "ok", "API is unhealthy"
    catalog, _ = request("/api/catalog")
    assert len(json.loads(catalog)["doc_types"]) >= 4, "Document types did not load"

    draft = "Поставка двух мониторов до 25.09.2026 только после согласования бюджета."
    result, _ = request("/api/process", {
        "draft": draft, "doc_type": "service_memo", "requisites": {},
    })
    prepared = json.loads(result)
    assert prepared["document"]["body"] == [draft], "Stub changed source text"
    assert prepared["missing_fields"], "Missing fields were not reported"

    for template_id in ("classic", "modern"):
        content, headers = request("/api/documents/download", {
            "document": prepared["document"], "template_id": template_id,
        })
        assert "wordprocessingml.document" in headers["Content-Type"], "Wrong file type"
        with ZipFile(BytesIO(content)) as document:
            xml = document.read("word/document.xml").decode("utf-8")
        assert draft in xml, "DOCX lost source text"
        assert "[Заполнить:" in xml, "DOCX lost missing-field markers"
    print("Docker smoke check passed: frontend, API, processing, both DOCX templates.")


if __name__ == "__main__":
    main()
