"""Check that every source_url in evidence_store.json still resolves."""

import json
import time
import urllib.request
import urllib.error
from collections import defaultdict

STORE = "evidence_store.json"
FIELDS = ["role", "food_sources", "reference_intake", "upper_limit", "regulatory_flags"]
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) lagomy-link-check"

store = json.load(open(STORE))
cited_by = defaultdict(set)
for key, entry in store.items():
    for field in FIELDS:
        for s in entry["evidence"].get(field, []):
            cited_by[s["source_url"]].add(key)


def status(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return r.status
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return e.code
        except Exception as e:
            return f"ERROR {type(e).__name__}"
    return "ERROR"


def category(code):
    if isinstance(code, int) and 200 <= code < 400:
        return "OK"
    if code in (404, 410):
        return "BROKEN"
    if code in (401, 403, 429):
        return "BLOCKED"
    return "OTHER"


urls = sorted(cited_by)
print(f"Checking {len(urls)} unique URLs...")
found = defaultdict(list)
for url in urls:
    code = status(url)
    found[category(code)].append((url, code))
    time.sleep(0.3)

print()
for cat in ("OK", "BROKEN", "BLOCKED", "OTHER"):
    print(f"{cat}: {len(found[cat])}")
for cat in ("BROKEN", "OTHER", "BLOCKED"):
    for url, code in found[cat]:
        print(f"\n[{cat} {code}] {url}")
        print("   cited by:", ", ".join(sorted(cited_by[url])))

       