# Drive brief implementation — 2026-10-27

Read the full record-17.txt. Changed only docs/shooting and src/shooting-landing in this pass; no root hub, brand assets, backend, runtime, commit or push edits. Previous RU/EN and form behavior retained.

## Delivered
Seven separate pages: professional.html, reels.html, commercial.html, art.html, editing.html, graphics.html, ai.html. Home now contains short bulleted service cards, one short promise, visual people/equipment/process → diamond workflow, pointer/touch-following camera eye, case carousel, backstage, authorized client wordmarks, and friendly CTA. Internal CRM/team links and the direction-selection CTA removed. RU/EN is small on the right. Logo caption is Independent production / Russia and CIS on separate lines.

Professional filming from RUB 40,000; Reels from RUB 20,000. Reels detail retains 8h simple filming + simple editing of 5 videos, scripts + RUB 10,000, complex work separately quoted. No international prices invented.

Parent supplied four actual archive videos and JPG posters from the previous site. Connected via services.js manifest. No video element or MP4 download is created on initial landing render; image posters only. Clicking creates a controls-enabled video in a large viewport dialog, preload none, no autoplay. Native video fullscreen control remains available. Closing removes the video. Videos checked by ffprobe: 8.043s, 5s, 1.707s, 9.6s. Browser opened the first video and exposed native playback controls; full playback/visual content of all four is not claimed. Backstage assets are null in manifest and clearly marked as awaiting material. No random films used.

Client names supplied by the user: Т-Банк, Яндекс, System108, Сбер, Вкусно и точка. Plain wordmarks, no invented case attribution.

## Checks
- Home at 320/375/390/430/768: scrollWidth equals viewport, seven cards, no unresolved keys. Visually inspected 390px hero/workflow/camera.
- All seven English service pages at 320px: no overflow, translated H1, input font 16px.
- Language preserved across EN home → CG page.
- Public CG demo save/restore/clear passes and restores service graphics; test draft cleared.
- Carousel opens supplied video, closing works. Backstage modal honestly states missing media.
- JS syntax, every RU/EN template key and every linked local asset checked.
- Public runtime has no owner API/session/fetch code. Source retains local fetch /api/intake and seven IDs align with current source backend. No real DB writes performed in this pass.

## Integration notes / limits
Loaded assets: styles.css, locales.js, services.js, app.js, site.js. Parent confirmed the backend whitelist includes all seven pages, JS and JPG/MP4 media. integration-status.json records the exact page names and asset request. Source includes base /shooting/ so both /shooting and /shooting/ resolve page/media links correctly. The source backend is not restarted here and its complete whitelist behavior is not verified live.

Removed unused duplicates site.css, cg.html, experience.js, media-manifest.js after verifying no HTML references. Current HTML selects the files above. Real touch hardware/keyboard, reduced-motion preference in a live browser, iframe hosting and a full accessibility audit not tested. Touch/pointer listeners are passive; reduced-motion disables eye/camera movement in CSS and JS.

Local Qwen bounded request failed with URLError; no local-model output used.
