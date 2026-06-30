# GitHub Publish Runbook

This project is ready to publish once GitHub authentication is available.

## Create Repository

The local repository already has an initial commit. Both
`codex/nexus-resolve-build` and `main` point at the build commit.

```powershell
cd "D:\Hackathon - API\NEXUS_RESOLVE_FINAL"
git checkout main
gh repo create nexus-resolve --public --source . --remote origin --push
```

If `gh` is unavailable, create a public repository named `nexus-resolve` in the
GitHub UI, then run:

```powershell
git remote add origin https://github.com/<your-user>/Project-Nexus_Resolve.git
git checkout main
git push -u origin main
```

## Configure Pages

1. Open the repository settings.
2. Go to Pages.
3. Set source to GitHub Actions.
4. Run the `Deploy GitHub Pages` workflow if it does not start automatically.
5. Copy the public Pages URL into `README.md`.

## Verify Public Replay

Open the Pages URL and confirm:

- The top bar shows `Replay Mode`.
- `INC-2026-00421` appears in Ticket Details.
- The scenario selector includes Linux, Firewall, Backup, Service Desk, AD,
  Command Centre, and Cloud alerts.
- `SOP beats history` appears.
- Approval buttons are disabled in Replay Mode.
- RCA and metrics appear after the timeline completes.

## Verify Local Live Proof

Before submitting the final video, run:

```powershell
cd "D:\Hackathon - API\NEXUS_RESOLVE_FINAL"
.\scripts\check-all.cmd
.\scripts\verify-live-openai.cmd
.\scripts\start-demo.cmd
```

Use `http://127.0.0.1:5174/apps/deep-dive/#both` to show the real dashboard
beside live API JSON and the hashed audit packet.
