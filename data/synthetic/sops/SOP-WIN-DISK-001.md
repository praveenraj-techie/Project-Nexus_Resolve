# SOP-WIN-DISK-001: Windows Application Log Disk Remediation

## Scope
Synthetic Windows application servers where a non-critical disk alert reports
high utilization on the `C:` drive.

## Required Controls
1. Delete only application logs older than 7 days.
2. Never touch `C:\Windows`, `C:\Program Files`, user profiles, or active logs.
3. Estimate reclaimed space before action.
4. Require human approval before remediation.
5. Validate free space after remediation.
6. Escalate if free space remains below 15%.

## Approved Candidate Path
- `C:\App\Logs`

## Protected Paths
- `C:\Windows`
- `C:\Windows\System32`
- `C:\Program Files`
- `C:\Users`

## Safe Command Pattern
Use mock-only execution in this demo. A production candidate command must include
an age filter and a dry-run guard such as `-WhatIf` before any approval package
is presented.

```powershell
Get-ChildItem 'C:\App\Logs' -File -Recurse |
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-7) } |
  Remove-Item -WhatIf
```

## Validation
After mock execution, compare before and after free space. If free space is below
15% of capacity, escalate to infrastructure operations.

