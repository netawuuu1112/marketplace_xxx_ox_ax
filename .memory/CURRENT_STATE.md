# Current state — 2026-11-14

- HTTPS site and core Docker services answer; API sees a private Chromium CDP container.
- Public authenticated search for `ssd` returned five offers from Yandex Market with five ordinary prices and five Wildberries cards with zero ordinary prices. Other eight comparison sources failed or timed out on this VPS. Details: `docs/MVP_SOURCE_STATUS_RU.md`.
- Browser route has been deployed on the VPS. Frontend now shows incomplete price coverage when a source provides cards without ordinary prices; frontend redeployment is pending.
- Existing search, favorites and bot start have passed previous live checks, but full end-to-end review, photo search, monitoring, price alerts and admin workflows are not verified across all sources.
- Full all-source MVP is blocked by external access and data-rights constraints under the current no-spend/no-contact requirement. Do not substitute conditional prices or fabricate offers.

Next: deploy and verify frontend warning, investigate WB card price, validate each remaining user workflow and record exact blockers.
