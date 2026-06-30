# NEXUS-RESOLVE

Policy-grounded AI remediation for synthetic enterprise infrastructure operations.

NEXUS-RESOLVE resolves synthetic HCL-style managed-infrastructure alerts by
retrieving a governing SOP, comparing historical tickets, rejecting unsafe
precedent, generating an approval-gated mock remediation plan, executing only
synthetic state changes, validating the result, and producing RCA plus audit
evidence.

## Modes

- Replay Mode: static dashboard flow for GitHub Pages. No backend or secrets.
- Local Live Mode: FastAPI backend, WebSocket timeline, Local ITSM Twin, and
  optional OpenAI Responses API tool-calling loop when `OPENAI_API_KEY` is
  present.
- Mock fallback: deterministic golden response if OpenAI is unavailable.

## Quick Start

Copy `.env.example` to `.env` only for local live mode. Do not commit `.env`.

Recommended one-command launcher for judges:

```bat
start_demo.bat
```

Download the ZIP, right-click it, choose **Extract All**, then run
`start_demo.bat` from the extracted folder. Do not run the batch file directly
from inside the compressed ZIP view.

On a fresh ZIP download, this launcher now performs first-run setup
automatically. It creates the backend virtual environment and installs the
dashboard packages before it runs checks or opens demo tabs.

Double-clicking `start_demo.bat` opens a persistent Command Prompt window, so
startup errors stay visible instead of closing immediately. If you run it from
an already-open terminal and do not want a second window, use:

```bat
set NEXUS_DEMO_STAY_OPEN=1
start_demo.bat
```

It prompts for one of three paths:

1. Offline demo with local/demo SNOW only.
2. OpenAI API online proof with demo SNOW/local judge tabs.
3. OpenAI plus production ServiceNow/PDI ITSM integration.

For OpenAI modes, choose either the built-in/default key if one is configured
locally or paste your own key for that run. The GitHub copy does not include a
real API key.

One-command local setup and checks:

```powershell
.\scripts\setup-all.cmd
.\scripts\check-all.cmd
```

Advanced direct safe demo launcher:

```powershell
.\scripts\start-demo.cmd
```

It forces `APP_MODE=mock` for the no-ServiceNow judge demo, reuses existing
listeners on ports 8000, 5173, 5174, and 5177 only when they expose the current
API/pages, starts missing services, checks health, and prints the dashboard,
Local SNOW, and deep-dive URLs. Prefer the top-level `start_demo.bat` unless you
specifically want this lower-level mock-only script.

Real ServiceNow PDI live launcher:

One-command setup, preflight, and start:

```powershell
.\scripts\live-servicenow-demo.cmd
```

Manual three-step path:

```powershell
.\scripts\configure-live-servicenow.cmd
.\scripts\verify-live-servicenow.cmd
.\scripts\start-live-servicenow.cmd
```

The configure command is interactive and writes only to local `.env`, which is
ignored by git. It keeps an existing OpenAI key if one is already present. The
verify command creates a real PDI incident, appends a work note, and looks it
up by incident number so you can confirm ServiceNow create/update/read
permission before judging. `start-live-servicenow.cmd` also offers guided setup
when required `.env` values are missing. Set or confirm these values in `.env`
for the real PDI path:

```text
OPENAI_API_KEY=your_openai_project_key
OPENAI_MODEL=gpt-5.5
APP_MODE=live
SERVICENOW_INSTANCE_URL=https://your-dev-instance.service-now.com
SERVICENOW_USERNAME=your_pdi_username
SERVICENOW_PASSWORD=your_pdi_password
SERVICENOW_TABLE=incident
SERVICENOW_CREATE_INCIDENTS=true
SERVICENOW_UPDATE_INCIDENTS=true
SERVICENOW_RESOLVE_ON_CLOSE=true
```

Backend:

```powershell
cd services\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

Dashboard:

```powershell
cd apps\dashboard
npm install
npm run test
npm run build
npm run dev
```

Open `http://localhost:5173` for the operations console.

Open `http://127.0.0.1:5177/apps/local-snow/` for the local ServiceNow-style
ITSM desk. It mirrors the latest active NEXUS run in real time, including
Incident, Problem, RITM, Change, CI/site context, work notes, activity, and
manual communication approvals. It is synthetic-only and does not need a PDI.

Open `http://127.0.0.1:5174/apps/deep-dive/#both` for the judge console. It
embeds the real dashboard and shows live FastAPI JSON when the backend is
running, with labeled trace replay as the safe fallback.

Live OpenAI smoke test after setting a real key:

```powershell
.\scripts\verify-live-openai.cmd
```

Live ServiceNow PDI smoke test after setting PDI credentials:

```powershell
.\scripts\verify-live-servicenow.cmd
```

This creates a real PDI preflight incident, appends a work note, and verifies
the same record can be looked up later by its real incident number.

Headless full workflow proof after setting OpenAI and PDI credentials:

```powershell
.\scripts\verify-live-servicenow-run.cmd
```

This starts a real NEXUS live run, creates one real PDI incident, approves and
closes the mock-only workflow, writes milestone work notes to that same PDI
record, and verifies the incident can still be looked up by number.

One-command live ServiceNow demo:

```powershell
.\scripts\live-servicenow-demo.cmd
```

The live ServiceNow launcher restarts the backend before opening the dashboard
so the current `.env` values are loaded by FastAPI.

## Architecture

The orchestrator owns the workflow state. OpenAI is used for a Responses API
tool-calling loop that can request the local SOP, history, state, and policy
preview tools before returning structured evidence and remediation outputs. The
backend still owns policy, approval, mock execution, validation, and audit
events. Structured outputs cover evidence summary, remediation plan, approval
summary, and RCA. Approval records include demo operator metadata, and the
backend can return a hashed audit packet plus a downloadable PDF audit report
for any active run. AI telemetry records source, model, tokens when returned by
the API, local tool-call count, latency, configurable cost estimates, and a
$30/hour human comparison. A ServiceNow-style mock connector endpoint exposes
the synthetic ticket shape a real ITSM adapter would use. In local live mode,
the ServiceNow PDI adapter can create a real PDI incident for the selected
synthetic alert and append work notes to that same incident as evidence,
approval, execution, validation, RCA, and closure milestones advance. See
`docs/architecture.md` for the diagram and data flow.

For the no-PDI judge demo, the backend also creates a Local ITSM Twin for every
live run. The twin opens a synthetic Incident, drafts a linked Problem, RITM,
and Change, and prepares approval-gated Teams bridge, ISINFO email, IVR,
stakeholder update, and closure communication drafts. Each outbound draft must
be manually approved or rejected in the dashboard and is delivered only inside
the simulator, with external side effects disabled. The separate Local SNOW
desk consumes the same backend state and WebSocket events, so every workflow
milestone is reflected as a local work note and activity update without a real
ServiceNow account.

## Demo Flow

The dashboard supports these replay/live scenarios:

- Windows Infra: disk utilization high.
- Database: DB connection pool saturation.
- Security / IAM: suspicious admin role assignment.
- Network: VPN tunnel packet loss.
- Linux: high CPU / load average.
- Firewall: rule blocking application traffic.
- Backup: critical server backup failed.
- Service Desk: repeated account lockout.
- AD: Group Policy not applying.
- Command Centre: alert storm / duplicate alerts.
- Endpoint Security: third-party application exception rejection path.
- Cloud: VM failed health/status check.

The first screen is an operations alert dashboard. Selecting an alert opens an
incident workspace with ticket details at the top and a nearby Start Simulation
control. Each scenario then follows the same workflow: receive alert, retrieve
SOP, compare history, flag unsafe precedent, generate an action review package,
pause for human approval, execute mock remediation, validate metrics, generate
RCA, and ask the operator to close the incident or keep it under observation
before closure.

During the live flow, the ITSM Twin Command Center shows the synthetic
Incident/Problem/RITM/Change chain and the manual communications queue. The
Local SNOW desk shows the same data as a ServiceNow-style operator form with
work notes, CI/site details, related records, NEXUS activity, and approval
buttons. This is the no-PDI ServiceNow-style demo path: open both pages, start
or select the active run, approve a Teams bridge or ISINFO draft for a P1/P2
scenario to show a simulated send, then approve remediation and continue to
RCA, audit PDF, and closure.

The dashboard also includes a dedicated executive impact dashboard. It compares
all catalog incidents against a 45-minute human baseline at $30/hour, shows
portfolio MTTR saved, manual steps avoided, audit completeness, and live run
OpenAI telemetry when available.

## Safety Model

This demo never executes real host remediation. It blocks protected resources,
requires a dry-run or mock-only guard, pauses for human approval, uses mock-only
state mutation, validates scenario-specific recovery metrics, requires manual
approval for outbound communications, and requires an explicit closure decision
after RCA.

## OpenAI Usage

Runtime reasoning is wrapped in `services/backend/app/openai_client.py` and uses
the Responses API path when a key is configured. Evidence and plan generation
run through an app-owned local tool loop before structured outputs are parsed.
The default model is configurable with `OPENAI_MODEL` and defaults to
`gpt-5.5`. The app falls back to validated synthetic outputs if the API is
unavailable during a demo.

Cost telemetry uses `OPENAI_INPUT_COST_PER_1M_USD` and
`OPENAI_OUTPUT_COST_PER_1M_USD` from `.env`, with demo defaults in
`.env.example`. Keep these server-side; never expose the API key in frontend
code.

## ServiceNow PDI Integration

The live backend exposes `GET /api/connectors/servicenow/status` and
`POST /api/runs/{run_id}/servicenow/work-note`. At run start, the orchestrator
creates one ServiceNow PDI incident when the live connector is ready. With
`APP_MODE=live`, PDI credentials, and both
`SERVICENOW_CREATE_INCIDENTS=true` and `SERVICENOW_UPDATE_INCIDENTS=true`, each
local live run creates a real incident and writes milestone work notes to that
same record. Without those settings, or if the PDI Table API create call fails,
`APP_MODE=live` refuses to start the run instead of silently falling back to
synthetic ticket-only behavior. Mock/test mode still uses no-op metadata so
tests, replay, and the Local ITSM Twin remain side-effect free.
Created PDI incidents are also stored in local history and shown in the
dashboard's ServiceNow PDI History panel so the real incident number remains
visible after later live runs. If `SERVICENOW_RESOLVE_ON_CLOSE=true`, the final
NEXUS closure also sends ServiceNow `state`, `close_code`, and `close_notes`
fields with the closing work note. The history panel can also verify a stored
incident number against the live PDI by calling the ServiceNow Table API. The
Audit Export panel can preview the final work note or write it to the attached
live incident. Host remediation remains mock-only.

## Codex Usage

Codex is used as the builder, reviewer, debugger, and test-hardening assistant.
It is not used as a runtime API inside the product.

## Tests

Backend:

```powershell
cd services\backend
.\.venv\Scripts\python -m pytest
```

Dashboard:

```powershell
cd apps\dashboard
npm run lint
npm run test
npm run build
npm run e2e
```

The browser E2E suite can also be run from the repo root:

```powershell
.\scripts\run-e2e.cmd
```

Coverage includes all 12 catalog scenarios, golden approval flow, observation
and closure flow, rejection safety, Local ITSM Twin record creation, manual
communication approval before simulated send, unsafe action blocks,
protected-resource blocks, audit packet hashing, ServiceNow dry-run work-note
preview, live PDI incident create/update adapter tests, persistent ServiceNow
incident history, OpenAI tool-call telemetry capture, event sequencing, replay
endpoints, scenario selector rendering, proof-strip rendering, PDF audit
export, security exception rejection replay, deep-dive rendering, and
first-screen console rendering.

## GitHub Pages

The dashboard build copies `data/scenarios/catalog.json` and every
`data/replay/*.events.jsonl` file into Vite's public folder at build time.
GitHub Actions publishes `apps/dashboard/dist`, so the public page can run
Replay Mode without a backend or OpenAI key.

Public replay: `https://praveenraj-techie.github.io/nexus-resolve/`

Public replay intentionally does not prove a live OpenAI call. For judging,
show the local live dashboard/deep-dive flow after setting `OPENAI_API_KEY` in
`.env`; the UI labels OpenAI, fallback, and replay evidence separately.

Publish steps are in `docs/publish-runbook.md`.

## Demo Video

A local 4:30 captioned demo artifact is available at
`media/nexus-resolve-demo.mp4`. It uses verified dashboard screenshots and
follows the narration in `docs/demo-script.md`.

## Roadmap

- Intune or WinRM execution connector with change windows.
- Change-management approval integration.
- SIEM audit export.
- Hosted live mode with server-side secret storage and rate limits.
- Real hosted connector path for SOP, history, policy, validation, and ticket
  update tools.
- Additional SOP packs for certificate expiry, DFS replication, and storage
  failover triage.
- Evaluation harness for policy violation prompts and regression replay.

## Project Layout

```text
data/                  Synthetic scenario catalog, SOPs, history, replay streams
services/backend/      FastAPI workflow, policy gates, tests
apps/dashboard/        React operations console
docs/                  Architecture, scoring map, demo script, risks
.github/workflows/     CI and GitHub Pages deployment
```
