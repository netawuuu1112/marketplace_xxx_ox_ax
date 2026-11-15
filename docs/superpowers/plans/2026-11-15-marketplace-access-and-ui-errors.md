# Marketplace access and UI errors implementation plan

**Goal:** Make failed source searches actionable and keep Mini App screens usable when external APIs fail.

**Architecture:** Keep the existing connector and price evidence rules. Add client-side links to the official search pages for each queried source, and display API failures on the review and comparison screens. These links are a navigation fallback, not a source of automatic price data.

- [x] Verify source URL shapes from existing connectors and current live source outcomes.
- [x] Add encoded official search links for failed or unpriced sources.
- [x] Fix asynchronous loading and error states in review and comparison screens.
- [x] Build the frontend and check links, HTTPS, API health, and deployed bundle on the VPS.
- [x] Update source status, project memory, commit, and deploy.
