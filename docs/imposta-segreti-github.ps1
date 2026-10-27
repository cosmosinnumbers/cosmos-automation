# Carica su GitHub i segreti dei workflow di cosmos-automation, leggendo i file di secrets\ SENZA mostrarli
# (li lancia Simone). Si può rilanciare quando un token cambia.
#   powershell -ExecutionPolicy Bypass -File C:\Users\Simon\progetti_claude\cosmos-automation\docs\imposta-segreti-github.ps1
$S = "C:\Users\Simon\progetti_claude\Progetto-YouTube-Faceless\secrets"
$C = "cosmosinnumbers/cosmos-automation"

function Set-FromFile($name, $files) {
    foreach ($f in $files) {
        if (Test-Path "$S\$f") {
            Get-Content -Raw "$S\$f" | gh secret set $name --repo $C
            if ($LASTEXITCODE -eq 0) { "ok    $name" } else { "ERRORE $name" }
            return
        }
    }
    "manca $($files -join ' / ') (salto $name)"
}

Set-FromFile YOUTUBE_TOKEN_JSON @("token.json")
Set-FromFile YOUTUBE_ANALYTICS_TOKEN_JSON @("token_analytics.json")
Set-FromFile GUMROAD_JSON @("gumroad.json", "gumroad.json.txt")
"Fatto. Nessun valore è stato mostrato."
