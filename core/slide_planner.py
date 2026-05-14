import yaml
from utils.claude_client import ClaudeClient

SYSTEM_PROMPT = """You are a presentation strategist at Indiamart Intermesh Ltd.
You create slide plans that match the specific preferences of the leader being presented to.
Every slide must have a clear purpose and key message."""

PLANNING_PROMPT = """Create a slide-by-slide plan for a presentation.

PRESENTING TO: {leader_name} ({leader_role})

LEADER PREFERENCES:
- Depth: {depth}
- Max slides: {max_slides}
- Tone: {tone}
- Always include topics: {always_include}
- Never include topics: {never_include}
- Prefers: {chart_pref}
- Max bullets per slide: {max_bullets}
- Suggested structure: {structure}

CONTENT AVAILABLE:
Title suggestion: {title}
Key metrics: {metrics}
Findings: {findings}
Achievements: {achievements}
Challenges: {challenges}
Recommendations: {recommendations}
Decisions needed: {decisions}
Available chart data: {chart_data}
Diagram suggestions: {diagrams}

Return a JSON array of slides:
[
  {{
    "slide_number": 1,
    "slide_type": "title",
    "layout": "title_slide",
    "title": "presentation title",
    "subtitle": "subtitle or date",
    "key_message": "",
    "content_source": "none",
    "has_chart": false,
    "has_diagram": false,
    "diagram_type": null,
    "bullets_planned": 0
  }},
  {{
    "slide_number": 2,
    "slide_type": "content",
    "layout": "bullets",
    "title": "slide title",
    "subtitle": "",
    "key_message": "the ONE thing this slide communicates",
    "content_source": "key_metrics,findings",
    "has_chart": false,
    "has_diagram": false,
    "diagram_type": null,
    "bullets_planned": 3
  }}
]

RULES:
- Respect max_slides strictly ({max_slides} slides maximum)
- Every slide MUST have a key_message (except title slide)
- slide_type must be one of: title, executive_summary, content, chart, diagram, comparison, ask
- layout must be one of: title_slide, bullets, bullets_with_callout, chart_with_text, diagram_full, two_column, ask_slide
- has_chart: true only if chart_data supports it
- has_diagram: true only if content naturally needs a visual (architecture, flow, comparison, timeline)
- diagram_type if has_diagram: architecture, flowchart, comparison, timeline
- First slide = title, second slide should be highest-impact insight
- Last content slide = the ASK (what decision/action is needed)
- Never include topics from the never_include list"""


class SlidePlanner:
    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def load_profile(self, profile_path: str) -> dict:
        with open(profile_path, "r") as f:
            return yaml.safe_load(f)

    def plan(self, content: dict, profile: dict) -> list:
        prefs = profile["content_preferences"]
        vis = profile["visual_preferences"]
        tone = profile["tone"]

        chart_pref = "charts over tables" if vis.get("prefers_charts_over_tables") else "tables over charts"

        prompt = PLANNING_PROMPT.format(
            leader_name=profile["name"],
            leader_role=profile["role"],
            depth=prefs["depth"],
            max_slides=prefs["max_slides"],
            tone=tone["language"],
            always_include=", ".join(tone.get("always_include", [])),
            never_include=", ".join(tone.get("never_include", [])),
            chart_pref=chart_pref,
            max_bullets=vis["max_bullet_points_per_slide"],
            structure="\n".join(profile.get("structure", [])),
            title=content.get("title_suggestion", "Presentation"),
            metrics=str(content.get("key_metrics", [])),
            findings=str(content.get("findings", [])),
            achievements=str(content.get("achievements", [])),
            challenges=str(content.get("challenges", [])),
            recommendations=str(content.get("recommendations", [])),
            decisions=str(content.get("decisions_needed", [])),
            chart_data=str(content.get("chart_data", [])),
            diagrams=str(content.get("diagram_suggestions", [])),
        )

        slides = self.claude.generate_json(SYSTEM_PROMPT, prompt)

        if not isinstance(slides, list):
            slides = slides.get("slides", [])

        max_s = prefs["max_slides"]
        if len(slides) > max_s:
            slides = slides[:max_s]

        return slides
