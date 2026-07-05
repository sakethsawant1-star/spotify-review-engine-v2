# Dashboard Correction Prompt

## Context
You are working on a Spotify AI Review Analytics Dashboard (Phase 5). The backend is FastAPI + PostgreSQL. The frontend is vanilla HTML/CSS/JS. The pipeline scrapes reviews from Reddit, Play Store, and App Store, cleans/deduplicates them, runs LLM analysis (Groq/Gemini), and stores results in Postgres. The frontend reads from `/api/dashboard/overview`, `/api/themes`, `/api/behavior-patterns`, `/api/quotes`, and `/api/summary`.

**Project goal:** This is Part 1 of a NextLeap PM Fellowship graduation project. An evaluator will inspect the dashboard to judge whether the engine surfaces actionable, discovery-related insights about Spotify users. The evaluator grades on: clarity/depth of thought, data orientation, creativity, and presentation quality.

## Issues to Fix (Priority Order)

### P0 — Critical Data Issues

1. **"THEMES DETECTED: 13" but only 7 are shown.** The Overview page shows 13 themes detected, but the Theme Classification page only renders 7 cards. The frontend logic (`app.js`) is intentionally filtering out 6 themes named "Unknown". Fix the LLM prompt or classification logic to properly categorize these reviews, or group them into a single "Other" category. Update the "THEMES DETECTED" count on the Overview to match the visible categories.

2. **"TOTAL REVIEWS ANALYZED: 33" vs 465+.** The Overview card shows 33, but summing the review volumes across themes yields 465, and `summary.md` says 469. Fix the API query (`/api/dashboard/overview`) or frontend calculation so the overview number accurately reflects the total pipeline corpus (e.g., 469).

### P1 — UX/Presentation Issues

3. **Quote Extraction lacks diversity.** The Quote Extraction page shows exactly 5 quotes, and they are all tagged "Algorithm Accuracy" from "reddit". The evaluator expects to see quotes across multiple themes and sources. Fix the `/api/quotes` endpoint or the frontend to show quotes from at least 3 different themes and 2 different sources.

4. **Behavior Patterns "30-DAY TREND" charts are missing.** The Behavior Patterns page has a column for "30-DAY TREND", but no actual charts or sparklines are rendered (even though CSS classes like `.bp-trend` exist). Either implement the data-driven trend visuals, or remove the "30-DAY TREND" column entirely rather than showing an empty/broken layout.

### P2 — Polish

5. **4-Class Sentiment Donut chart labels.** The Overview donut chart only displays "32% Positive" in the center. While the legend below it shows all 4 classes, ensure the donut segments themselves have tooltips or labels for the other classes (Mixed, Neutral, Negative) for better interactivity.

6. **Executive Summary has only 1 quote.** The "Voice of the User" section on the Summary page ("Get Summary") only displays one quote. Add 2-3 more representative quotes from different themes to make the summary feel comprehensive and data-backed.

## Files to check
- `phase5-dashboard/app.py` — backend API
- `phase5-dashboard/frontend/app.js` — frontend logic
- `phase5-dashboard/frontend/dashboard.html` — overview page
- `phase5-dashboard/frontend/theme-classification.html`
- `phase5-dashboard/frontend/quote-extraction.html`
- `phase5-dashboard/frontend/behavior-patterns.html`
- `phase5-dashboard/frontend/summary.html`
- `phase3-pipeline/` — if theme classification needs prompt changes
- `phase4-agent/` — if LLM analysis prompts need updating

## Constraints
- Do NOT redesign the dashboard layout or color scheme. The Spotify-themed dark UI is good. Only fix data accuracy and completeness.
- Do NOT change the mock pipeline. The pipeline button is a mock and should remain unchanged.
- Do NOT change the database schema. Work within the existing Postgres tables.
- Keep changes minimal and testable. Each fix should be independently verifiable.
