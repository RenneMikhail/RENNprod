# Dashboard QA — 26.10.2026

Applied only in docs/crm and src/crm-prototype. No backend, secret, runtime DB, commit or push changes.

## Implemented

Three widgets: available employees, new tasks, active projects. Drilldown is tables only; city filter, search and sorting. Employees have the 8 requested role codes, Russian labels, demo availability switch, separate approval and add permissions. Tasks support new/working/archive, per-task approval tasks:approve, clickable client completed-work history. Project adapter uses existing order objects and opens the old card. Missing order cities remain "Не указан" rather than invented values.

Public mode has separate localStorage namespace renn-dashboard-demo-v1. Demo owner delegates each permission separately to selected manager Anna or Ilya; neither manager has permissions initially. Employee role receives access denied. Demo roles are explicitly simulation, not security or authentication.

Source uses /api/me with same-origin cookie credentials and X-Local-Session when injected. Only owner/manager are admitted and permissions come solely from the returned permissions array. No browser role fallback. If /api/me fails or format is unknown, dashboard remains closed. Live employees adapt RPRegistry in memory with source labels and unknown availability. Browser controls never update live verification/availability or backend records. New source employees are labelled local drafts, tasks remain unconnected instead of silently mixing demo tasks.

Source dashboard.js/dashboard.css are canonical modules also bundled at the end of existing app.js/style.css, so the existing server asset whitelist continues working without backend edits. Source HTML loads only the existing bundled assets. Public HTML loads standalone dashboard assets; shared theme/mobile remain last. Source modules and bundles must be updated together when editing later.

## Actual browser verification

- 390px: employee table, Kazan filter and availability toggle work. Page scrollWidth equals viewport; only table wrapper scrolls horizontally.
- Default manager employees:add disabled and tasks:approve disabled.
- Owner delegates only tasks:approve to Anna: Anna approval becomes enabled; task can be approved. Ilya still cannot approve another task.
- Click client → completed demo interview history with city/date/status.
- Existing project opens previous order dialog.
- Employee role → access denied, dashboard widgets and sidebar nav hidden.
- Added demo CG employee with literal <b> in name; text is escaped, persists after reload, and city filter selects it.
- Widths 320/375/390/430/768: document scrollWidth exactly matches viewport. Table wrapper widths 290/333/348/388/726, table scrollWidth 700/700/700/700/726. Form computed font 16px at every width.
- Public demo reset to defaults after tests.
- Source served independently without /api/me: 404 causes access denied with no demo-role selector or fallback.
- JavaScript syntax checked. Static public JS/HTML scan: no fetch(), /api/, X-Local, SESSION, localhost or 127.0.0.1.

## Limits

Actual cookie-login owner/manager response from the concurrently developed backend has not been tested here. Source employee mutations and tasks API are not implemented in this UI; no successful server mutation claimed. Permission delegation is public demo-only until backend delegation endpoint is available. Source active orders still demo. Table touch scrolling checked through responsive DOM dimensions, not on physical phone. New dashboard is Russian; existing RU/EN legacy dictionary does not fully translate new dashboard. No production-security claim.

OLMO was queried for one bounded permission function draft. Its answer incorrectly required owner AND a manager grant, so none of that generated code was accepted.
