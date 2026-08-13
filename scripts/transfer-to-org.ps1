# Transfer certus-leadgen to an org (one command). Usage:
#   .\scripts\transfer-to-org.ps1 -Org <org-slug> [-Fallback]
# Requires: gh CLI authenticated as f2025408135-cyber (Token A in keyring).
param(
    [Parameter(Mandatory = $true)][string]$Org,
    [switch]$Fallback
)

$repo = "f2025408135-cyber/certus-leadgen"
Write-Host "[transfer] target org: $Org"

if ($Fallback) {
    Write-Host "[transfer] FALLBACK: creating private repo in org $Org ..."
    gh repo create "$Org/certus-leadgen" --private --description "USP award-notice lead engine + cold email skill (private)" --source $repo --push
    if ($LASTEXITCODE -ne 0) { Write-Host "[transfer] FAILED — org not accessible with current token."; exit 1 }
    Write-Host "[transfer] mirror pushed. Old repo at $repo can be deleted manually."
    exit 0
}

Write-Host "[transfer] calling transfer API (new_owner=$Org) ..."
gh api -X POST "repos/$repo/transfer" -f "new_owner=$Org" --jq ".full_name"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[transfer] transfer API failed. Try: -Fallback (mirror) or check that the account is an org member and the token has admin on the repo."
    exit 1
}
Write-Host "[transfer] OK -> https://github.com/$Org/certus-leadgen (private preserved)"
git remote set-url origin "https://github.com/$Org/certus-leadgen.git"
Write-Host "[transfer] local remote re-pointed."
