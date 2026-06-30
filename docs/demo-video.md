# Demo Video Artifact

The local captioned demo video is generated at:

```text
media/nexus-resolve-demo.mp4
```

Current verified metadata:

- Duration: 270 seconds, or 4:30.
- Size: under 1 MB.
- Source visuals: verified local dashboard screenshots in `media/demo-assets/`.

It is 4 minutes and 30 seconds long and follows the required narration plan:

1. Repetitive P3-P5 ticket burden.
2. Scenario selector and synthetic infra alert trigger.
3. SOP and similar historical tickets.
4. Unsafe precedent detection.
5. Safe action remediation review.
6. Human approval gate.
7. Mock execution and scenario validation.
8. Live AI Proof strip showing OpenAI/fallback/replay source.
9. Deep-dive both-screen view with live API JSON and audit packet hash.
10. RCA, metrics, audit trail, and rubric alignment.

Regenerate after capturing fresh dashboard screenshots:

```powershell
.\scripts\create-demo-video.cmd
```

The generated video is intentionally local submission media, not runtime product
code. It uses synthetic screenshots only and contains no secrets.
