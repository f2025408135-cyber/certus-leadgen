# certus-leadgen — USP Award-Notice Lead Engine + Cold Email Skill

An opencode skill that cracks B2B leads for **Certus** (AI pricing for Austrian construction tenders) from legally published **contract award notices** on [ausschreibungen.usp.gv.at](https://ausschreibungen.usp.gv.at) (USP eProcurement Austria), then prepares — and, after human approval, sends — personalized warm-open German outreach emails.

**Logic:** a company that just won a public contract actively participates in public tenders → knows the process → is the ideal target customer for tender-pricing software.

> ⚠️ **HARD GATE:** nothing is ever sent without (a) an explicit approval file listing the exact recipients, (b) a `--send` flag, and (c) configured credentials. The scripts enforce this.

## Pipeline (one command per stage)

| # | Stage | Script | Output |
|---|---|---|---|
| 1 | **Extract** award notices (Bekanntgaben) from USP | `usp_leads.py` | `raw/usp_awards_<date>.csv` (winner, value €, award date, authority, title, URL) |
| 2 | **Filter** (AT SMEs, industries, €50k–€20M, 12 months) | `filter_leads.py` | filtered CSV with drop reasons |
| 3 | **Research** emails (website → Impressum/Kontakt) | `research_email.py` | enriched CSV (email, source) |
| 4 | **Track** in Excel | `leads_tracker.py` | `leads_formatted.xlsx`, sheet **"Cold Email"**, per-round status |
| 5 | **Draft** personalized warm-open emails | `generate_drafts.py` | `drafts/round1/<company>.txt` + preview |
| 6 | **Approve** (human) | — | `approvals/round1_approved.csv` (`company;email`) |
| 7 | **Send** via SMTP (app password) | `send_emails.py` | sent-log, tracker updates |

## Quick start

```bash
# 1) install deps
pip install -r requirements.txt

# 2) sender identity (copy + fill)
cp config.example.json marketing/leads/sender_config.json

# 3) credentials (env vars OR marketing/leads/credentials.json — gitignored)
export CERTUS_SMTP_HOST=smtp.gmail.com
export CERTUS_SMTP_PORT=587
export CERTUS_SMTP_USER=you@gmail.com
export CERTUS_SMTP_PASS=<app-password>

# 4) extract + filter + research
python scripts/usp_leads.py --cpvs 45000000,71000000,72000000,48000000 \
  --from 2025-08-09 --to 2026-08-09 --max-leads 200 --delay 1.0 \
  --out marketing/leads/raw/usp_awards_$(date +%F).csv
python scripts/filter_leads.py marketing/leads/raw/usp_awards_$(date +%F).csv
python scripts/research_email.py --file marketing/leads/raw/usp_awards_$(date +%F)_filtered.csv --limit 20

# 5) tracker + drafts
python scripts/leads_tracker.py import marketing/leads/raw/usp_awards_$(date +%F)_filtered_researched.csv
python scripts/generate_drafts.py --csv marketing/leads/raw/usp_awards_$(date +%F)_filtered_researched.csv \
  --round 1 --config marketing/leads/sender_config.json --max 20

# 6) human approves -> approvals/round1_approved.csv (company;email)

# 7) dry-run first, then real send
python scripts/send_emails.py --drafts marketing/leads/drafts/round1 \
  --approvals marketing/leads/approvals/round1_approved.csv
python scripts/send_emails.py --drafts marketing/leads/drafts/round1 \
  --approvals marketing/leads/approvals/round1_approved.csv --send
```

## Tests

```bash
python -m pytest tests -q   # 10 tests: parsing, filtering, tracker, drafts, send gate
```

## Guardrails

- **Hard approval gate** for every send (approval file + `--send` + credentials).
- **No product pitch in round 1** — the warm-open uses a university-project framing (fully configurable in `sender_config.json`); product mention is a later-round decision.
- **GDPR/B2B etiquette:** award data is legally published; emails come from company Imprints; volume cap ≤20/week; ≤2 rounds per lead; opt-outs honored immediately; records retained ≤12 months.
- **Rate discipline:** USP fetch delay ≥1.0s (the site rate-limits itself); SMTP batches ≤20.
- **PII:** all lead data lives in `marketing/leads/` (gitignored). Never commit `credentials.json`.

## As an opencode skill

Install this folder as `.opencode/skills/certus-leadgen/` in the Certus repo. Invoke with: "leadgen", "find leads", "cold email", "USP", "Zuschläge". The skill then runs stages 1–5, surfaces drafts + approval list, and waits for the human gate.

## Disclaimer

The USP site is a public service; this tool reads public data politely (rate-limited, no credentials, no scraping of protected areas). Data accuracy varies — values marked "not published" are kept and flagged for human review, never fabricated. This project is not affiliated with the USP/BRZ.
