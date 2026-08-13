"""Email research helper — find a company's public email from its website.

Strategy per the founder brief: company website -> Impressum or contact page.
This script fetches a website, finds imprint/contact links, and extracts emails.
For top leads the skill-runner (LLM) should additionally verify the best contact
person and preferred address — the script's output is the starting point.

Usage:
  python research_email.py --company "Musterbau Huber GmbH" --website https://www.musterbau-huber.example.at
  python research_email.py --file filtered.csv --website-col website --out enriched.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Certus-Leadgen)"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
LINK_HINTS = ("impressum", "kontakt", "contact", "imprint", "about", "ueber", "über", "team")
BLOCKED_DOMAINS = ("example.com", "example.org", "wixpress", "sentry", "schema.org", "w3.org", ".png", ".jpg", ".gif", ".svg", ".css", ".js")


def fetch(url: str, timeout: int = 25) -> str | None:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        if r.status_code == 200 and "text" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        return None
    return None


def find_emails(html: str) -> list[str]:
    out = []
    for m in EMAIL_RE.findall(html or ""):
        m = m.strip(".")
        if m.lower().endswith(tuple(BLOCKED_DOMAINS)) or m.lower().startswith(("noreply", "no-reply", "webmaster", "hostmaster")):
            continue
        if m not in out:
            out.append(m)
    return out


def find_link_pages(base_url: str, html: str) -> list[str]:
    pages = []
    for m in re.finditer(r'href=["\']([^"\']+)["\']', html or ""):
        href = m.group(1)
        low = href.lower()
        if any(h in low for h in LINK_HINTS):
            pages.append(urljoin(base_url, href))
    # dedupe, keep domain-internal
    host = urlparse(base_url).netloc
    seen, out = set(), []
    for u in pages:
        if urlparse(u).netloc and urlparse(u).netloc != host:
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:6]


def research(website: str) -> dict:
    if not website:
        return {"website": "", "email": "", "emails": [], "source": ""}
    html = fetch(website)
    if not html:
        return {"website": website, "email": "", "emails": [], "source": "unreachable"}
    emails = find_emails(html)
    source = website
    if not emails:
        for page in find_link_pages(website, html):
            page_html = fetch(page)
            found = find_emails(page_html)
            if found:
                emails = found
                source = page
                break
    # prefer generic business addresses
    email = ""
    for pref in ("office", "kontakt", "info", "buero", "buro"):
        for e in emails:
            if e.lower().startswith(pref):
                email = e
                break
        if email:
            break
    if not email and emails:
        email = emails[0]
    return {"website": website, "email": email, "emails": emails, "source": source}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--company", default="")
    p.add_argument("--website", default="")
    p.add_argument("--file", default=None)
    p.add_argument("--website-col", default="website")
    p.add_argument("--out", default=None)
    p.add_argument("--limit", type=int, default=0)
    args = p.parse_args()

    if args.file:
        inp = Path(args.file)
        with inp.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh, delimiter=";"))
        if not rows:
            print("[research] no rows")
            return 1
        cols = list(rows[0].keys())
        for c in ("email", "email_source", "emails_all"):
            if c not in cols:
                cols.append(c)
        n = args.limit or len(rows)
        for i, row in enumerate(rows[:n]):
            if row.get("email"):
                continue  # already researched
            print(f"  {i + 1}/{n}: {row.get('winner', '?')[:40]}", end=" ")
            res = research(row.get(args.website_col, ""))
            row["email"] = res["email"]
            row["email_source"] = res["source"]
            row["emails_all"] = ";".join(res["emails"])
            print(f"-> {res['email'] or 'NONE'} ({res['source'][:50]})")
        out = Path(args.out) if args.out else inp.with_name(inp.stem + "_researched.csv")
        with out.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, delimiter=";")
            w.writeheader()
            for row in rows:
                w.writerow(row)
        print(f"[research] -> {out}")
        return 0

    res = research(args.website)
    print(json_dump(res))
    return 0


def json_dump(d: dict) -> str:
    import json
    return json.dumps(d, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    sys.exit(main())
