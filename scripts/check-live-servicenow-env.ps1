$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $Root ".env"

function Read-EnvMap {
  param([string]$Path)
  $map = @{}
  if (!(Test-Path -LiteralPath $Path)) {
    return $map
  }
  foreach ($line in Get-Content -LiteralPath $Path) {
    $trimmed = $line.Trim()
    if (!$trimmed -or $trimmed.StartsWith("#") -or !$trimmed.Contains("=")) {
      continue
    }
    $parts = $trimmed.Split("=", 2)
    $key = $parts[0].Trim()
    $value = $parts[1].Trim().Trim("'").Trim('"')
    if ($key) {
      $map[$key] = $value
    }
  }
  return $map
}

if (!(Test-Path -LiteralPath $EnvFile)) {
  Write-Host ".env is missing."
  exit 2
}

$map = Read-EnvMap $EnvFile
$required = @(
  "OPENAI_API_KEY",
  "OPENAI_MODEL",
  "APP_MODE",
  "SERVICENOW_INSTANCE_URL",
  "SERVICENOW_USERNAME",
  "SERVICENOW_PASSWORD",
  "SERVICENOW_CREATE_INCIDENTS",
  "SERVICENOW_UPDATE_INCIDENTS"
)

$missing = @()
foreach ($name in $required) {
  if (!$map.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($map[$name]) -or $map[$name] -eq "replace_me") {
    $missing += $name
  }
}
if ($missing.Count -gt 0) {
  Write-Host ("Missing .env values: " + ($missing -join ", "))
  exit 2
}

if ($map["APP_MODE"].ToLowerInvariant() -ne "live") {
  Write-Host "APP_MODE must be live for real PDI create/update."
  exit 2
}

if ($map["SERVICENOW_CREATE_INCIDENTS"].ToLowerInvariant() -ne "true" -or $map["SERVICENOW_UPDATE_INCIDENTS"].ToLowerInvariant() -ne "true") {
  Write-Host "SERVICENOW_CREATE_INCIDENTS and SERVICENOW_UPDATE_INCIDENTS must both be true."
  exit 2
}

Write-Host "Live ServiceNow/OpenAI .env settings detected."
Write-Host ("ServiceNow URL: " + $map["SERVICENOW_INSTANCE_URL"])
Write-Host ("OpenAI model: " + $map["OPENAI_MODEL"])
exit 0
