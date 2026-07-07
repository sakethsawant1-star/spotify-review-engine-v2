# 🎵 Spotify Review Discovery Engine & AI Vibe Prompt

![Spotify](https://img.shields.io/badge/Spotify-1ED760?style=for-the-badge&logo=spotify&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-43853D?style=for-the-badge&logo=node.js&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-f55036?style=for-the-badge)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlebard&logoColor=white)

An end-to-end **AI-Powered Review Analytics Engine** and **Music Discovery MVP (Vibe Prompt)** built to analyze user feedback, extract actionable product insights, and solve music discovery loops on Spotify.

---

## 📌 Project Overview

This project is divided into two major components:
1. **The Review Discovery Engine:** A continuous, automated feedback loop that scrapes thousands of reviews from Reddit, the App Store, the Play Store, and Spotify Community. It uses a multi-model LLM architecture (Gemini + Groq) to strip PII, classify themes, analyze sentiment, and extract user pain points about music discovery.
2. **The Vibe Prompt MVP:** A production-deployed, stateless AI bridge that takes a user's natural language vibe description (e.g., *"late night drive, melancholic but calm"*) and curates a personalized Spotify playlist instantly, solving the exact discovery fatigue identified by the Review Engine.

---

## 🏗️ How It Works (The Data Pipeline)

The engine relies on a headless, scheduled GitHub Actions pipeline that feeds a centralized PostgreSQL database. The heavy lifting is done in the background so the frontend dashboard remains blazing fast.

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
        O2[Vibe Prompt MVP]
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
    
    A4 -.->|Informs Product MVP| O2
```

---

## 🧠 Strategic Highlights

### 1. Aggressive Relevance Filtering
Feeding raw scraped data to LLMs is expensive and inefficient. We built a strict NLP relevance filter that drops **91.3%** of "noise" (e.g., spam, "great app"). The AI only processes reviews containing actual friction points, maximizing insight density and minimizing compute cost.

### 2. Multi-Model LLM Architecture
- **Groq (Llama 3 70B):** Used for rapid, high-volume categorization tasks where latency matters.
- **Google Gemini:** Used for complex nuance extraction (pulling out behavioral workarounds, deep sentiment, and exact user quotes).

### 3. Automated User Research
Instead of lagging manual surveys, this Engine creates a **continuous, automated feedback loop** running in the background via GitHub Actions, giving product teams a massive competitive advantage.

### 4. Zero-Cost Vibe MVP
The Vibe Prompt MVP uses a completely stateless architecture (`Node.js/Express` on Railway + Vercel Frontend + Groq + Spotify Web API) to generate and save playlists directly to a user's Spotify account, proving the research hypothesis at zero infrastructure cost.

---

## 📊 By The Numbers (Latest Run)
- **Total Raw Reviews Scraped:** `5,421`
- **Relevance Drop Rate:** `91.3%`
- **PII Items Redacted:** `484` (Zero PII tolerance)
- **High-Quality Processed Reviews:** `469` 
- **Source Breakdown:** App Store (`60.3%`), Play Store (`24.7%`), Reddit (`14.9%`)

---

## 🛠️ Tech Stack

### Data & Backend
* **Database:** PostgreSQL (Supabase) / SQLite (Local)
* **Scraping:** Python (PRAW, google-play-scraper)
* **Pipeline:** Python, spaCy (NER for PII), pandas
* **Vibe Backend:** Node.js, Express, Axios

### AI & LLMs
* **Models:** Google Gemini 2.5 Flash, Groq (Llama-3.3-70b-versatile)
* **Tasks:** Intent Extraction, Sentiment Analysis, Theme Classification, PII validation

### Frontend & Deployment
* **Dashboards:** HTML5, CSS3 (Glassmorphism, Dark/Light modes), Vanilla JS
* **Hosting:** Vercel (Frontend), Railway (Node.js Backend)
* **Automation:** GitHub Actions (Nightly Data Pipeline)

---
*Created as part of the NextLeap PM Fellowship Graduation Project.*
