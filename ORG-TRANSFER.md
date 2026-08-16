# certus-leadgen → certustenders org: exact handover (verified status 2026-08-09)

## Current state
- Repo: **private** at `github.com/f2025408135-cyber/certus-leadgen` — complete, sanitized, tested (10/10), pushed.
- Org: **certustenders exists** (`github.com/orgs/certustenders/dashboard`) — but is owned by a **different GitHub account**.
- Verified limits (API evidence):
  - `f2025408135-cyber` is NOT a member of certustenders ("You must be a member of certustenders…" 403).
  - Both fine-grained PATs **cannot create org repos** ("You need admin access to the organization…" 403) and **cannot run transfers** ("Resource not accessible…" 403).
  - → No available token can move the repo into the org. **The org owner must do one 60-second step.**

## Option A — Import (recommended: keeps full history, zero access-granting)
1. Log into the account that owns certustenders (browser).
2. https://github.com/new/import  (or org → Repositories → **New → Import repository**)
3. Source: `https://github.com/f2025408135-cyber/certus-leadgen.git`
   - Owner: **certustenders** · Name: **certus-leadgen** · Privacy: **Private**
   - Credentials: GitHub username `f2025408135-cyber` + its PAT (**Token A**, in the keyring — or generate a classic PAT with `repo` scope on that account)
4. Import runs in minutes → repo lives in the org with history.

## Option B — Create empty + push (then this machine pushes)
1. Org owner: certustenders → **Repositories → New** → `certus-leadgen` → **Private** → Create (do NOT add a README).
2. Org owner: repo → Settings → Collaborators → add **f2025408135-cyber** with Write.
3. This machine (one command):
   ```powershell
   git remote set-url origin https://github.com/certustenders/certus-leadgen.git
   git push -u origin main
   ```
4. Optional: delete the old `f2025408135-cyber/certus-leadgen` (or keep as backup).

## Option C — Transfer (if you prefer)
1. Org owner: certustenders → Settings/People → invite **f2025408135-cyber** as Owner (accept on that account).
2. Then on the account f2025408135-cyber: repo → Settings → Danger Zone → **Transfer ownership** → `certustenders` → confirm.
3. Private flag + history move with it. No re-push needed.

## After the move
- Update this repo's `README.md` badge/links if they reference the old URL (they don't).
- **Revoke both PATs pasted in chat** (Settings → Developer settings → Personal access tokens). If Token A is revoked, re-auth: `gh auth login`.
