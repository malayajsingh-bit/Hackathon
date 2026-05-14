# Indiamart AI Presentation Generator

AI-powered PPT generator that creates presentations tailored to leadership preferences.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key (or enter in the UI)
export ANTHROPIC_API_KEY="your-key-here"

# Run the app
streamlit run app.py
```

## Usage

1. Open the app in your browser (http://localhost:8501)
2. Enter your Anthropic API key in the sidebar
3. Provide content (upload files, paste text, or enter a topic)
4. Select who you're presenting to (CEO, CTO, VP Sales, VP Product)
5. Review and edit the slide plan
6. Click Generate PPT and download

## Project Structure

```
Hackathon/
├── app.py                    # Streamlit UI
├── requirements.txt
├── core/
│   ├── content_extractor.py  # Reads sources → structured content
│   ├── slide_planner.py      # Content + Profile → slide structure
│   ├── slide_generator.py    # Slide structure → text per slide
│   ├── chart_generator.py    # Data → matplotlib charts
│   ├── diagram_generator.py  # Specs → diagram images
│   └── ppt_renderer.py       # Everything → .pptx file
├── profiles/
│   ├── ceo.yml               # CEO preferences
│   ├── cto.yml               # CTO preferences
│   ├── vp_sales.yml          # VP Sales preferences
│   └── vp_product.yml        # VP Product preferences
├── utils/
│   ├── claude_client.py      # Claude API wrapper
│   └── config.py             # Brand colors, fonts, constants
├── output/                   # Generated PPTs saved here
└── temp/                     # Temporary chart/diagram images
```

## Adding New Leader Profiles

Create a new `.yml` file in `profiles/` following the existing format.
The app auto-discovers all profiles on startup.
