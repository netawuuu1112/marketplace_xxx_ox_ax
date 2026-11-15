# Wildberries observed search implementation plan

**Goal:** Use live ordinary prices from the search JSON loaded by the WB page on the existing VPS.

**Architecture:** Observe only a successful same-origin search response matching query and page in an owned CDP tab. Retain public product fields and reuse existing kopeck normalization; DOM remains the fallback. Preserve failures and price evidence rules for all other sources.

- [x] Reproduce a live WB search JSON response on the VPS (100 products, HTTP 200).
- [x] Add failing tests for product-price semantics, conditional-price exclusion and invalid ids.
- [x] Implement bounded observation and existing normalizer integration.
- [ ] Verify tests and live public API after deployment.
- [ ] Record remaining all-source access blockers and synchronize project memory.

Additional verified defect: DNS's initial HTTP 401 browser-check page was closed too early. A bounded raw-CDP wait produced 24 real search results, but no prices. Added an opt-in DNS-only transport with completed-navigation checks and refusal preservation (3 tests); public deployment verification remains pending.
