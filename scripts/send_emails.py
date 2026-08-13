"""Send emails for APPROVED leads — SMTP with app-password credentials.

HARD GATE (inherits the machine's email-automation doctrine):
- Dry-run by default. Real sending requires BOTH:
    1) credentials configured (env vars or marketing/leads/credentials.json), AND
    2) an explicit --send flag AND an approval file listing the recipients
       (marketing/leads/approvals/round1_approved.csv with columns: company,email).
- Never logs the password; never sends to unapproved addresses; per-round tracking.

Credentials (credentials.json, gitignored):
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "you@gmail.com",
  "smtp_pass": "<app-password>",
  "from_name": "Your Name",
  "reply_to": "you@gmail.com"
}
Or env vars: CERTUS_SMTP_HOST/PORT/USER/PASS.

Usage:
  python send_emails.py --drafts marketing/leads/drafts/round1 --approvals marketing/leads/approvals/round1_approved.csv [--send]
  python send_emails.py --drafts ... --approvals ...            # dry-run (default): prints what WOULD be sent
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import smtplib
import sys
from datetime import datetime
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from pathlib import Path

DEFAULT_CREDENTIALS = Path("marketing/leads/credentials.json")
SENT_LOG = Path("marketing/leads/sent-log")
MAX_PER_BATCH = 20  # hard cap per run (volume discipline)


def load_credentials(path: Path) -> dict:
    creds: dict = {}
    if path.exists():
        creds = json.loads(path.read_text(encoding="utf-8"))
    env = {
        "smtp_host": os.environ.get("CERTUS_SMTP_HOST", ""),
        "smtp_port": os.environ.get("CERTUS_SMTP_PORT", ""),
        "smtp_user": os.environ.get("CERTUS_SMTP_USER", ""),
        "smtp_pass": os.environ.get("CERTUS_SMTP_PASS", ""),
    }
    for k, v in env.items():
        if v:
            creds[k] = v
    missing = [k for k in ("smtp_host", "smtp_port", "smtp_user", "smtp_pass") if not creds.get(k)]
    if missing:
        print(f"[send] credentials missing: {missing} (set env CERTUS_SMTP_* or create {path})", file=sys.stderr)
        sys.exit(2)
    creds["smtp_port"] = int(creds["smtp_port"])
    return creds


def load_approved(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"[send] approval file missing: {path} — HARD GATE: nothing will be sent.", file=sys.stderr)
        sys.exit(2)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    out = {}
    for r in rows:
        email = (r.get("email") or "").strip()
        company = (r.get("company") or "").strip()
        if email and company:
            out[company.lower()] = email
    if not out:
        print("[send] approval file has no rows — nothing to send.", file=sys.stderr)
        sys.exit(2)
    return out


def send_one(smtp: smtplib.SMTP, creds: dict, to_email: str, subject: str, body: str) -> None:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((str(Header(creds.get("from_name", creds["smtp_user"]), "utf-8")), creds["smtp_user"]))
    msg["To"] = to_email
    msg["Reply-To"] = creds.get("reply_to", creds["smtp_user"])
    msg["Date"] = formatdate(localtime=True)
    smtp.sendmail(creds["smtp_user"], [to_email], msg.as_string())


def main() -> int:
    p = argparse.ArgumentParser(prog="send_emails.py")
    p.add_argument("--drafts", required=True, help="draft dir (round1/round2)")
    p.add_argument("--approvals", required=True, help="approved recipients CSV")
    p.add_argument("--send", action="store_true", help="REALLY send (default: dry-run)")
    p.add_argument("--subject", default="Kurze Frage zu einem öffentlichen Auftrag")
    p.add_argument("--credentials", default=str(DEFAULT_CREDENTIALS))
    args = p.parse_args()

    approved = load_approved(Path(args.approvals))
    if len(approved) > MAX_PER_BATCH:
        print(f"[send] batch exceeds cap {MAX_PER_BATCH} — split the batch.", file=sys.stderr)
        return 1
    if args.send:
        creds = load_credentials(Path(args.credentials))  # only real sending needs credentials

    drafts = sorted(Path(args.drafts).glob("*.txt"))
    to_send = []
    for f in drafts:
        # map draft file back to company via approval list by matching filename slug
        company_slug = f.stem
        match = None
        for comp in approved:
            if comp.replace(" ", "-").replace(".", "")[:30] in company_slug or company_slug in comp.replace(" ", "-")[:40]:
                match = comp
                break
        if not match:
            continue
        to_send.append((approved[match], match, f))

    if not to_send:
        print("[send] no drafts match the approval list — nothing to send.")
        return 0

    print(f"[send] {len(to_send)} approved emails prepared (dry-run)" if not args.send else f"[send] SENDING {len(to_send)} emails")
    for email, company, f in to_send:
        body = f.read_text(encoding="utf-8")
        if not args.send:
            print(f"  DRY: {company} <{email}> | {f.name} | subject: {args.subject}")
            continue
        try:
            with smtplib.SMTP(creds["smtp_host"], creds["smtp_port"], timeout=60) as smtp:
                smtp.ehlo()
                if creds["smtp_port"] == 587:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(creds["smtp_user"], creds["smtp_pass"])
                send_one(smtp, creds, email, args.subject, body)
            SENT_LOG.mkdir(parents=True, exist_ok=True)
            log = SENT_LOG / "sent.log"
            with log.open("a", encoding="utf-8") as lh:
                lh.write(f"{datetime.now().isoformat()}|{company}|{email}|{f.name}|OK\n")
            print(f"  SENT: {company} <{email}>")
        except Exception as e:
            with (SENT_LOG / "sent.log").open("a", encoding="utf-8") as lh:
                lh.write(f"{datetime.now().isoformat()}|{company}|{email}|{f.name}|ERROR|{e}\n")
            print(f"  FAIL: {company} <{email}>: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
