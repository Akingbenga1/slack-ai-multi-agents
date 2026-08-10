# Task 24.4 — File-grounded workflow advice

Stories: `TM-22`, `TM-23` · Journey: `J11` · Label: `deferred:shared-workflow-library`

## Steps

- [x] Add `workflow_advise` intent + route classification (beats generic `file_analyse` / `qa`)
- [x] Resolve evidence from attachment and/or stored template (`client_id` fail-closed)
- [x] Compose actionable guidance grounded in file (+ optional RAG); no generic hedge when file evidence exists
- [x] Escalate advice workflow to Sonnet
- [x] MCP tools: `get_workflow_template` + `advise_workflow` (required `client_id`)
- [x] Wire Slack path to enrich evidence before agent compose
- [x] Light tests + docs

## Acceptance criteria

- [x] Advice asks classify to `workflow_advise`
- [x] Guidance uses attached/stored template text when present (not empty hedge)
- [x] Cross-tenant template fetch fail-closed
- [x] MCP tools require `client_id`
