# Indiamart AI Presentation Generator

Automatically generates branded PowerPoint presentations tailored to Indiamart leadership (CEO, CTO, VP Sales, VP Product). You feed it content — text, files, URLs, or Gmail threads — and it produces a ready-to-present `.pptx` file.

---

## What you need before starting

- **Python 3.10 or higher** — check with `python --version`
- **Git** — to clone the repo
- **The LLM gateway credentials** — a `gateway_config.json` file (see below)

---

## Setup (one-time)

**1. Clone the repo**
```bash
git clone <repo-url>
cd Hackathon
```

**2. Create a virtual environment** (recommended, keeps dependencies isolated)
```bash
python -m venv venv

# On Mac/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Create the gateway config file**

Create a file named `gateway_config.json` in the project root with this content:
```json
{
  "gateway_url": "https://imllm.intermesh.net/v1",
  "api_key": "your-api-key-here",
  "model_name": "google/gemini-3-flash-preview"
}
```
Get the `api_key` from your team. Without this file the tool will not work.

---

## Running the app (Streamlit UI)

```bash
streamlit run app.py
```

Then open your browser at **http://localhost:8501**

---

## Running via Claude Code (CLI)

If you have Claude Code installed, just open this project folder and type:
```
I want to make a PPT
```
Claude will guide you through picking the leader, content source, and will generate the file automatically.

---

## How to use (Streamlit)

1. Open the app at `http://localhost:8501`
2. Choose who the presentation is for (CEO, CTO, VP Sales, VP Product)
3. Provide your content — paste text, upload a file (PDF/Excel/DOCX), enter a URL, or describe a topic
4. Review the slide plan and make changes if needed
5. Click **Generate PPT** — the file downloads automatically

---

## Supported content sources

| Source | What to provide |
|---|---|
| Text | Paste or type your content directly |
| Files | PDF, Word, Excel, CSV, PowerPoint |
| URL | Any public webpage |
| Topic | Just describe it — the AI fills in the content |
| Gmail | Email threads (requires Gmail MCP in Claude Code) |

---

## Project structure

```
Hackathon/
├── app.py                    # Streamlit web UI
├── mcp_ppt_runner.py         # CLI runner (used by Claude Code)
├── requirements.txt          # Python dependencies
├── gateway_config.json       # LLM gateway credentials (create this yourself)
├── core/
│   ├── content_extractor.py  # Reads sources and pulls out key content
│   ├── slide_planner.py      # Turns content into a slide plan
│   ├── slide_generator.py    # Writes text for each slide
│   ├── chart_generator.py    # Creates charts from data
│   ├── diagram_generator.py  # Creates diagrams
│   ├── ppt_renderer.py       # Assembles everything into a .pptx
│   └── gmail_mcp_bridge.py   # Normalises Gmail thread data
├── profiles/
│   ├── ceo.yml               # CEO style & preferences
│   ├── cto.yml               # CTO style & preferences
│   ├── vp_sales.yml          # VP Sales style & preferences
│   └── vp_product.yml        # VP Product style & preferences
├── prompts.md                # All LLM system prompts
├── utils/
│   └── config.py             # Brand colors, fonts, constants
├── output/                   # Generated .pptx files are saved here
└── temp/                     # Temporary files used during generation
```

---

## Adding a new leader profile

1. Create a new `.yml` file in `profiles/` (e.g. `vp_engineering.yml`)
2. Follow the same structure as an existing profile
3. The app picks it up automatically — no code changes needed
