# Indiamart AI Presentation Generator

This tool automatically creates professional PowerPoint presentations for Indiamart leadership — CEO, CTO, VP Sales, and VP Product. You give it your content, it figures out the best way to present it, and gives you a ready-to-use `.pptx` file.

---

## Two ways to use it

### 1. Web App
Open it in your browser, fill a form, click a button, download the PPT.
No coding knowledge needed.

### 2. Claude Code (AI assistant)
Have a conversation with Claude Code — tell it what you want, it asks you questions, and builds the PPT for you.
Works great if you already use Claude Code.

---

## Before you start — things you need

1. **Python 3.10 or above** installed on your computer
   > Not sure? Open a terminal and type `python --version`. If it shows 3.10 or higher, you're good.

2. **Git** installed
   > Used to download this project to your computer.

3. **The LLM gateway credentials** — a small file called `gateway_config.json`
   > Ask your team for the API key. You'll create this file in step 4 of setup.

---

## Setup (do this once)

Open a terminal and run these commands one by one:

**Step 1 — Download the project**
```bash
git clone <repo-url>
cd Hackathon
```

**Step 2 — Create a virtual environment**
> This keeps the project's dependencies separate from the rest of your computer.
```bash
python -m venv venv
```
Then activate it:
```bash
# On Mac or Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

**Step 3 — Install dependencies**
```bash
pip install -r requirements.txt
```

**Step 4 — Create the gateway config file**

Create a file named `gateway_config.json` in the project folder and paste this into it:
```json
{
  "gateway_url": "https://imllm.intermesh.net/v1",
  "api_key": "your-api-key-here",
  "model_name": "google/gemini-3-flash-preview"
}
```
Replace `your-api-key-here` with the actual key from your team. **Without this file, nothing will work.**

---

---

# Way 1 — Web App

## How to start it

```bash
python main.py
```

Then open your browser and go to **http://localhost:8000**

## How to use it

1. **Choose who the presentation is for** — CEO, CTO, VP Sales, or VP Product
2. **Give it your content** — you can paste text, upload files, enter a website link, or just describe a topic
3. **Click Analyze** — the AI reads your content and creates a slide-by-slide plan
4. **Review the plan** — you'll see a list of slides. Change anything you want — add, remove, rename, reorder
5. **Click Generate** — the AI writes all the slides, creates charts if needed, and builds the PPT
6. **Download your file** — a branded `.pptx` ready to present

## What content can you give it?

| Type | What to do |
|---|---|
| **Text** | Paste or type your content in the box |
| **Files** | Upload a PDF, Word doc, Excel sheet, CSV, or existing PowerPoint |
| **Website** | Paste a URL — it reads the page for you |
| **Just a topic** | Type something like "Q1 Sales Performance" — the AI fills in the content |
| **Update an old PPT** | Upload your existing `.pptx` and tell it what's changed |
| **Gmail emails** | Connect your Gmail and pick which email threads to use |
| **GitHub repo** | Paste a GitHub link — useful for tech presentations |
| **OpenProject** | Connect to your project management tool |
| **Google Sheets** | Paste a link to a shared spreadsheet |

> You can mix and match — for example, upload a file AND add a Gmail thread AND a website link. It merges everything together.

## Connecting Gmail (Web App)

To use Gmail as a content source in the web app, you need to set it up once using Google OAuth.

**Setup steps:**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Go to **APIs & Services → Credentials**
3. Click **Create Credentials → OAuth 2.0 Client ID** (choose "Web application")
4. Under "Authorized redirect URIs", add: `http://localhost:8000/auth/gmail/callback`
5. Download the credentials file and rename it to `credentials.json`
6. Place `credentials.json` in the project folder

**In the app:**
1. Click **Connect Gmail**
2. Upload your `credentials.json` if prompted (it auto-loads if already in the folder)
3. Sign in with Google in the browser
4. Search for emails by keyword or sender, then pick the threads you want

> Your sign-in is saved automatically — you won't need to do this every time.

---

---

# Way 2 — Claude Code

## What is Claude Code?

Claude Code is an AI coding assistant made by Anthropic. It can be used as a command-line tool, inside VS Code, JetBrains, or as a desktop app. If you have it set up, you can use it to generate PPTs through a simple conversation.

## How to use it

Open this project folder in Claude Code, then just type what you want:

```
I want to make a PPT
```

```
Create a presentation for the CEO about app churn
```

```
Make slides for VP Sales using this report: report.pdf
```

Claude Code will ask you a few questions (who is it for, what content to use) and then build the entire PPT for you — step by step.

## What happens behind the scenes

Claude Code follows these steps automatically:

| Step | What it does |
|---|---|
| **1. Input gathering** | Asks you who the presentation is for and where the content is coming from |
| **2. Content extraction** | Reads your content and pulls out the key information |
| **3. Slide planning** | The AI designs the narrative — what story to tell, in what order |
| **4. Plan review** | Shows you the slide list. You can ask for changes before it writes anything |
| **5. Slide generation** | Writes the full content for every slide |
| **6. PPT rendering** | Puts it all together into a branded `.pptx` file, saved in the `output/` folder |

## Connecting Gmail (Claude Code)

**No setup needed.** Claude Code has Gmail built in through its MCP integration.

Just tell it:
```
Use my Gmail — search for "app churn" threads
```

Claude Code will connect to Gmail automatically using your Claude account, search for threads, show you a list, and let you pick which ones to include.

---

---

## What goes where — project folder explained

```
Hackathon/
│
├── main.py                  ← Start the web app by running this
├── requirements.txt         ← List of packages to install
├── gateway_config.json      ← Your LLM API credentials (you create this)
├── credentials.json         ← Gmail OAuth file for web app (optional, only for Gmail)
├── token.json               ← Auto-saved Gmail login (created automatically)
│
├── static/                  ← The web app's frontend (browser UI)
│
├── core/                    ← The engine — content reading, AI calls, PPT building
│
├── profiles/                ← One file per leader (CEO, CTO, VP Sales, VP Product)
│   ├── ceo.yml              ← Controls tone, depth, slide count, what to include/avoid
│   ├── cto.yml
│   ├── vp_sales.yml
│   └── vp_product.yml
│
├── prompts.md               ← The instructions given to the AI — edit this to change AI behaviour
├── templates/               ← The Indiamart branded PowerPoint template
├── output/                  ← Your generated PPT files are saved here
└── temp/                    ← Temporary files created during generation (safe to ignore)
```

---

## Common questions

**Where does the generated PPT get saved?**
In the `output/` folder inside the project. The web app also gives you a direct download button.

**Can I change how the AI writes slides?**
Yes — open `prompts.md` and edit the relevant section. No coding required.

**Can I add a new leader profile?**
Yes — create a new `.yml` file in `profiles/` and follow the format of an existing one. The app picks it up automatically.

**The AI generated fewer slides than expected — is that a bug?**
No. If the AI hits its output limit, the tool automatically fills in any missing slides with placeholder text. You can edit those in PowerPoint afterward.

**Gmail isn't connecting on the web app — what do I do?**
Delete `token.json` from the project folder and try connecting again. If that doesn't help, double-check that your `credentials.json` has the correct redirect URI: `http://localhost:8000/auth/gmail/callback`.
