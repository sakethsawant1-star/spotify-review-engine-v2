# Dashboard Correction Prompt

## Context
You are working on a Spotify AI Review Analytics Dashboard (Phase 5). The backend is FastAPI + PostgreSQL. The frontend is vanilla HTML/CSS/JS. The pipeline scrapes reviews from Reddit, Play Store, and App Store, cleans/deduplicates them, runs LLM analysis (Groq/Gemini), and stores results in Postgres. The frontend reads from `/api/dashboard/overview`, `/api/themes`, `/api/behavior-patterns`, `/api/quotes`, and `/api/summary`.

**Project goal:** This is Part 1 of a NextLeap PM Fellowship graduation project. An evaluator will click "Run Analytics Pipeline," watch it execute, then inspect the dashboard to judge whether the engine surfaces actionable, discovery-related insights about Spotify users. The evaluator grades on: clarity/depth of thought, data orientation, creativity, and presentation quality.

## Issues to Fix (Priority Order)

### P0 — Critical Data Issues

1. **"AVG SENTIMENT SCORE: 427%" on Overview.** This is broken. Sentiment should be a value between 0-100% or a 1-5 scale. Diagnose whether the API is returning a raw sum instead of an average. Fix the backend calculation in `app.py` (`/api/dashboard/overview`) or fix the frontend formatting in `dashboard.html`. The displayed value must make sense to an evaluator at a glance (e.g., "3.2 / 5" or "64% Positive").

2. **"THEMES DETECTED: 13" but only 7 are named.** The Theme Classification page shows 7 real themes (Algorithm Accuracy, Library Management, Ads & Premium Friction, Audio Quality & Playback, UI Navigation, Feature Discovery, Search Usability) and 6 cards labeled "Unknown." This looks unfinished. Fix the LLM prompt or the classification logic so that reviews currently bucketed as "Unknown" get reclassified into meaningful themes. If reclassification is too costly, merge the Unknown cards into an "Other / Miscellaneous" single card with a count, and update the Overview stat to show "7 Core Themes" instead of "13."

3. **"TOTAL REVIEWS ANALYZED: 33" on Overview but summary.md says 469.** The overview card shows 33 which contradicts the pipeline stats (5,421 scraped → 469 analyzed). Check if the overview query only counts the latest batch. If the DB has all 469, fix the query to reflect the full corpus. If the DB truly only has 33, document why (e.g., rate limits, demo run) but at minimum, make the number consistent across the dashboard and the summary doc.

### P1 — UX/Presentation Issues

4. **Quote Extraction page shows only 5 quotes, all tagged "Algorithm Accuracy," all from Reddit.** This looks like the query is filtering too aggressively or the pipeline only processed one batch. The evaluator expects to see quotes across multiple themes and sources. Fix the `/api/quotes` endpoint or the frontend to show quotes from at least 3 different themes and 2 different sources. If the data exists in the DB, it's a query/filter issue. If not, ensure the next pipeline run processes more diverse data.

5. **Behavior Patterns "30-DAY TREND" mini-charts.** These look like static placeholder graphics. If they are hardcoded SVGs or images, replace them with actual data-driven visuals (even simple CSS bar charts). If the data doesn't exist for real trends, remove the "30-DAY TREND" column entirely rather than showing fake data. Evaluators will check.

6. **Landing page "RUN ANALYTICS PIPELINE" button.** Per `summary.md`, the pipeline was moved to GitHub Actions. If clicking this button still tries to run the full scrape+analyze pipeline synchronously (which will time out on a deployed server), change the behavior: either (a) have it trigger the GitHub Action via API dispatch and show a "Pipeline triggered" toast, or (b) change the button to "VIEW DASHBOARD" which navigates to `/dashboard.html`, and add a small footnote: "Pipeline runs automatically via CI/CD." Do not leave a button that hangs or errors for the evaluator.

### P2 — Polish

7. **4-Class Sentiment donut chart on Overview shows only "32% Positive" label.** The donut itself should render all 4 segments (Positive, Mixed, Neutral, Negative) with their percentages. If the data exists, fix the chart rendering in `app.js`. If only the positive % is returned by the API, update the API to return all 4 classes.

8. **Executive Summary page ("Get Summary")** is solid but the "Voice of the User" section only shows 1 quote. Add 2-3 more representative quotes from different themes to make the summary feel comprehensive.

## Files to check
- `phase5-dashboard/app.py` — backend API
- `phase5-dashboard/frontend/app.js` — frontend logic
- `phase5-dashboard/frontend/dashboard.html` — overview page
- `phase5-dashboard/frontend/theme-classification.html`
- `phase5-dashboard/frontend/quote-extraction.html`
- `phase5-dashboard/frontend/behavior-patterns.html`
- `phase5-dashboard/frontend/summary.html`
- `phase5-dashboard/frontend/index.html` — landing page
- `phase3-pipeline/` — if theme classification needs prompt changes
- `phase4-agent/` — if LLM analysis prompts need updating

## Constraints
- Do NOT redesign the dashboard layout or color scheme. The Spotify-themed dark UI is good. Only fix data accuracy and completeness.
- Do NOT change the database schema. Work within the existing Postgres tables.
- Keep changes minimal and testable. Each fix should be independently verifiable.
