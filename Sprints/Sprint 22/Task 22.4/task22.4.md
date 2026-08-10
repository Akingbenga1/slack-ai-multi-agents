# Task 22.4 — Optional second org smoke

## Steps

- [x] `POST /admin/tenants` — create tenant + org admin + billing + agent config (`PO-04`)
- [x] Admin `/admin/tenants` create form (optional local `activate_plan`)
- [x] Smoke: `scripts/second_org_smoke.py` + `api.app.demo.isolation.prove_no_knowledge_leak`
- [x] Pytest: provision + no knowledge leak; admin create API
- [x] Docs: admin-portal / demo-readiness / demo-script / README

## Acceptance criteria

- [x] Platform owner can create a second org via admin portal (API + UI)
- [x] Smoke proves admin list shows both tenants and Qdrant search does not leak across `client_id`
