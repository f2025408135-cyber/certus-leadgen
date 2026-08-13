"""USP eProcurement Austria — award notice (Bekanntgabe) lead extractor.

Source: https://ausschreibungen.usp.gv.at (public, legally required award publications)
API (reverse-engineered from the public site, verified 2026-08-09):
  GET /at.gv.bmdw.eproc-p/public/api/tenderlist?kdBaseTypes[0]=bg&cpvList[0]=...&fromdate=&todate=&start=&length=
  Detail: GET /at.gv.bmdw.eproc-p/public/tender-detail?object=<uuid>  (award winner + value)

Extracts per award: title, authority, award date, winner company, value EUR,
contract date, UUID, detail URL. Outputs CSV (UTF-8, ';').

Usage:
  python usp_leads.py [--cpvs 45000000,71000000,72000000] [--from 2025-08-09] [--to 2026-08-09]
                     [--max-leads 300] [--delay 1.0] [--out marketing/leads/raw/usp_awards_YYYY-MM-DD.csv]

Be polite: --delay default 1.0s between detail fetches (the site itself rate-limits ~1s).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://ausschreibungen.usp.gv.at/at.gv.bmdw.eproc-p"
LIST_API = f"{BASE}/public/api/tenderlist"
DEFAULT_CPVS = ["45000000", "71000000", "72000000", "48000000"]  # Bau, Architektur/Ingenieur, IT-Dienste, Software

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (Certus-Leadgen; contact: founder)"


def fetch_list(session: requests.Session, cpvs: list[str], fromdate: str, todate: str,
               start: int = 0, length: int = 100) -> dict:
    params = {
        "draw": "1", "start": str(start), "length": str(length),
        "order[0][column]": "2", "order[0][dir]": "desc",
        "orderColumn": "2", "orderDir": "desc",
        "kdBaseTypes[0]": "bg",  # Bekanntgabe = contract award notices
        "fromdate": fromdate, "todate": todate,
    }
    for i, cpv in enumerate(cpvs):
        params[f"cpvList[{i}]"] = cpv
    r = session.get(LIST_API, params=params, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"  # USP serves UTF-8; requests may guess wrong without charset header
    return r.json()


def parse_value(text: str) -> float | None:
    """'11.839.880,91 €' -> 11839880.91 ; '74922.5' -> 74922.5 ; None if unparsable."""
    if not text:
        return None
    m = re.search(r"([\d.\s]+,\d{2})\s*€?", text.replace("\xa0", " "))
    if m:
        try:
            return float(m.group(1).replace(".", "").replace(",", ".").replace(" ", ""))
        except ValueError:
            return None
    try:
        return float(str(text).strip())
    except ValueError:
        return None


def text_of(html: str) -> str:
    import html as _html
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " | ", html)
    t = re.sub(r"\|+", "|", t)
    return re.sub(r"\s+", " ", _html.unescape(t))


def field_after(text: str, label: str, limit: int = 220) -> str:
    """Value of a label:value pair in the tag-stripped detail text."""
    i = text.find(label)
    if i < 0:
        return ""
    seg = text[i + len(label):i + len(label) + limit]
    seg = seg.strip(" |")
    # cut at the next obvious label start
    seg = re.split(r"\s{2,}", seg)[0] if re.search(r"\s{2,}", seg) else seg
    return seg.strip(" |").strip()


def fetch_detail(session: requests.Session, uuid: str) -> dict:
    """Fetch award detail (structural parse of the Thymeleaf cards)."""
    for detail_type in ("tender-detail", "notice-detail"):
        r = session.get(f"{BASE}/public/{detail_type}", params={"object": uuid}, timeout=60)
        if r.status_code != 200:
            continue
        r.encoding = "utf-8"
        html = r.text
        # winner: <h3 class="mx-2"> inside the 'Auftragnehmer' collapsible card
        m = re.search(r'<a[^>]*>\s*Auftragnehmer\s*</a>.*?<h3 class="mx-2">([^<]+)</h3>', html, re.S)
        winner = _clean(m.group(1)) if m else ""
        # authority: first h3 on the page (Auftraggeber card)
        m = re.search(r'<h3 class="mx-2">([^<]+)</h3>', html)
        authority = _clean(m.group(1)) if m else ""
        # kdd-group pairs: <dt>Label:</dt><dd>Value</dd>
        pairs = {}
        for dm in re.finditer(r"<dt>([^<]+):</dt>\s*<dd>([^<]*)</dd>", html, re.S):
            pairs[_clean(dm.group(1))] = _clean(dm.group(2))
        value_raw = pairs.get("Auftragswert bzw. Wertumfang", "")
        contract_date = pairs.get("Tag des Vertragsabschlusses", "")
        stammzahl = pairs.get("Stammzahl", "")
        if not winner and "Auftragnehmer" not in html:
            continue
        return {
            "winner": winner, "authority_page": authority, "value_raw": value_raw,
            "value_eur": parse_value(value_raw), "contract_date": contract_date,
            "stammzahl": stammzahl,
            "detail_url": f"{BASE}/public/{detail_type}?object={uuid}",
            "detail_type": detail_type,
        }
    return {"winner": "", "authority_page": "", "value_raw": "", "value_eur": None,
            "contract_date": "", "stammzahl": "", "detail_url": "", "detail_type": "not-found"}


def _clean(s: str) -> str:
    import html as _html
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def run(cpvs: list[str], fromdate: str, todate: str, max_leads: int, delay: float,
        out_path: Path, session: requests.Session | None = None) -> list[dict]:
    s = session or requests.Session()
    s.headers.update({"User-Agent": UA})
    leads: list[dict] = []
    start = 0
    total = None
    while len(leads) < max_leads:
        j = fetch_list(s, cpvs, fromdate, todate, start=start, length=100)
        total = j.get("recordsFiltered")
        rows = j.get("data", [])
        if not rows:
            break
        for row in rows:
            if len(leads) >= max_leads:
                break
            lead = {
                "tender_title": row[0] or "",
                "authority": row[1] or "",
                "award_date": row[2] or "",
                "uuid": row[4] or "",
                "is_notice": bool(row[5]),
                "cpv": ",".join(cpvs),
            }
            time.sleep(delay)
            try:
                d = fetch_detail(s, lead["uuid"])
            except Exception as e:  # transient network issues: skip, don't die
                print(f"  [warn] detail fetch failed {lead['uuid']}: {e}", file=sys.stderr)
                d = {"winner": "", "value_raw": "", "value_eur": None, "contract_date": "",
                     "stammzahl": "", "detail_url": "", "detail_type": "error"}
            lead.update(d)
            lead["source_url"] = lead["detail_url"] or f"{BASE}/public/tender-detail?object={lead['uuid']}"
            leads.append(lead)
            print(f"  {len(leads):>3}/{total}: {lead['winner'][:40] or '?'} | {lead['value_eur']} | {lead['award_date']}")
        start += 100
        if start >= (total or 0):
            break
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "tender_title", "authority", "award_date", "winner", "value_eur", "value_raw",
            "contract_date", "stammzahl", "cpv", "uuid", "source_url"], delimiter=";")
        w.writeheader()
        for lead in leads:
            w.writerow({k: lead.get(k, "") for k in w.fieldnames})
    print(f"[usp_leads] {len(leads)} awards -> {out_path}")
    return leads


def main() -> int:
    p = argparse.ArgumentParser(description="USP award-notice lead extractor")
    p.add_argument("--cpvs", default=",".join(DEFAULT_CPVS), help="comma-separated CPV codes")
    p.add_argument("--from", dest="fromdate", default=(date.today() - timedelta(days=365)).isoformat())
    p.add_argument("--to", dest="todate", default=date.today().isoformat())
    p.add_argument("--max-leads", type=int, default=300)
    p.add_argument("--delay", type=float, default=1.0)
    p.add_argument("--out", default=str(Path("marketing/leads/raw") / f"usp_awards_{date.today().isoformat()}.csv"))
    args = p.parse_args()
    run(args.cpvs.split(","), args.fromdate, args.todate, args.max_leads, args.delay, Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
