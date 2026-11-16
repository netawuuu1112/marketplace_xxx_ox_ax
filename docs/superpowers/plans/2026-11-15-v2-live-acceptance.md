# V2 live acceptance continuation

**Goal:** Replace fixture-only evidence with bounded real-source checks, fix reproducible integration defects and publish the verified result in PR9.
**Architecture:** Keep the existing connectors and V2 domain. Run diagnostics without installing V2 into production, modifying its database, sending vendor inquiries or starting a second Telegram poller.
**Constraints:** No new spending; no production deployment before separate owner permission; no invented prices, regions, delivery or success statuses. Preserve all services and secrets. Current spec: docs/MARKETFUSION_V2_REQUIREMENTS_RU.md.

- [x] Run bounded real V2 searches through the existing Russian VPS network in an isolated temporary Python module; record exact/related groups, prices and source failures, without production DB writes.
- [x] Inspect ordinary page/API responses and source-maintained GitHub code for missing region/delivery/price fields. Apply only fixes supported by actual response evidence, with failing regression tests first.
- [x] Test product-bound monitoring/history with current real observations in a separate local DB; distinguish a measured price from a simulated threshold event and from an actual Telegram delivery.
- [ ] Verify existing authorized AI/photo/review paths without new spending, and diagnose missing capability rather than asserting readiness from configuration.
- [x] Run appropriate regression, browser, staging and CI gates after changes; update source matrix, memory, release limits and PR.
- [ ] Perform full production acceptance/deployment only after source readiness and separate permission under specification section14.


Continuation evidence Nov16: five live local priced sources, sameMPN3sourcegroup, actualYMoscow watch/history, YM13reviews; optional privateagent and temporaryVPSUnixroute proven separately. No persistent route or production release. AI/visionmetadata+routing verified without paidgeneration; WBsuccessfulreview/AI/photo/Telegramrealalert remain open. Local gates117Python+6browser+builds+nonemptyrestore passed. Final code CI96a48a4/run43934832807: all four jobs passed; PR updated, verified source ZIP retained. Ownerconfirmedserverscurrentlyunavailable; stopVPSprobes. See current verificationreport for fiveblocked sources and fullacceptance gaps.
