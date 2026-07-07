# 🎵 Spotify Review Discovery Engine

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-f55036?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=github-actions&logoColor=white)

An end-to-end **AI-Powered Review Analytics Engine** built to scrape, process, and analyze user feedback across multiple platforms to extract actionable product insights regarding Spotify's music discovery features.

---

## 📌 Project Overview

This project is a continuous, automated feedback loop that proactively discovers what users are saying "in the wild" about their Spotify experience. Instead of relying on lagging manual user surveys, this engine automatically identifies workarounds, abandonment triggers, and friction points.

It scrapes thousands of reviews from Reddit, the Apple App Store, the Google Play Store, and the Spotify Community forums. It then utilizes a multi-model LLM architecture (Google Gemini and Groq) to:
- Strip Personal Identifiable Information (PII)
- Classify reviews into specific pain-point themes
- Analyze sentiment and user frustration levels
- Extract highly representative user quotes
- Detect overarching behavioral patterns

---

## 🏗️ Architecture & Data Pipeline

The engine relies on a headless, scheduled GitHub Actions pipeline that feeds a centralized PostgreSQL database. All heavy data processing occurs in the background, ensuring the insight dashboard remains blazing fast.

```mermaid
graph TD
    subgraph "Layer 1 — Data Collection"
        S1[Google Play Store]
        S2[Apple App Store]
        S3[Reddit]
        S4[Spotify Community]
    end

    subgraph "Layer 2 — Data Pipeline"
        P1[(PostgreSQL Raw Data)]
        P2[Cleaning & Normalization]
        P3[PII Removal Engine]
        P4[Deduplication]
        P5[(PostgreSQL Processed)]
    end

    subgraph "Layer 3 — LLM Analysis Agent"
        A1[Theme Classification]
        A2[Sentiment Analysis]
        A3[Quote Extraction]
        A4[Behavior Pattern Detection]
    end

    subgraph "Layer 4 — Delivery"
        O1[Insight Dashboard UI]
        O2[Research Findings Report]
    end

    S1 --> P1
    S2 --> P1
    S3 --> P1
    S4 --> P1

    P1 --> P2 --> P3 --> P4 --> P5

    P5 --> A1
    P5 --> A2
    P5 --> A3
    P5 --> A4

    A1 --> O1
    A2 --> O1
    A3 --> O1
    A4 --> O1
    
    A1 --> O2
    A2 --> O2
    A3 --> O2
    A4 --> O2
```

---

## 🧠 Strategic Highlights

### 1. Aggressive Relevance Filtering
Feeding raw scraped data to LLMs is expensive and inefficient. We built a strict NLP relevance filter that drops **91.3%** of "noise" (e.g., spam, "great app"). The AI only spends compute time on reviews containing actual friction points, maximizing insight density and minimizing API costs.

### 2. Multi-Model LLM Architecture
- **Groq (Llama 3 70B):** Utilized for rapid, high-volume categorization tasks where latency is critical.
- **Google Gemini (2.5 Flash):** Utilized for complex nuance extraction, including pulling out behavioral workarounds, analyzing deep sentiment, and extracting exact user quotes.

### 3. Headless Execution
Originally, the dashboard featured a "Run Pipeline" button that would hang the UI during scraping and analysis. This architecture shifts the heavy lifting to run headlessly via a scheduled **GitHub Actions** pipeline. The UI is now instantly responsive, querying pre-processed insights directly from PostgreSQL.

### 4. Zero PII Tolerance
The data pipeline includes a dual-pass PII removal process (Regex + NER via spaCy). Any review that cannot be confidently stripped of personal identifiers is excluded from the dataset entirely.

---

## 📊 By The Numbers (Latest Pipeline Run)

During the most recent end-to-end automated pipeline run, the system processed:
- **Total Raw Reviews Scraped:** `5,421`
- **Relevance Drop Rate:** `91.3%`
- **PII Items Redacted:** `484` 
- **High-Quality Processed Reviews Analyzed:** `469` 
- **Source Breakdown:** App Store (`60.3%`), Play Store (`24.7%`), Reddit (`14.9%`)

---

## 🛠️ Tech Stack

### Data & Backend
* **Database:** PostgreSQL (Supabase) 
* **Scraping:** Python (PRAW, google-play-scraper)
* **Pipeline:** Python, spaCy (NER for PII), pandas

### AI & LLMs
* **Models:** Google Gemini 2.5 Flash, Groq (Llama-3.3-70b-versatile)
* **Tasks:** Sentiment Analysis, Theme Classification, Quote Extraction, Behavior Pattern Detection

### Frontend & Automation
* **Dashboards:** HTML5, CSS3 (Glassmorphism, Light/Dark Modes), Vanilla JS
* **Automation:** GitHub Actions (Nightly Data Pipeline)

---
*Created as part of the NextLeap PM Fellowship Graduation Project (Part 1).*
