# Hackathon Scoring Map

## Innovation

NEXUS-RESOLVE is not a chatbot. It is an operations console where AI reasoning
is constrained by SOP retrieval, unsafe precedent detection, policy gates,
approval, mock execution, validation, and audit evidence.

## Impact

The target problem is repetitive P3-P5 remediation work. The demo shows manual
steps avoided, estimated MTTR reduction, and audit completeness.

## HCLTech Relevance

The scenarios map to enterprise managed operations across Windows Infra,
Database, IAM, Network, Linux, Firewall, Backup, Service Desk, AD, Command
Centre, and Cloud teams: alerts, SOPs, incident history, change approval, safe
execution, validation, and RCA.

## OpenAI Capabilities

- Responses API for application-owned runtime reasoning.
- Function-calling loop over safe local SOP, history, state, and policy tools.
- Structured output wrapper for remediation plans and RCA.
- Configurable `gpt-5.5` default model.
- Deterministic fallback for resilient demos.
- Visible proof strip that distinguishes OpenAI, deterministic fallback, and
  replay/static evidence.

## Technical Excellence

- FastAPI backend with tests.
- React/Vite dashboard with replay and live modes.
- WebSocket event stream with ordered audit events.
- Explicit policy module and protected-resource tests.
- No secrets or real enterprise data.
- Identity-aware approval metadata.
- Hashed audit packet endpoint for active runs.
- ServiceNow-style mock connector contract for synthetic incidents.
- Optional ServiceNow PDI incident create and milestone work-note write-back for
  live judge demos, with a command-line preflight that creates, updates, and
  looks up a real PDI incident, optional closure-state update, one-command live
  launcher, dashboard history for created PDI numbers, and live PDI lookup by
  incident number. A headless verifier can run the actual live workflow and
  confirm the created PDI incident after milestone updates.
- Judge deep-dive page with live API JSON when the backend is online.

## Scalability

The roadmap extends the pattern to broader ServiceNow ticket updates, change
management approval, SIEM export, additional remediation playbooks, and
Intune/WinRM execution connectors behind production change windows. Real host
execution remains intentionally outside the hackathon demo.
