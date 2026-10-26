# Shooting mobile integration — 2026-10-26

Scope: only src/shooting-landing and docs/shooting in branch mobile-integration. No commit, push, publication, root page or backend edits in this pass.

## Verified
- JS syntax: both app.js and locale dictionaries pass node --check.
- Browser viewport widths 320, 375, 390, 430, 768: document width equals viewport, cards do not overlap. Repeated after shared theme files appeared.
- Text controls computed 16px at every tested width; touch controls have 44px minimum height.
- At 320 × 640 dialog bounds x=12..308, y=12..628. At 320 × 360: y=12..348, internal content scrolls (787px). This tests reduced viewport height, not a real phone keyboard.
- RU demo save gives exact message: Демо: сохранено только на этом устройстве; команде не отправлено.
- Reopen and restore recovers the TEST description. Clear removes draft and resets form. EN save/clear also passed. Test drafts cleared.
- RU/EN switch resolves every visible text key; English layout at 375 has no horizontal overflow.
- Public runtime assets contain no owner API requests, loopback URLs, session placeholder/header or fetch call. Storage key renn-prod-shooting-demo-v1; no personal data should be entered.
- Source retains its existing real local intake transport. Backend regression was not re-run against this checkout; this pass changes its layout/brand only.
- Public head loads ../shared/theme.css and ../shared/mobile.css last. Home/team/CRM navigation uses ../, ../team/, ../crm/.
- Brand updated to RENN Prod. RUB offer unchanged; no invented clients or international prices.

## Limits
Native mobile keyboard, actual iOS/Android devices and screen-reader interaction not tested. Reduced-motion/focus rules retained; no full accessibility audit. localStorage is browser/device-specific and can be unavailable or cleared by the browser. ES/FR absent.

OLMO: bounded request attempted; local endpoint returned URLError. No OLMO-generated code was used.
