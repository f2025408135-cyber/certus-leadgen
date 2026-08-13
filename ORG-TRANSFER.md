# Transfer certus-leadgen to the CERTUS org — one command once the org is reachable

## Status (verified 2026-08-09)
- Repo is live and **private**: `https://github.com/f2025408135-cyber/certus-leadgen`
- **Token A** (keyring, `github_pat_11B6TWNMI0rjBQEAC1nrbG_…`) = works: read/write, admin on this repo, can create repos.
- **Token B** (the "org token", `github_pat_11B6TWNMI0DBHMl…`) = NO org access, NO repo write, NO repo creation (verified 403s). It is not usable for this task.
- The account `f2025408135-cyber` is currently a member of **no org** (checked via API + public membership + profile). The CERTUS org is therefore not reachable with the available credentials.

## What must happen first (human, 2 min, web UI)
1. Create the org (if it doesn't exist): https://github.com/new?owner=organization → e.g. **certus-at**
2. Make sure the account `f2025408135-cyber` is a member of that org (Owner role).
3. Tell the agent the org slug — or run the script below.

## Then: run the transfer (one command)

```powershell
# from the repo clone:
.\scripts\transfer-to-org.ps1 -Org <org-slug>
```

It performs: `POST /repos/f2025408135-cyber/certus-leadgen/transfer` with `new_owner=<org>` (private flag preserved), then re-points the local remote. History, issues, and privacy move with the repo.

## Fallback (if the transfer API is blocked for fine-grained tokens)

```powershell
.\scripts\transfer-to-org.ps1 -Org <org-slug> -Fallback
```
→ creates a private repo in the org (needs a token with org rights — e.g. a classic PAT with `repo` scope, or the UI) and pushes a mirror, then the old repo can be deleted.

## Security reminder
- Both PATs were pasted in chat → **revoke them** after the transfer (Settings → Developer settings → Personal access tokens). The transfer itself should use Token A.
