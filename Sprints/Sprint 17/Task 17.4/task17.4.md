# Task 17.4 — Failure logging to `jobs` / usage

## Steps

- [x] Ensure recurring report failures call `mark_failed` on the `jobs` row
- [x] Record `job` usage event with `status=failed` meta on failure
- [x] Success path keeps `report_post` usage
- [x] Unit test for failure path + docs pointer

## Acceptance criteria

- [x] Failed report runs leave a failed `jobs` row (`kind=recurring_report`)
- [x] Failure is visible in usage events (`event_type=job`)
- [x] Success still records `report_post`
