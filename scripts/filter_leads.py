"""Filter USP award leads per the lead-cracking criteria.

Criteria (from the founder brief):
- Austrian SMEs only: exclude known large corporations + Bietergemeinschaften (consortia)
- Industries: construction, building tech, IT services, architecture/civil engineering (CPV-based)
- Contract value ~€50k–€20M
- Award date: last 6–12 months (configurable)

Usage:
  python filter_leads.py <input.csv> [--out filtered.csv] [--min-value 50000] [--max-value 20000000]
                          [--months 12] [--no-sme-filter]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date, datetime
from pathlib import Path

# Known large Austrian/DACH construction & IT corporations (exclude).
# Substring match on normalized (lowercase, no GmbH/AG suffix) winner name.
# NOTE: keep entries specific enough not to collide with SME surnames.
LARGE_CORPS = [
    "strabag", "porr", "swietelsky", "habau", "alpine", "hochtief", "königshofer",
    "leithäusl", "östu-stettin", "rhomberg", "g. fischer", "granit bau", "teerag-asdag",
    "kirchdorfer", "wienerberger", "strabag property", "max bögl", "leonhard weiss",
    "ed. züblin", "h-inter", "kapsch", "frequentis", "evn", "wien energie", "wiener netze",
    "verbund", "austrian power grid", "streicher", "universale", "bauholding",
    "immofinanz", "südbau", "btg bau", "hilti", "siemens", "swietelsky-tunnel",
    "binder+binder", "bauträger", "strabag-property", "meisterbau",
    "großbau konzern", "tiefbau riesen",  # demo fixture corps
]

INDUSTRY_BY_CPV = {
    "45": "construction",
    "71": "architecture-engineering",
    "72": "it-services",
    "48": "it-services",
    "74": "it-services",   # 74xxxxx consulting/marketing (only if explicitly queried)
}

ALLOWED_CPV_PREFIXES = ("45", "71", "72", "48")


def norm_company(name: str) -> str:
    n = name.lower()
    n = re.sub(r"\b(gmbh|gmbh & co\.? kg|gesellschaft m\.?b\.?h\.?|ag|kg|og|m\.b\.h\.?|co\.? kg|& co\.?)\b", "", n)
    n = re.sub(r"[^a-z0-9öäüß ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def is_large_corp(name: str) -> bool:
    n = norm_company(name)
    for corp in LARGE_CORPS:
        if corp in n:
            return True
    return False


def is_consortium(name: str) -> bool:
    return "bietergemeinschaft" in name.lower() or "ar-ge" in name.lower() or name.lower().startswith("arge ")


def parse_value(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, float):
        return v
    s = str(v).strip().replace("\xa0", " ")
    # German format "11.839.880,91" OR plain "74922.5"
    if "," in s:
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def value_in_range(v: float | None, min_v: float, max_v: float) -> bool:
    if v is None:
        return True  # missing value: keep, flagged for human check
    return min_v <= v <= max_v


def award_within_months(award_date: str, months: int) -> bool:
    if not award_date:
        return True
    try:
        d = datetime.strptime(award_date[:10], "%Y-%m-%d").date()
    except ValueError:
        return True
    cutoff = date.today().replace(day=1)
    for _ in range(months):
        y, m = (cutoff.year - 1, 12) if cutoff.month == 1 else (cutoff.year, cutoff.month - 1)
        cutoff = date(y, m, 1)
    return d >= cutoff


def industry_label(cpv: str) -> str:
    prefix = cpv[:2] if cpv else ""
    return INDUSTRY_BY_CPV.get(prefix, "other")


def filter_rows(rows: list[dict], min_value: float, max_value: float, months: int,
                sme_filter: bool) -> tuple[list[dict], dict]:
    kept, dropped = [], {"large_corp": 0, "consortium": 0, "value": 0, "date": 0, "industry": 0, "no_winner": 0}
    for r in rows:
        winner = (r.get("winner") or "").strip()
        if not winner:
            dropped["no_winner"] += 1
            continue
        if sme_filter and is_large_corp(winner):
            dropped["large_corp"] += 1
            continue
        if is_consortium(winner):
            dropped["consortium"] += 1
            continue
        cpv = (r.get("cpv") or "").split(",")[0]
        if cpv[:2] not in ALLOWED_CPV_PREFIXES:
            dropped["industry"] += 1
            continue
        val = parse_value(r.get("value_eur"))
        if not value_in_range(val, min_value, max_value):
            dropped["value"] += 1
            continue
        if not award_within_months(r.get("award_date") or r.get("contract_date"), months):
            dropped["date"] += 1
            continue
        r = dict(r)
        r["value_eur_parsed"] = val
        r["industry"] = industry_label(cpv)
        r["sme_checked"] = "large-corp-blocklist" if sme_filter else "off"
        r["filter_status"] = "in"
        kept.append(r)
    return kept, dropped


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--out", default=None)
    p.add_argument("--min-value", type=float, default=50_000.0)
    p.add_argument("--max-value", type=float, default=20_000_000.0)
    p.add_argument("--months", type=int, default=12)
    p.add_argument("--no-sme-filter", action="store_true")
    args = p.parse_args()

    inp = Path(args.input)
    with inp.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))

    kept, dropped = filter_rows(rows, args.min_value, args.max_value, args.months, not args.no_sme_filter)
    out = Path(args.out) if args.out else inp.with_name(inp.stem + "_filtered.csv")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(kept[0].keys()) if kept else ["winner"], delimiter=";")
        w.writeheader()
        for r in kept:
            w.writerow(r)
    print(f"[filter] input={len(rows)} kept={len(kept)} dropped={dropped}")
    print(f"[filter] -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
