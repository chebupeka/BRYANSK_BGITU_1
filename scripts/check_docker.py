"""Check the Compose stack through nginx without calling a real model provider."""

import argparse
import json
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

BASE_URL = "http://127.0.0.1:8080"


def request(base_url, path, payload=None, expected_status=200):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if data is not None else {}
    try:
        response = urlopen(Request(base_url + path, data=data, headers=headers), timeout=180)
    except HTTPError as error:
        response = error
    with response:
        assert response.status == expected_status, (
            f"{path}: expected HTTP {expected_status}, received {response.status}"
        )
        return response.read(), response.headers


def check_error(content, headers):
    body = json.loads(content)
    error = body["error"]
    assert isinstance(error["code"], str) and error["code"], "Error code is missing"
    assert error["message"] == body["detail"], "Error message is inconsistent"
    assert isinstance(error["retryable"], bool), "Retry flag is missing"
    assert isinstance(error["details"], list), "Error details are missing"
    assert error["request_id"] == headers["X-Request-ID"], "Request ID is inconsistent"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=BASE_URL, help="Frontend/nginx base URL")
    parser.add_argument("--expected-mode", choices=("stub", "unavailable"), default="stub")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")

    html, _ = request(base_url, "/")
    assert '<div id="root">' in html.decode("utf-8"), "Frontend HTML is missing"
    health, _ = request(base_url, "/api/health")
    health = json.loads(health)
    assert health["status"] == "ok", "API is unhealthy"
    if health["processor_mode"] != args.expected_mode:
        raise SystemExit(
            f"Smoke check requires {args.expected_mode} mode; no real model calls will be made"
        )
    catalog, _ = request(base_url, "/api/catalog")
    catalog = json.loads(catalog)
    assert len(catalog["doc_types"]) >= 4, "Document types did not load"
    assert catalog["processor_mode"] == args.expected_mode, "Processor mode is inconsistent"

    draft = "Поставка двух мониторов до 25.09.2026 только после согласования бюджета."
    payload = {
        "draft": draft, "doc_type": "service_memo", "requisites": {},
    }
    if args.expected_mode == "unavailable":
        check_error(*request(base_url, "/api/ready", expected_status=503))
        check_error(*request(base_url, "/api/process", payload, expected_status=503))
        print("Docker smoke check passed: frontend, liveness, readiness and processing refusal.")
        return

    ready, _ = request(base_url, "/api/ready")
    assert json.loads(ready)["status"] == "ready", "API is not ready"
    result, _ = request(base_url, "/api/process", payload)
    prepared = json.loads(result)
    assert prepared["document"]["body"] == [draft], "Stub changed source text"
    assert prepared["missing_fields"], "Missing fields were not reported"
    repeated, _ = request(base_url, "/api/process", payload)
    assert json.loads(repeated)["document"] == prepared["document"], (
        "Repeated processing changed document content"
    )

    check_error(*request(base_url, "/api/process", {**payload, "draft": " "}, expected_status=422))
    check_error(*request(base_url, "/api/nonexistent", expected_status=404))

    for template_id in ("classic", "modern"):
        content, headers = request(base_url, "/api/documents/download", {
            "document": prepared["document"], "template_id": template_id,
        })
        assert "wordprocessingml.document" in headers["Content-Type"], "Wrong file type"
        with ZipFile(BytesIO(content)) as document:
            xml = document.read("word/document.xml").decode("utf-8")
        assert draft in xml, "DOCX lost source text"
        assert "[Заполнить:" in xml, "DOCX lost missing-field markers"
    print(
        "Docker smoke check passed: frontend, readiness, API errors, "
        "processing, both DOCX templates."
    )


if __name__ == "__main__":
    main()
