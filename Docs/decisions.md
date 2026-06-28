# AI & Architectural Decisions Log

This document tracks key engineering, product, and design decisions made during the Spotify Music Discovery Review Engine project.

---

## 1. Product Context & Scope
* **Decision:** Focus on **Spotify** as the target platform for review analysis.
* **Rationale:** Spotify is the market leader with a massive volume of user feedback, and its discovery mechanisms (e.g., algorithmic playlists, search, recommendations) are central to the user experience.
* **Current Focus:** The immediate scope is limited to Part 1: building the **AI-powered Review Engine** to uncover user discovery pain points.

## 2. LLM Provider
* **Decision:** Use **Groq API** (specifically `llama3-70b-8192` and `mixtral-8x7b-32768`).
* **Rationale:** 
  * Strict zero-budget constraint.
  * Groq offers a generous free tier (30 requests/min, 14,400 requests/day).
  * Extremely fast inference speeds, which is highly beneficial for batch processing.

## 3. Database Architecture
* **Decision:** Use **SQLite** for relational storage and structured querying.
* **Rationale:**
  * Serverless, self-contained, and zero-cost setup.
  * Highly suited for local development and processing dataset sizes of ~5,000 reviews.
  * Allows robust SQL querying for generating quantitative reports.

## 4. Rejection of Vector Database (ChromaDB) for Review Engine
* **Decision:** Defer or reject the integration of **ChromaDB** for the Review Engine phase.
* **Rationale:** 
  * The current task is batch classification and taxonomy mapping (labeling sentiment and themes), which is best handled by prompting a structured LLM using relational storage.
  * A vector database is overkill for simple classification and adds unnecessary complexity.
  * Vector search / ChromaDB will be re-evaluated in Part 4 of the project if we build an interactive AI-Native search MVP.

## 5. User Segmentation Strategy
* **Decision:** Adopt a **use-case driven segmentation** (based on music discovery behavior and frustrations) rather than traditional demographic segmentation (age, gender).
* **Rationale:** Music discovery habits, platform fatigue, and curation needs are behavior-driven, crossing age and geographic boundaries.

## 6. Sentiment Taxonomy
* **Decision:** Utilize a 4-class classification system: **Positive**, **Neutral**, **Negative**, and **Frustrated**.
* **Rationale:** Isolating "Frustrated" as a distinct class allows us to flag high-risk churn signals and specific UX friction points that generic "Negative" labels might obscure.

## 7. Theme/Topic Taxonomy
* **Decision:** Limit classifications to **≤ 7 controlled themes** (T1: Algorithm Accuracy, T2: Search Usability, T3: Library Management, T4: Feature Discovery, T5: UI Navigation, T6: Audio Quality & Playback, T7: Ads & Premium Friction).
* **Rationale:** Restricting the taxonomy avoids LLM cognitive overload, prevents classification drift, and ensures clean quantitative aggregation in reports.

## 8. Directory & Phase Structure
* **Decision:** Organize the codebase into discrete, phase-specific folders (e.g., `phase1-setup/`, `phase2-data-pipeline/`).
* **Rationale:** Keeps the codebase clean, modular, and directly aligned with the approved implementation plan.

## 9. Sequence of User Research
* **Decision:** Choose the primary user segment *after* analyzing reviews with the AI Engine.
* **Rationale:** Review engine data will point out where the highest concentration of user friction lies, allowing user surveys and interviews to target the right segment with maximum precision.

## 10. Reddit Data Source — RSS Feed Fallback
* **Decision:** Use Reddit's public **RSS/Atom feeds** instead of the JSON API or PRAW.
* **Rationale:**
  * Reddit's public JSON endpoints (`.json`) now return HTTP 403 for all subreddits — even without authentication. This is part of Reddit's 2023 API policy change.
  * Reddit's formal API access now requires submitting a review request (approval can take days).
  * RSS feeds (`/r/subreddit.rss`) remain publicly accessible (HTTP 200 confirmed).
  * RSS provides sufficient data (post title + body text) for our discovery keyword filtering and LLM classification.
  * Reddit data is a secondary/supplementary source (~500–1,000 items). Play Store and App Store are the primary sources.

