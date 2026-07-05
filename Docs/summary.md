# Project Summary: AI-Powered Review Discovery Engine (Spotify Analytics)

## 📌 Where We Stand Right Now
The core Review Analytics Engine has been successfully built, integrated, and polished. The system is fully capable of scraping user reviews from multiple platforms, processing them to remove PII, analyzing the text using LLMs (Gemini/Groq) for sentiment and theme classification, and presenting the insights on a highly responsive, modern web dashboard.

The pipeline data is now properly centralized in a **PostgreSQL** database, and the frontend is connected and actively pulling real data instead of static placeholders.

---

## 🏗️ What We Built (Phase by Phase)

1. **Phase 1: Setup & Configuration**
   - Initialized the modular project architecture.
   - Set up `config.py` and environment variable management for API keys (Gemini, Groq, Postgres).
   - Designed the database schemas for raw reviews, processed reviews, and AI-generated insights.

2. **Phase 2: Data Scraping**
   - Built scrapers (`reddit_scraper.py`, etc.) to automatically fetch user feedback from various platforms (Reddit, App Store, Play Store) based on Spotify-related keywords.

3. **Phase 3: Data Pipeline (Cleaning & Filtering)**
   - Developed `cleaner.py` and `pii_remover.py` to sanitize the data, ensuring user privacy and high-quality text for the AI.
   - Built `relevance_filter.py` to discard spam or unrelated reviews.

4. **Phase 4: AI Analysis Agent**
   - Implemented `gemini_agent.py` and `analyzer.py` to process the clean reviews.
   - Used detailed prompting strategies (`synthesis_prompt.txt`, `quote_prompt.txt`) to classify themes (e.g., Algorithm Accuracy, UI Navigation) and extract compelling user quotes.
   - Implemented batching and rate-limit handling for reliable API communication.

5. **Phase 5: Frontend Dashboard**
   - Built a sleek, Spotify-themed interactive UI using HTML, CSS (with Light/Dark modes), and Vanilla JS (`app.js`).
   - Created specialized views: **Overview Dashboard**, **Theme Classification**, **Behavior Patterns**, and **Quote Extraction Database**.

6. **Phase 6: Deployment & Automation**
   - Migrated from local SQLite to a production-ready **PostgreSQL** database via `migrate_to_postgres.py`.
   - Wrote deployment configuration files (`railway.toml`, `render.yaml`).
   - Offloaded the heavy scraping and LLM pipeline to **GitHub Actions**, which runs on a schedule to continually feed the PostgreSQL database.

---

## 📊 By The Numbers (Data Pipeline Execution)

During our most recent end-to-end automated pipeline run, the system processed the following data points:

- **Total Raw Reviews Scraped:** `5,421` reviews
- **Relevance Drop Rate:** `91.3%` (Filtering out spam, single-word reviews, and unactionable noise).
- **High-Quality Processed Reviews:** `469` highly relevant reviews forwarded to the AI.
- **PII Items Redacted:** `484` instances of Personal Identifiable Information removed for user privacy.
- **Source Breakdown (Analyzed Dataset):**
  - App Store: `60.3%`
  - Play Store: `24.7%`
  - Reddit: `14.9%`

---

## 🧠 Strategic Decision Logic (For Your Advisor)

When discussing the architecture and logic of this project with your Advisor, here are the key strategic decisions made to ensure this solution is robust, competitive, and highly actionable:

1. **Aggressive Relevance Filtering (The 91.3% Drop Rate)**
   - *Logic:* Large Language Models (LLMs) are expensive and subject to strict rate limits. Feeding 5,421 raw reviews to an LLM is inefficient. By building a strict keyword and NLP relevance filter in Phase 3, we discarded "Great app!" and spam reviews. This ensures the AI only spends compute time on reviews that contain **actual friction points or feature requests**, drastically lowering API costs and improving insight density.

2. **Multi-Model LLM Architecture (Groq + Gemini)**
   - *Logic:* We utilized Groq for rapid, high-volume categorization tasks (due to its low latency) and Gemini for complex nuance extraction (like pulling out specific behavior patterns and user quotes). This hybrid approach provides the best balance of speed and deep comprehension.

3. **Database Migration to PostgreSQL**
   - *Logic:* While SQLite was fine for local development, migrating to PostgreSQL ensures the engine can handle concurrent reads from the dashboard and writes from the GitHub Actions automation. This makes the project fully production-ready and deployable on platforms like Railway/Render.

4. **Automated User Research over Manual Surveys**
   - *Logic (Aligning with Feedback):* As noted in your feedback session, user research should increase confidence in product direction without requiring constant manual oversight. Instead of running slow, manual user surveys, this Engine creates a **continuous, automated feedback loop**. It proactively discovers what users are saying in the wild, identifying workarounds and abandonment triggers automatically. This gives the product team a significant **competitive advantage** over teams relying on lagging survey data.

5. **Headless Execution via GitHub Actions**
   - *Logic:* Originally, the dashboard had a "Run Pipeline" button that would hang the UI for minutes while scraping and analyzing. We shifted this to run headlessly via GitHub Actions. Now, the heavy processing happens in the background, and the UI is instantly responsive, querying pre-processed insights directly from PostgreSQL. This is how modern data pipelines operate at scale.

---

## 🚀 Immediate Next Steps
- Implementing the **"Get Summary"** feature on the dashboard to replace the legacy "Run Pipeline" button, giving the user a narrative-driven executive summary of the analytics.
