$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$EnvFile = Join-Path $Root ".env"
$TemplateFile = Join-Path $Root ".env.example"

function Read-EnvMap {
  param([string]$Path)
  $map = [ordered]@{}
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
    $value = $parts[1].Trim()
    if ($value.Length -ge 2 -and $value[0] -eq $value[$value.Length - 1] -and ($value[0] -eq '"' -or $value[0] -eq "'")) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    if ($key) {
      $map[$key] = $value
    }
  }
  return $map
}

function ConvertFrom-Secure {
  param([Security.SecureString]$Value)
  if ($null -eq $Value -or $Value.Length -eq 0) {
    return ""
  }
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
  try {
    return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
  } finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
  }
}

function Read-Setting {
  param(
    [string]$Name,
    [string]$Prompt,
    [string]$Default = "",
    [switch]$Secret,
    [switch]$Required
  )

  $current = ""
  if ($settings.Contains($Name)) {
    $current = [string]$settings[$Name]
  }
  if (!$current -or $current -eq "replace_me") {
    $current = $Default
  }

  $suffix = ""
  if ($current) {
    $suffix = if ($Secret) { " [current: set, Enter keeps it]" } else { " [current: $current]" }
  }

  while ($true) {
    if ($Secret) {
      $secure = Read-Host "$Prompt$suffix" -AsSecureString
      $value = ConvertFrom-Secure $secure
    } else {
      $value = Read-Host "$Prompt$suffix"
    }
    if (!$value -and $current) {
      return $current
    }
    if ($value) {
      return $value
    }
    if (!$Required) {
      return ""
    }
    Write-Host "$Name is required." -ForegroundColor Yellow
  }
}

function Format-EnvValue {
  param([string]$Value)
  if ($null -eq $Value) {
    return ""
  }
  if ($Value -match '\s|#') {
    return '"' + ($Value -replace '"', '\"') + '"'
  }
  return $Value
}

$settings = Read-EnvMap $TemplateFile
foreach ($entry in (Read-EnvMap $EnvFile).GetEnumerator()) {
  $settings[$entry.Key] = $entry.Value
}

Write-Host ""
Write-Host "NEXUS-RESOLVE live ServiceNow setup" -ForegroundColor Cyan
Write-Host "Secrets stay only in local .env, which is ignored by git."
Write-Host "Press Enter to keep an existing value."
Write-Host ""

$settings["OPENAI_API_KEY"] = Read-Setting "OPENAI_API_KEY" "OpenAI API key" $env:OPENAI_API_KEY -Secret -Required
$settings["OPENAI_MODEL"] = Read-Setting "OPENAI_MODEL" "OpenAI model" ($(if ($env:OPENAI_MODEL) { $env:OPENAI_MODEL } else { "gpt-5.5" })) -Required
$settings["APP_MODE"] = "live"

$settings["SERVICENOW_INSTANCE_URL"] = Read-Setting "SERVICENOW_INSTANCE_URL" "ServiceNow PDI URL, for example https://dev123.service-now.com" -Required
$settings["SERVICENOW_USERNAME"] = Read-Setting "SERVICENOW_USERNAME" "ServiceNow PDI username" -Required
$settings["SERVICENOW_PASSWORD"] = Read-Setting "SERVICENOW_PASSWORD" "ServiceNow PDI password" -Secret -Required
$settings["SERVICENOW_TABLE"] = Read-Setting "SERVICENOW_TABLE" "ServiceNow table" "incident" -Required
$settings["SERVICENOW_CREATE_INCIDENTS"] = "true"
$settings["SERVICENOW_UPDATE_INCIDENTS"] = "true"
$settings["SERVICENOW_CALLER_ID"] = Read-Setting "SERVICENOW_CALLER_ID" "Optional caller_id reference value" "" 
$settings["SERVICENOW_ASSIGNMENT_GROUP"] = Read-Setting "SERVICENOW_ASSIGNMENT_GROUP" "Optional assignment_group reference value" ""
$settings["SERVICENOW_CATEGORY"] = Read-Setting "SERVICENOW_CATEGORY" "ServiceNow category" "inquiry" -Required
$settings["SERVICENOW_IMPACT"] = Read-Setting "SERVICENOW_IMPACT" "ServiceNow impact choice" "3" -Required
$settings["SERVICENOW_URGENCY"] = Read-Setting "SERVICENOW_URGENCY" "ServiceNow urgency choice" "3" -Required
$settings["SERVICENOW_RESOLVE_ON_CLOSE"] = Read-Setting "SERVICENOW_RESOLVE_ON_CLOSE" "Resolve PDI incident when NEXUS closes it (true/false)" "true" -Required
$settings["SERVICENOW_CLOSE_STATE"] = Read-Setting "SERVICENOW_CLOSE_STATE" "ServiceNow resolved/closed state choice" "6" -Required
$settings["SERVICENOW_CLOSE_CODE"] = Read-Setting "SERVICENOW_CLOSE_CODE" "ServiceNow close_code choice" "Solved (Permanently)" -Required
$settings["SERVICENOW_CLOSE_NOTES"] = Read-Setting "SERVICENOW_CLOSE_NOTES" "ServiceNow close_notes text" "NEXUS-RESOLVE closed after approved mock remediation, validation, and RCA." -Required

$order = @(
  "OPENAI_API_KEY",
  "OPENAI_MODEL",
  "APP_MODE",
  "OPENAI_INPUT_COST_PER_1M_USD",
  "OPENAI_OUTPUT_COST_PER_1M_USD",
  "HUMAN_HOURLY_RATE_USD",
  "HUMAN_BASELINE_MINUTES_PER_INCIDENT",
  "BACKEND_PORT",
  "FRONTEND_PORT",
  "SERVICENOW_INSTANCE_URL",
  "SERVICENOW_USERNAME",
  "SERVICENOW_PASSWORD",
  "SERVICENOW_TABLE",
  "SERVICENOW_CREATE_INCIDENTS",
  "SERVICENOW_UPDATE_INCIDENTS",
  "SERVICENOW_CALLER_ID",
  "SERVICENOW_ASSIGNMENT_GROUP",
  "SERVICENOW_CATEGORY",
  "SERVICENOW_IMPACT",
  "SERVICENOW_URGENCY",
  "SERVICENOW_RESOLVE_ON_CLOSE",
  "SERVICENOW_CLOSE_STATE",
  "SERVICENOW_CLOSE_CODE",
  "SERVICENOW_CLOSE_NOTES"
)

$lines = New-Object System.Collections.Generic.List[string]
foreach ($name in $order) {
  if (!$settings.Contains($name)) {
    continue
  }
  $lines.Add("$name=$(Format-EnvValue ([string]$settings[$name]))")
}
foreach ($entry in $settings.GetEnumerator()) {
  if ($order -notcontains $entry.Key) {
    $lines.Add("$($entry.Key)=$(Format-EnvValue ([string]$entry.Value))")
  }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($EnvFile, $lines, $utf8NoBom)

Write-Host ""
Write-Host "Saved live configuration to $EnvFile" -ForegroundColor Green
Write-Host "OpenAI key: set"
Write-Host "ServiceNow URL: $($settings["SERVICENOW_INSTANCE_URL"])"
Write-Host "Create incidents: true"
Write-Host "Update incidents: true"
Write-Host ""
Write-Host "Next:"
Write-Host "  scripts\live-servicenow-demo.cmd"
Write-Host "Or manually:"
Write-Host "  scripts\verify-live-servicenow.cmd"
Write-Host "  scripts\start-live-servicenow.cmd"
