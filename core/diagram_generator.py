import os
import json
from utils.claude_client import ClaudeClient
from utils.config import BRAND_HEX

SYSTEM_PROMPT = """You are a diagram designer. You create clean, professional Excalidraw diagrams
for business presentations at Indiamart. Use the brand colors provided.
Return ONLY a valid JSON array of Excalidraw elements."""

DIAGRAM_PROMPT = """Create an Excalidraw diagram for a presentation slide.

DIAGRAM SPECIFICATION:
Type: {diagram_type}
Title: {title}
Elements: {elements}
Connections: {connections}
Groups: {groups}

BRAND COLORS TO USE:
- Primary Blue: {primary} (main elements)
- Dark Navy: {dark} (text, borders)
- Orange Accent: {accent} (highlights, callouts)
- Success Green: {success} (positive items)
- Danger Red: {danger} (negative items, warnings)

EXCALIDRAW FORMAT RULES:
- Start with cameraUpdate: {{"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0}}
- Rectangles: {{"type": "rectangle", "id": "unique_id", "x": N, "y": N, "width": N, "height": N, "backgroundColor": "#hex", "fillStyle": "solid", "roundness": {{"type": 3}}, "strokeColor": "#hex", "label": {{"text": "label", "fontSize": 16}}}}
- Arrows: {{"type": "arrow", "id": "unique_id", "x": N, "y": N, "width": N, "height": 0, "points": [[0,0],[width,0]], "strokeColor": "#hex", "strokeWidth": 2, "endArrowhead": "arrow"}}
- Text: {{"type": "text", "id": "unique_id", "x": N, "y": N, "text": "content", "fontSize": 20, "strokeColor": "#hex"}}

DIAGRAM TYPE GUIDELINES:
- architecture: Use colored zones (rectangles with low opacity) to group layers. Place boxes inside zones. Connect with arrows.
- flowchart: Linear or branching flow. Use diamonds for decisions. Use arrows between steps.
- comparison: Two columns side by side. Left = before/current (red tones), Right = after/proposed (green tones).
- timeline: Horizontal flow with milestones. Use a horizontal line with nodes branching up/down.

RULES:
- Keep it clean and readable — max 15-20 elements
- Minimum font size: 16
- Minimum box size: 140x55
- Leave 30px gaps between elements
- Use background zones (opacity: 30) to group related elements
- No emoji in text
- Return ONLY the JSON array, no explanation"""

# Fallback diagrams when Claude API isn't available or fails
FALLBACK_DIAGRAMS = {
    "architecture": [
        {"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0},
        {"type": "rectangle", "id": "zone1", "x": 20, "y": 50, "width": 230, "height": 500,
         "backgroundColor": "#dbe4ff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#4a9eed", "strokeWidth": 1, "opacity": 35},
        {"type": "text", "id": "z1l", "x": 70, "y": 58, "text": "Frontend", "fontSize": 18, "strokeColor": "#2563eb"},
        {"type": "rectangle", "id": "b1", "x": 40, "y": 100, "width": 190, "height": 55,
         "backgroundColor": "#a5d8ff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#4a9eed", "label": {"text": "Web App", "fontSize": 16}},
        {"type": "rectangle", "id": "b2", "x": 40, "y": 180, "width": 190, "height": 55,
         "backgroundColor": "#a5d8ff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#4a9eed", "label": {"text": "Mobile App", "fontSize": 16}},
        {"type": "rectangle", "id": "zone2", "x": 290, "y": 50, "width": 230, "height": 500,
         "backgroundColor": "#e5dbff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#8b5cf6", "strokeWidth": 1, "opacity": 35},
        {"type": "text", "id": "z2l", "x": 350, "y": 58, "text": "Backend", "fontSize": 18, "strokeColor": "#6d28d9"},
        {"type": "rectangle", "id": "b3", "x": 310, "y": 100, "width": 190, "height": 55,
         "backgroundColor": "#d0bfff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#8b5cf6", "label": {"text": "API Gateway", "fontSize": 16}},
        {"type": "rectangle", "id": "b4", "x": 310, "y": 180, "width": 190, "height": 55,
         "backgroundColor": "#d0bfff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#8b5cf6", "label": {"text": "Services", "fontSize": 16}},
        {"type": "rectangle", "id": "zone3", "x": 560, "y": 50, "width": 220, "height": 500,
         "backgroundColor": "#d3f9d8", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#22c55e", "strokeWidth": 1, "opacity": 35},
        {"type": "text", "id": "z3l", "x": 620, "y": 58, "text": "Data", "fontSize": 18, "strokeColor": "#15803d"},
        {"type": "rectangle", "id": "b5", "x": 580, "y": 100, "width": 180, "height": 55,
         "backgroundColor": "#c3fae8", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#22c55e", "label": {"text": "Database", "fontSize": 16}},
        {"type": "rectangle", "id": "b6", "x": 580, "y": 180, "width": 180, "height": 55,
         "backgroundColor": "#c3fae8", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#22c55e", "label": {"text": "Cache", "fontSize": 16}},
        {"type": "arrow", "id": "a1", "x": 230, "y": 127, "width": 80, "height": 0,
         "points": [[0, 0], [80, 0]], "strokeColor": "#1e1e1e", "strokeWidth": 2, "endArrowhead": "arrow"},
        {"type": "arrow", "id": "a2", "x": 500, "y": 127, "width": 80, "height": 0,
         "points": [[0, 0], [80, 0]], "strokeColor": "#1e1e1e", "strokeWidth": 2, "endArrowhead": "arrow"},
    ],
    "flowchart": [
        {"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0},
        {"type": "rectangle", "id": "s1", "x": 300, "y": 30, "width": 200, "height": 55,
         "backgroundColor": "#a5d8ff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#4a9eed", "label": {"text": "Start", "fontSize": 18}},
        {"type": "arrow", "id": "a1", "x": 400, "y": 85, "width": 0, "height": 40,
         "points": [[0, 0], [0, 40]], "strokeColor": "#1e1e1e", "strokeWidth": 2, "endArrowhead": "arrow"},
        {"type": "rectangle", "id": "s2", "x": 300, "y": 125, "width": 200, "height": 55,
         "backgroundColor": "#d0bfff", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#8b5cf6", "label": {"text": "Process", "fontSize": 18}},
        {"type": "arrow", "id": "a2", "x": 400, "y": 180, "width": 0, "height": 40,
         "points": [[0, 0], [0, 40]], "strokeColor": "#1e1e1e", "strokeWidth": 2, "endArrowhead": "arrow"},
        {"type": "diamond", "id": "d1", "x": 320, "y": 220, "width": 160, "height": 100,
         "backgroundColor": "#fff3bf", "fillStyle": "solid", "strokeColor": "#f59e0b",
         "label": {"text": "Decision", "fontSize": 16}},
        {"type": "arrow", "id": "a3", "x": 480, "y": 270, "width": 100, "height": 0,
         "points": [[0, 0], [100, 0]], "strokeColor": "#22c55e", "strokeWidth": 2, "endArrowhead": "arrow",
         "label": {"text": "Yes", "fontSize": 14}},
        {"type": "arrow", "id": "a4", "x": 320, "y": 270, "width": -100, "height": 0,
         "points": [[0, 0], [-100, 0]], "strokeColor": "#ef4444", "strokeWidth": 2, "endArrowhead": "arrow",
         "label": {"text": "No", "fontSize": 14}},
        {"type": "rectangle", "id": "s3", "x": 580, "y": 245, "width": 160, "height": 55,
         "backgroundColor": "#b2f2bb", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#22c55e", "label": {"text": "Success", "fontSize": 16}},
        {"type": "rectangle", "id": "s4", "x": 60, "y": 245, "width": 160, "height": 55,
         "backgroundColor": "#ffc9c9", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#ef4444", "label": {"text": "Retry", "fontSize": 16}},
    ],
    "comparison": [
        {"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0},
        {"type": "rectangle", "id": "left", "x": 20, "y": 50, "width": 360, "height": 500,
         "backgroundColor": "#ffc9c9", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#ef4444", "strokeWidth": 1, "opacity": 25},
        {"type": "text", "id": "ll", "x": 130, "y": 60, "text": "BEFORE", "fontSize": 22, "strokeColor": "#ef4444"},
        {"type": "rectangle", "id": "right", "x": 420, "y": 50, "width": 360, "height": 500,
         "backgroundColor": "#b2f2bb", "fillStyle": "solid", "roundness": {"type": 3},
         "strokeColor": "#22c55e", "strokeWidth": 1, "opacity": 25},
        {"type": "text", "id": "rl", "x": 545, "y": 60, "text": "AFTER", "fontSize": 22, "strokeColor": "#22c55e"},
    ],
    "timeline": [
        {"type": "cameraUpdate", "width": 800, "height": 600, "x": 0, "y": 0},
        {"type": "arrow", "id": "line", "x": 50, "y": 300, "width": 700, "height": 0,
         "points": [[0, 0], [700, 0]], "strokeColor": "#1E3A5F", "strokeWidth": 3, "endArrowhead": "arrow"},
        {"type": "text", "id": "tl", "x": 300, "y": 250, "text": "Timeline", "fontSize": 22, "strokeColor": "#1E3A5F"},
    ],
}


class DiagramGenerator:
    def __init__(self, claude_client: ClaudeClient, output_dir: str = "temp"):
        self.claude = claude_client
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, diagram_spec: dict, filename: str) -> tuple:
        """Returns (excalidraw_elements_json, png_path_or_none)"""
        diagram_type = diagram_spec.get("type", "architecture")

        try:
            elements = self._generate_with_claude(diagram_spec)
        except Exception:
            elements = FALLBACK_DIAGRAMS.get(diagram_type,
                                              FALLBACK_DIAGRAMS["architecture"])

        json_path = os.path.join(self.output_dir, filename.replace(".png", ".json"))
        with open(json_path, "w") as f:
            json.dump(elements, f, indent=2)

        return elements, json_path

    def _generate_with_claude(self, spec: dict) -> list:
        prompt = DIAGRAM_PROMPT.format(
            diagram_type=spec.get("type", "architecture"),
            title=spec.get("title", "Diagram"),
            elements=json.dumps(spec.get("elements", []), indent=2),
            connections=json.dumps(spec.get("connections", []), indent=2),
            groups=json.dumps(spec.get("groups", []), indent=2),
            primary=BRAND_HEX["primary"],
            dark=BRAND_HEX["dark"],
            accent=BRAND_HEX["accent"],
            success=BRAND_HEX["success"],
            danger=BRAND_HEX["danger"],
        )

        result = self.claude.generate_json(SYSTEM_PROMPT, prompt)

        if isinstance(result, dict):
            result = result.get("elements", [result])
        if not isinstance(result, list):
            raise ValueError("Expected JSON array of elements")

        return result

    def generate_placeholder_image(self, diagram_spec: dict, filename: str) -> str:
        """Generate a matplotlib-based placeholder for the diagram when Excalidraw export isn't available."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        fig, ax = plt.subplots(figsize=(12, 7))
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 60)
        ax.set_aspect("equal")
        ax.axis("off")

        diagram_type = diagram_spec.get("type", "architecture")
        title = diagram_spec.get("title", "Diagram")
        elements = diagram_spec.get("elements", [])
        connections = diagram_spec.get("connections", [])

        ax.text(50, 57, title, ha="center", va="top", fontsize=18,
                fontweight="bold", color="#1E3A5F")

        colors = {"blue": "#DBEAFE", "green": "#D1FAE5", "purple": "#EDE9FE",
                  "orange": "#FED7AA", "red": "#FECACA"}
        border_colors = {"blue": "#2563EB", "green": "#16A34A", "purple": "#8B5CF6",
                         "orange": "#F59E0B", "red": "#EF4444"}

        if elements:
            n = len(elements)
            cols = min(n, 4)
            rows = (n + cols - 1) // cols
            box_w = 80 / cols
            box_h = min(10, 40 / rows)

            positions = {}
            for i, elem in enumerate(elements):
                row = i // cols
                col = i % cols
                x = 10 + col * (box_w + 3)
                y = 45 - row * (box_h + 5)

                group = elem.get("group", "blue")
                color_key = elem.get("color", group)
                if color_key not in colors:
                    color_key = "blue"

                rect = patches.FancyBboxPatch(
                    (x, y), box_w, box_h,
                    boxstyle="round,pad=0.5",
                    facecolor=colors[color_key],
                    edgecolor=border_colors[color_key],
                    linewidth=2)
                ax.add_patch(rect)
                ax.text(x + box_w / 2, y + box_h / 2, elem.get("label", elem.get("id", "")),
                        ha="center", va="center", fontsize=10, fontweight="bold",
                        color="#1F2937")
                positions[elem["id"]] = (x + box_w / 2, y + box_h / 2)

            for conn in connections:
                src = conn.get("from", "")
                dst = conn.get("to", "")
                if src in positions and dst in positions:
                    sx, sy = positions[src]
                    dx, dy = positions[dst]
                    ax.annotate("", xy=(dx, dy), xytext=(sx, sy),
                                arrowprops=dict(arrowstyle="->", color="#6B7280", lw=1.5))
                    if conn.get("label"):
                        mx, my = (sx + dx) / 2, (sy + dy) / 2
                        ax.text(mx, my + 1.5, conn["label"], ha="center", fontsize=8,
                                color="#6B7280")
        else:
            ax.text(50, 30, f"[{diagram_type.title()} Diagram]", ha="center", va="center",
                    fontsize=16, color="#6B7280", style="italic")

        output_path = os.path.join(self.output_dir, filename)
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return output_path
