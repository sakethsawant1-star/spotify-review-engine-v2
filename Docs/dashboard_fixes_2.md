# Dashboard Correction Prompt (Round 2)

## Context
You are working on the Spotify AI Review Analytics Dashboard. We need to do another round of iterations on the frontend (HTML/JS) and backend (FastAPI/Python) to polish the presentation of our data for the evaluator.

## Issues to Fix

### 1. Overview Page: "Total Reviews Analyzed" Funnel
Currently, the "Total Reviews Analyzed" card just shows a static/small number (e.g., 33). We want to show the true scale of the pipeline.
**Fix:** Change this card to display the data pipeline funnel. For example, it should visually convey: `5,421 Scraped > 469 Analyzed`. Below that, you can show the smaller batch number as `"33 new reviews added to analysis"`. Update the HTML structure of this KPI card and the backend API (`/api/dashboard/overview`) if necessary to pass these funnel numbers.

### 2. Overview Page: 4-Class Sentiment Pie Chart
The 4-class sentiment chart is still broken. It currently only shows a single "32% Positive" label in the center and does not render the actual pie/donut slices for Mixed, Neutral, and Negative.
**Fix:** Fix the chart rendering logic in `app.js` (using Chart.js or whatever library is currently in place). The pie chart must visually display all 4 sentiment classes as distinct slices, and hover states should work.

### 3. Theme Classification: Percentage Math Error
On the Theme Classification page, when hovering over the sentiment breakdown bars for a specific theme, the percentages for Positive + Negative + Mixed + Neutral do not add up to 100%. 
**Fix:** Fix the math logic in `app.js` or the backend API (`/api/themes`). Ensure that the sentiment distribution for each individual theme accurately sums to 100%.

### 4. Behavior Patterns: 30-Day Trend Charts
The "30-DAY TREND" mini-charts feel inaccurate and look like placeholders. 
**Fix:** Remove the fake sparkline charts entirely. Replace them with a clear, text-based infographic or badge that justifies the pattern (e.g., a pill badge showing `+12.4% MoM` in green or `-8.2%` in red) with a small up/down trend arrow indicator. Ensure the UI looks intentional and data-backed.

### 5. Quote Extraction: Lack of Theme Diversity
The Extracted Quotes Database is still only showing quotes from a single theme (e.g., "Algorithm Accuracy").
**Fix:** Update the backend query in `/api/quotes` and the frontend rendering. The quote database MUST pull and display quotes from a diverse set of themes, not just one. Ensure the table populates with a variety of theme tags.

### 6. Executive Summary ("Get Summary") Generation
The Executive Summary page needs to be much more comprehensive but presented in a concise, structured way. Currently, it only shows one quote under "The Voice of the User" and uses long, wordy paragraphs.
**Fix:** 
- Add logic to display **at least 3 diverse quotes** under the "Voice of the User" section.
- Expand the AI Executive Summary generation so that it explicitly references the *actual* metrics on the dashboard (total reviews analyzed, top themes, predominant sentiment, and critical behavior patterns).
- **Format:** The generated summary must be concise, structured, and bullet-pointed (given in brief) instead of long, dense paragraphs, so it is easy for an evaluator to scan.
- Ensure the text reads like a comprehensive overview of *every detail analyzed by the pipeline*.

## Constraints
- Keep the existing dark/Spotify UI theme.
- Ensure all numbers and math render correctly.
- Provide the exact code snippets needed to replace the broken parts in `app.js`, `app.py`, or the HTML files.
