# MuleGuard Local 🛡️

**Explainable, hybrid-ML Mule-Account Detection System.**

Built from raw bank statements (PDF/CSV/XLSX), MuleGuard detects mule accounts, circular/layered fund flows, and produces a transparent, provable risk assessment — powered by a fast cloud LLM for AI narratives and a fully offline ML engine for all scoring.

---

## 🚀 Quick Start

### 1. Get a free Groq API key
Sign up at 👉 [console.groq.com](https://console.groq.com) — no credit card needed.

### 2. Add it to your `.env` file
```bash
cp .env.example .env
# Then open .env and set:
GROQ_API_KEY=gsk_your_key_here
```

### 3. Run with Docker
```bash
./setup.sh
```

Once setup completes, the application is live at:
👉 **http://localhost:8000**

*(API Documentation at `http://localhost:8000/api/docs`)*

---

## 🐳 Docker Commands (Day-to-Day)

| Action | Command |
|--------|---------|
| Start the app | `docker compose up -d` |
| Stop the app | `docker compose down` |
| Rebuild after code change | `docker compose up -d --build` |
| View live logs | `docker compose logs -f` |

---

## 🧠 The Hybrid ML Engine

Nothing is ever computed randomly by an LLM. Every score, flag, and metric is mathematically provable. The AI is only used to generate the plain-English narrative summary.

| Layer | Method | Description |
|-------|--------|-------------|
| **1 — Deterministic Rules** | YAML-configured Rules | Catch textbook mule behavior (retention ratios, structuring, Tarjan's cycle detection). |
| **2 — Unsupervised ML** | Isolation Forest & Robust MAD | Dynamically learns from your entire dataset to catch zero-day anomalies and outliers. |
| **3 — Supervised ML** | LightGBM | Sleeps until you hit 200 manually-labeled accounts, then wakes up to boost accuracy. |
| **4 — AI Narrative** | Groq (Llama 3.1 8B) | Generates a plain-English investigator summary in ~1-2 seconds. Falls back to a rule-based template if the API is unavailable. |

### Three-Tier Decision
All processed statements are classified as:
- 🔴 **CONFIRMED SUSPICIOUS** — fused score ≥ 75, at least one rule triggered
- 🟡 **REVIEW REQUIRED** — ambiguous, ranked for human investigation
- 🟢 **LIKELY LEGITIMATE** — fused score ≤ 25, low anomaly, high confidence

---

## 🕵️‍♂️ Advanced Circular Flow Detection

- Uses **Tarjan's SCC** to filter candidate cyclic regions
- Uses **Johnson's Algorithm** for elementary cycle enumeration
- Scores cycles on **Amount Conservation**, **Velocity Compression**, and **Cycle Recurrence**

---

## 🛠️ Technology Stack

**Backend:**
- Python 3.11+ / FastAPI / Uvicorn
- SQLModel / SQLite (local persistence, zero config)
- `scikit-learn` & `pandas` (anomaly detection)
- `networkx` (graph analytics & cycle detection)
- `pdfplumber`, `camelot-py`, `pytesseract` (offline OCR extraction)
- **Groq API** (ultra-fast LLM narrative generation)

**Frontend:**
- React 18 + TypeScript + Vite
- Tailwind CSS / Recharts / TanStack Table
- Cytoscape.js (interactive proof graph)

---

## ⚙️ Configuration

Every rule threshold, ML sensitivity, and scoring weight is exposed in `/config/thresholds.yaml`. You can tune the entire pipeline dynamically via the frontend UI without touching any Python code.

### Environment Variables (`.env`)

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Your Groq API key for AI narrative generation (free) |
| `DATA_DIR` | Directory for all uploaded files and the SQLite DB |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |
| `HOST` | Bind address (`127.0.0.1` for local, `0.0.0.0` for LAN) |
| `PORT` | Port to serve on (default `8000`) |

---

*Built with ❤️ for transparent, explainable financial investigation.*
