"""Draft generator — personalized warm-open German emails faithful to the founder's example.

Example (verbatim basis):
    Guten Tag, liebes Team der [Company],
    mein Name ist [Your First Name] und ich bin [Your context line] und habe gesehen, dass Sie im Mai
    diesen Jahres den Auftrag zur [Tender title] der Wiener
    Gesundheitsverbund gewonnen haben. Gratulation erstmal dazu.
    Im Rahmen eines Uni Projekts befrage ich Firmen zu öffentlichen Ausschreibungen, um die
    Branche besser zu verstehen. Dabei wollte ich Sie fragen:
    Was war bei der Angebotserstellung dieses Auftrags der aufwendigste Teil?
    Über eine zwei Zeilen Antwort würde ich mich riesig freuen.
    Vielen Dank und beste Grüße, [Your Full Name], [Your Phone]

Config: marketing/leads/sender_config.json (see config.example.json in the skill dir).
Output: marketing/leads/drafts/round1/<slug>.txt (+ one combined preview file).

Usage:
  python generate_drafts.py --csv <researched.csv> --round 1 [--config path] [--max 20]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_CONFIG = Path("marketing/leads/sender_config.json")
DEFAULT_DRAFTS = Path("marketing/leads/drafts")

MONTHS_DE = ["", "Januar", "Februar", "März", "April", "Mai", "Juni",
             "Juli", "August", "September", "Oktober", "November", "Dezember"]


def load_config(path: Path) -> dict:
    if not path.exists():
        print(f"[drafts] config missing: {path} — copy config.example.json to {path} and fill in.", file=sys.stderr)
        sys.exit(2)
    cfg = json.loads(path.read_text(encoding="utf-8"))
    need = ["sender_name", "sender_line", "question", "signature_name", "phone"]
    missing = [n for n in need if not cfg.get(n)]
    if missing:
        print(f"[drafts] config missing fields: {missing}", file=sys.stderr)
        sys.exit(2)
    return cfg


def month_de(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        m = int(date_str[5:7])
        return MONTHS_DE[m] if 1 <= m <= 12 else ""
    except (ValueError, IndexError):
        return ""


def render_round1(lead: dict, cfg: dict) -> str:
    company = (lead.get("winner") or lead.get("company") or "Ihr Unternehmen").strip()
    title = (lead.get("tender_title") or "Ihren zuletzt gewonnenen Auftrag").strip()
    authority = (lead.get("authority") or "").strip()
    award_date = lead.get("award_date") or ""
    month = month_de(award_date)
    time_note = f" im {month} diesen Jahres" if month else " kürzlich"

    authority_part = f" der {authority}" if authority else ""
    title_part = f" den Auftrag zu {title}" if lead.get("tender_title") else " einen öffentlichen Auftrag"
    line = f"Guten Tag, liebes Team der {company},\n\n"
    line += f"mein Name ist {cfg['sender_name']} und ich bin {cfg['sender_line']} und habe gesehen, dass Sie{time_note}{title_part}{authority_part} gewonnen haben. Gratulation erstmal dazu.\n\n"
    line += "Im Rahmen eines Uni Projekts befrage ich Firmen zu öffentlichen Ausschreibungen, um die Branche besser zu verstehen. Dabei wollte ich Sie fragen:\n\n"
    line += f"{cfg['question']}\n\n"
    line += "Über eine zwei Zeilen Antwort würde ich mich riesig freuen.\n\n"
    line += f"Vielen Dank und beste Grüße,\n\n{cfg['signature_name']}\n{cfg['phone']}"
    return line


def render_round2(lead: dict, cfg: dict) -> str:
    company = (lead.get("winner") or lead.get("company") or "").strip()
    line = f"Guten Tag, liebes Team der {company},\n\n"
    line += "ich wollte mich nur kurz melden — falls meine letzte Nachricht untergegangen ist: Ich wäre weiterhin sehr an einer kurzen Einschätzung interessiert.\n\n"
    line += f"{cfg['question']}\n\n"
    line += "Über zwei Zeilen freue ich mich riesig.\n\n"
    line += f"Beste Grüße,\n{cfg['signature_name']}\n{cfg['phone']}"
    return line


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9äöüß]+", "-", name.lower()).strip("-")
    return s[:60] or "lead"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--round", choices=["1", "2"], default="1")
    p.add_argument("--config", default=str(DEFAULT_CONFIG))
    p.add_argument("--max", type=int, default=20)
    p.add_argument("--outdir", default=str(DEFAULT_DRAFTS))
    args = p.parse_args()

    cfg = load_config(Path(args.config))
    with Path(args.csv).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))

    outdir = Path(args.outdir) / f"round{args.round}"
    outdir.mkdir(parents=True, exist_ok=True)
    n = 0
    preview = []
    for lead in rows:
        if not (lead.get("email") or "").strip():
            continue  # only leads with a researched address
        if n >= args.max:
            break
        body = render_round1(lead, cfg) if args.round == "1" else render_round2(lead, cfg)
        company = (lead.get("winner") or lead.get("company") or "lead").strip()
        f = outdir / f"{n + 1:02d}-{slug(company)}.txt"
        f.write_text(body, encoding="utf-8")
        preview.append(f"### {company} <{lead.get('email')}>  (award: {lead.get('tender_title', '')[:60]} | {lead.get('authority', '')})\n\n{body}\n")
        n += 1

    combined = outdir / "_preview_all.txt"
    combined.write_text("\n\n" + "=" * 70 + "\n\n".join(preview), encoding="utf-8")
    print(f"[drafts] {n} drafts -> {outdir} (preview: {combined})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
