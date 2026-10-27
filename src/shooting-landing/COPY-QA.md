# Copy and hierarchy pass — 2026-10-26

Changed only docs/index.html, docs/shooting and src/shooting-landing. Existing logo/brand asset, shared files, team, CRM, backend, database and original runtime untouched. No commit or push.

Applied: role hub with Client → shooting/, Manager → crm/, Employee → team/?view=employee, separate recruitment → team/?view=join. Hub has RU/EN. Shooting copy shortened in both locales, decorative technical captions and repeated professional heading removed. Body and service descriptions 16px; leads 18px. Four services and original RUB package retained (20k, 8h simple filming, 5 simple edits; scripts +10k). Demo notice shortened, local-only/no-send meaning preserved.

Browser QA: hub and shooting at 320/375/390/430/768px — scrollWidth equals viewport. Computed body 16px, lead 18px; shooting card descriptions 16px. Hub EN switch and client link tested. Public shooting RU save/restore/clear and EN save/clear passed; test drafts cleared. No unresolved translation keys. JS syntax checks pass for source/public scripts and inline hub script. Public runtime scan found no local API/session/fetch code. Backend transport in src was not modified; real intake not re-tested in this pass. Native mobile keyboard not tested.

OLMO request attempted; local endpoint unavailable (URLError); no local-model output used.
