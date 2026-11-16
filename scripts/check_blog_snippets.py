#!/usr/bin/env python3
"""Check the code blocks in the Qdrant blog post against a running Qdrant server.

Each checked block is identified by its first line, so the post needs no test
attributes. This script reads those blocks from the HTML, so it tests the same text
a reader copies.

Start a server (Docker or Podman):
  docker run -p 6333:6333 qdrant/qdrant      # or: podman run -p 6333:6333 docker.io/qdrant/qdrant

Run the checks:
  QDRANT_URL=http://localhost:6333 python scripts/check_blog_snippets.py

"""

from __future__ import annotations

import ast
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POST = ROOT / "blogs" / "qdrant-is-a-storage-engine.html"
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLLECTION = "recipes"
DIM = 384

results: list[tuple[str, str]] = []  # (status, name)


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name))
    print(f"{status:4}  {name}" + (f"  ({detail})" if detail else ""))


def request(method: str, path: str, body=None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        QDRANT_URL + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"{}")


def error_text(body: dict) -> str:
    # Qdrant reports success as "status": "ok" and failure as an object with "error".
    status = body.get("status")
    return str(status.get("error", "")) if isinstance(status, dict) else ""


# Each checked block is identified by how it starts, so the post HTML carries no test hooks.
BLOCK_STARTS = {
    "payload": '{\n  "title"',
    "collection": "PUT /collections/recipes\n",
    "indexes": "# one request per field",
    "upsert-cloud": "PUT /collections/recipes/points?wait=true",
    "query-cloud": "POST /collections/recipes/points/query",
}


def blocks(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    found = {}
    for body in re.findall(r"<pre><code>(.*?)</code></pre>", text, re.S):
        decoded = html.unescape(re.sub(r"<[^>]+>", "", body))
        for name, start in BLOCK_STARTS.items():
            if decoded.startswith(start):
                found[name] = decoded
    return found


def parse_rest(block: str) -> tuple[str, str, dict]:
    first, _, rest = block.partition("\n")
    method, path = first.split(" ", 1)
    return method, path.strip(), json.loads(rest)


def cleanup() -> None:
    request("DELETE", f"/collections/{COLLECTION}")


def main() -> int:
    print(f"Checking {POST.relative_to(ROOT)} against {QDRANT_URL}\n")
    status, _ = request("GET", "/")
    if status != 200:
        print("No Qdrant server answered. Start one, then run this again.")
        return 2

    found = blocks(POST)
    expected = {"payload", "collection", "indexes", "upsert-cloud", "query-cloud"}
    missing = expected - found.keys()
    record("PASS" if not missing else "FAIL", "all checked blocks present", ", ".join(sorted(missing)))

    cleanup()

    # 1. Collection: size, distance, and TurboQuant bits4 should all be accepted and stored.
    method, path, body = parse_rest(found["collection"])
    status, resp = request(method, path.replace("/recipes", f"/{COLLECTION}"), body)
    record("PASS" if status == 200 else "FAIL", "collection request is accepted", error_text(resp))
    status, resp = request("GET", f"/collections/{COLLECTION}")
    cfg = resp.get("result", {}).get("config", {})
    vectors = cfg.get("params", {}).get("vectors", {})
    quant = cfg.get("quantization_config") or {}
    record(
        "PASS" if vectors.get("size") == DIM and vectors.get("distance") == "Cosine" else "FAIL",
        "stored vector size and distance match the post",
        f"size={vectors.get('size')}, distance={vectors.get('distance')}",
    )
    record(
        "PASS" if quant.get("turbo", {}).get("bits") == "bits4" else "FAIL",
        "stored quantization is turbo bits4",
        json.dumps(quant),
    )
    strict = cfg.get("strict_mode_config") or {}
    record(
        "PASS" if strict.get("enabled") is True and strict.get("unindexed_filtering_retrieve") is False else "FAIL",
        "stored strict mode blocks unindexed filtering",
        json.dumps(strict),
    )

    # 2. Indexes: one request per field, each should succeed.
    index_requests = re.findall(r"PUT (\S+)\n(\{.*?\})", found["indexes"])
    all_ok = True
    for path, raw in index_requests:
        status, resp = request("PUT", path.replace("/recipes", f"/{COLLECTION}"), json.loads(raw))
        if status != 200:
            all_ok = False
            record("FAIL", f"index request {raw}", error_text(resp))
    record("PASS" if all_ok and index_requests else "FAIL", f"{len(index_requests)} payload index requests accepted")

    # 3. Payload from the post: this is the point we load, so it must round-trip unchanged.
    payload = json.loads(found["payload"])
    record("PASS", "payload block is valid JSON", f"{len(payload)} fields")

    # 4. Cloud upsert: the format must be accepted by the server. Without a Cloud
    #    cluster the inference call cannot run, so the server should say it has no
    #    inference service, not that the request is malformed.
    method, path, body = parse_rest(found["upsert-cloud"])
    status, resp = request(method, path.replace("/recipes", f"/{COLLECTION}"), body)
    err = error_text(resp)
    format_ok = status != 200 and "inference" in err.lower() and "format" not in err.lower()
    record(
        "PASS" if format_ok else "FAIL",
        "cloud upsert format is accepted (needs Cloud to run inference)",
        err or f"HTTP {status}",
    )

    # 5. Same upsert with a synthetic vector: checks the payload and point shape end to end.
    point = body["points"][0]
    point["vector"] = [0.01 * (i % 7) for i in range(DIM)]
    status, resp = request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": [point]})
    record("PASS" if status == 200 else "FAIL", "upsert with a 384-dim vector is accepted", error_text(resp))
    status, resp = request("POST", f"/collections/{COLLECTION}/points", {"ids": [1], "with_payload": True})
    stored = resp.get("result", [{}])[0].get("payload", {}) if status == 200 else {}
    record("PASS" if stored == payload else "FAIL", "stored payload matches the post's payload block")

    # 6. Cloud query: the request format must be accepted.
    method, path, body = parse_rest(found["query-cloud"])
    status, resp = request(method, path.replace("/recipes", f"/{COLLECTION}"), body)
    err = error_text(resp)
    format_ok = status != 200 and "inference" in err.lower() and "format" not in err.lower()
    record(
        "PASS" if format_ok else "FAIL",
        "cloud query format is accepted (needs Cloud to run inference)",
        err or f"HTTP {status}",
    )

    # 6b. Strict mode: a search on a field with no index must fail with a clear error.
    status, resp = request(
        "POST",
        f"/collections/{COLLECTION}/points/scroll",
        {"filter": {"must": [{"key": "rating", "range": {"gte": 4}}]}, "limit": 5},
    )
    record(
        "PASS" if status != 200 and "Index required" in error_text(resp) else "FAIL",
        "filter on an unindexed field is rejected by strict mode",
        error_text(resp)[:80] or f"HTTP {status}",
    )

    # 7. The filter from the query: seed two more recipes, then check that the
    #    same filter returns only the Thai dish under 30 minutes.
    seeds = [
        {"id": 2, "vector": [0.02] * DIM, "payload": {**payload, "minutes": 45}},
        {"id": 3, "vector": [0.03] * DIM, "payload": {**payload, "cuisine": "italian", "minutes": 20}},
    ]
    request("PUT", f"/collections/{COLLECTION}/points?wait=true", {"points": seeds})
    filt = body.get("filter")
    status, resp = request(
        "POST",
        f"/collections/{COLLECTION}/points/query",
        {"query": [0.01] * DIM, "filter": filt, "limit": 3, "with_payload": True},
    )
    ids = sorted(p["id"] for p in resp.get("result", {}).get("points", [])) if status == 200 else None
    record(
        "PASS" if ids == [1] else "FAIL",
        "the query filter returns only the Thai dish under 30 minutes",
        f"ids={ids}",
    )

    cleanup()
    return report()


def report() -> int:
    failed = [name for status, name in results if status == "FAIL"]
    skipped = [name for status, name in results if status == "SKIP"]
    print()
    if failed:
        print(f"{len(failed)} check(s) failed:")
        for name in failed:
            print(f"  - {name}")
        return 1
    passed = sum(1 for status, _ in results if status == "PASS")
    print(f"{passed} passed, {len(skipped)} skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
