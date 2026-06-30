# Risk Register

| Risk | Impact | Mitigation |
| --- | --- | --- |
| OpenAI API unavailable | Live demo could stall | Deterministic fallback emits "OpenAI unavailable, using validated fallback response." |
| GitHub Pages deploy fails | Public replay unavailable | Dashboard builds as static Vite output; scenario catalog and replay JSONL are copied at build time. |
| Backend not running | Live mode unavailable | Replay mode is the default and needs no backend. |
| Safety concern | Judges worry about destructive automation | Mock-only execution, approval gate, protected-resource block, and dry-run review are visible. |
| Synthetic data concern | Scenario feels too artificial | Data includes 11 infra scenarios with SOP, history, unsafe precedent, escalation, and before/after state. |
| Secret exposure | API keys could leak in static site | `.env` is ignored; Pages mode never needs backend secrets. |
| Demo feels scripted | Judges may think the page is static | Dashboard shows a Live AI Proof strip, deep-dive labels trace replay, and live API cards fetch FastAPI JSON when the backend is online. |
| Audit credibility | Judges ask what would be attached to an incident | Backend exposes `GET /api/runs/{run_id}/audit-packet` with a SHA-256 hash, approval metadata, policy checks, events, RCA, and safety metadata. |
| Public replay cannot prove live OpenAI | Pages is static by design | Use Pages for safe replay and the local live demo for server-side OpenAI proof; never expose the API key to the browser. |
