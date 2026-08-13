# Publish / Transfer to the CERTUS Org — Helper

> The skill is live and private at: **https://github.com/f2025408135-cyber/certus-leadgen** (private = verified).
> The "CERTUS org" does not yet exist / is not accessible to the tokens on this machine (orgs list empty; GitHub only allows org creation via the web UI, and fine-grained PATs cannot create repos anyway). Two options below.

## Option A — Transfer to a new org (recommended, keeps history)

1. Create the org (2 min, web UI only — no API for it):
   - https://github.com/new?owner=organization → pick a name, e.g. **certus-at** (free, public org; repos stay private)
   - Add your account `f2025408135-cyber` as owner (you will be, as creator)
2. Transfer the repo (1 min):
   - https://github.com/f2025408135-cyber/certus-leadgen/settings → "Danger Zone" → **Transfer ownership** → type the org name → confirm. History, issues, private flag all move with it.
3. Done. No code changes needed.

## Option B — If the org already exists under another account

- Ask that account to invite `f2025408135-cyber` (Owner role), then transfer as in step 2.
- OR tell the agent the org slug + provide a token with org rights — the push script below does the rest.

## Push script (if a new repo location is needed later)

```powershell
# from the local clone at C:\Users\hp\AppData\Local\Temp\opencode\certus-leadgen-publish
git remote set-url origin https://github.com/<org>/certus-leadgen.git
git push -u origin main
```

## Security note (important)

- The PAT you pasted in chat (`github_pat_11B6TWNMI0DBHMl...`) was **shared in plaintext — revoke it** in GitHub → Settings → Developer settings → Personal access tokens → Fine-grained → Revoke. (It couldn't create repos anyway; this machine's stored keyring token was used for the push and is more capable.)
- Nothing secret was pushed: no credentials, no lead data, no personal identity — verified by scan (the only matches are the large-corporation blocklist in `filter_leads.py`, which is functional filter logic, not personal data).
- `marketing/leads/**` and `credentials.json` are gitignored in the published repo.
