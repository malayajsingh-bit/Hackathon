from utils.claude_client import ClaudeClient

SYSTEM_PROMPT = """You are a presentation content writer at Indiamart Intermesh Ltd.
You write concise, impactful slide content tailored to the audience.
Every word must earn its place on the slide."""

SLIDE_CONTENT_PROMPT = """Generate content for slide {slide_number} of {total_slides}.

SLIDE PLAN:
- Type: {slide_type}
- Layout: {layout}
- Title: {title}
- Key message: {key_message}
- Content source: {content_source}
- Has chart: {has_chart}
- Has diagram: {has_diagram}
- Bullets planned: {bullets_planned}

AVAILABLE CONTENT:
{available_content}

LEADER PREFERENCES:
- Tone: {tone}
- Max bullets: {max_bullets}
- Max chars per bullet: {max_chars}
- Min font size: {min_font} (so keep text SHORT)

Return JSON:
{{
  "title": "short impactful title (max 8 words)",
  "subtitle": "optional subtitle or empty string",
  "bullets": ["bullet 1", "bullet 2"],
  "key_callout": "the standout number or fact (or empty string)",
  "speaker_notes": "what presenter should SAY (2-3 sentences of context not on slide)",
  "chart_spec": null,
  "diagram_spec": null
}}

If has_chart is true, include chart_spec:
{{
  "chart_spec": {{
    "type": "bar|line|pie|horizontal_bar",
    "title": "chart title",
    "data": {{
      "labels": ["label1", "label2"],
      "datasets": [
        {{"label": "series", "values": [100, 200]}}
      ]
    }}
  }}
}}

If has_diagram is true, include diagram_spec:
{{
  "diagram_spec": {{
    "type": "architecture|flowchart|comparison|timeline",
    "title": "diagram title",
    "elements": [
      {{"id": "n1", "label": "Node 1", "type": "box", "group": "group1"}},
      {{"id": "n2", "label": "Node 2", "type": "box", "group": "group2"}}
    ],
    "connections": [
      {{"from": "n1", "to": "n2", "label": "connects"}}
    ],
    "groups": [
      {{"id": "group1", "label": "Layer 1", "color": "blue"}},
      {{"id": "group2", "label": "Layer 2", "color": "green"}}
    ]
  }}
}}

RULES:
- Each bullet: max {max_chars} characters
- Lead with the insight, not the setup
- Use Indian number format for currency (lakhs/crores with ₹)
- Use % for percentages
- Include actual numbers, never vague language like "significant" or "many"
- Speaker notes add context that doesn't fit on the slide
- For title slide: bullets should be empty, subtitle = date or tagline"""


class SlideGenerator:
    def __init__(self, claude_client: ClaudeClient):
        self.claude = claude_client

    def generate_all(self, slide_plan: list, content: dict, profile: dict) -> list:
        slides = []
        total = len(slide_plan)
        vis = profile["visual_preferences"]
        tone = profile["tone"]

        content_str = self._format_content(content)

        for plan in slide_plan:
            slide_content = self._generate_single(plan, content_str, total, vis, tone)
            slides.append(slide_content)

        return slides

    def _generate_single(self, plan: dict, content_str: str, total: int,
                         vis: dict, tone: dict) -> dict:
        prompt = SLIDE_CONTENT_PROMPT.format(
            slide_number=plan["slide_number"],
            total_slides=total,
            slide_type=plan["slide_type"],
            layout=plan["layout"],
            title=plan["title"],
            key_message=plan.get("key_message", ""),
            content_source=plan.get("content_source", ""),
            has_chart=plan.get("has_chart", False),
            has_diagram=plan.get("has_diagram", False),
            bullets_planned=plan.get("bullets_planned", 3),
            available_content=content_str,
            tone=tone["language"],
            max_bullets=vis["max_bullet_points_per_slide"],
            max_chars=vis.get("max_chars_per_bullet", 70),
            min_font=vis["font_size_minimum"],
        )

        result = self.claude.generate_json(SYSTEM_PROMPT, prompt)

        for key in ["title", "subtitle", "bullets", "key_callout", "speaker_notes"]:
            if key not in result:
                result[key] = "" if key != "bullets" else []

        result["slide_number"] = plan["slide_number"]
        result["slide_type"] = plan["slide_type"]
        result["layout"] = plan["layout"]

        return result

    def _format_content(self, content: dict) -> str:
        parts = []
        if content.get("key_metrics"):
            parts.append("KEY METRICS:\n" + "\n".join(
                [f"- {m['metric']}: {m['value']} ({m.get('change', 'N/A')}, {m.get('period', '')})"
                 for m in content["key_metrics"]]))
        if content.get("findings"):
            parts.append("FINDINGS:\n" + "\n".join([f"- {f}" for f in content["findings"]]))
        if content.get("achievements"):
            parts.append("ACHIEVEMENTS:\n" + "\n".join([f"- {a}" for a in content["achievements"]]))
        if content.get("challenges"):
            parts.append("CHALLENGES:\n" + "\n".join([f"- {c}" for c in content["challenges"]]))
        if content.get("recommendations"):
            parts.append("RECOMMENDATIONS:\n" + "\n".join([f"- {r}" for r in content["recommendations"]]))
        if content.get("decisions_needed"):
            parts.append("DECISIONS NEEDED:\n" + "\n".join([f"- {d}" for d in content["decisions_needed"]]))
        if content.get("chart_data"):
            parts.append("CHART DATA:\n" + str(content["chart_data"]))
        if content.get("diagram_suggestions"):
            parts.append("DIAGRAM SUGGESTIONS:\n" + str(content["diagram_suggestions"]))
        return "\n\n".join(parts)
