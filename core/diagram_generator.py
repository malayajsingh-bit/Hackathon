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
        """
        Render diagram at EXACT PPT embedding size (11.0" × 4.04") so that
        fontsize=22 in matplotlib = 22 pt visually in the final PPT slide.
        Boxes are always wider than tall (horizontal rectangles).
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from collections import defaultdict, deque
        import textwrap

        diagram_type = diagram_spec.get("type", "flowchart")
        title        = diagram_spec.get("title", "")
        elements     = diagram_spec.get("elements", [])
        connections  = diagram_spec.get("connections", [])

        # ── These MUST match ppt_renderer._add_diagram_slide embedding ──────
        # width=Inches(11.0), height=Inches(_CONTENT_H - 0.2) = 4.04"
        FIG_W, FIG_H = 11.0, 4.04

        FILL   = {"blue": "#DBEAFE", "green": "#D1FAE5", "orange": "#FED7AA",
                  "red": "#FEE2E2", "purple": "#EDE9FE", "navy": "#EEF2FF",
                  "default": "#F1F5F9"}
        BORDER = {"blue": "#2563EB", "green": "#16A34A", "orange": "#F97316",
                  "red": "#DC2626", "purple": "#7C3AED", "navy": "#1E3A5F",
                  "default": "#94A3B8"}

        def gc(group):
            g = (group or "blue").lower()
            return FILL.get(g, FILL["default"]), BORDER.get(g, BORDER["default"])

        # Create figure at exact embedding size with axes filling the whole figure
        fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        ax.set_xlim(0, FIG_W)
        ax.set_ylim(0, FIG_H)
        ax.axis("off")
        fig.patch.set_facecolor("white")

        # Title strip at the top
        TITLE_H = 0.38
        if title:
            ax.text(FIG_W / 2, FIG_H - TITLE_H / 2, title,
                    ha="center", va="center", fontsize=13, fontweight="bold",
                    color="#1E3A5F", zorder=5)
            ax.axhline(y=FIG_H - TITLE_H, xmin=0, xmax=1,
                       color="#E5E7EB", linewidth=1, zorder=1)

        # Usable drawing area (in inches = data coords)
        MX = 0.25   # left/right margin
        MY = 0.15   # top/bottom margin inside body
        BODY_TOP = FIG_H - TITLE_H - MY   # top of drawing area
        BODY_BOT = MY                     # bottom of drawing area
        BODY_H   = BODY_TOP - BODY_BOT    # total usable height ≈ 3.16"
        BODY_CY  = (BODY_TOP + BODY_BOT) / 2

        positions  = {}
        elem_by_id = {e.get("id", f"_{i}"): e for i, e in enumerate(elements)}
        for i, e in enumerate(elements):
            e.setdefault("id", f"_{i}")

        # ── draw_box: cx/cy/bw/bh in inches (= data coords) ─────────────────
        def draw_box(cx, cy, bw, bh, label, group, fontsize=22, zorder=3):
            fill, border = gc(group)
            rect = patches.FancyBboxPatch(
                (cx - bw / 2, cy - bh / 2), bw, bh,
                boxstyle="round,pad=0.03",
                facecolor=fill, edgecolor=border,
                linewidth=2, zorder=zorder)
            ax.add_patch(rect)
            # Horizontal padding: 0.18" each side; vertical padding baked into bh
            H_PAD = 0.18
            inner_w = max(0.1, bw - 2 * H_PAD)
            # Avg char width for regular (non-bold) Calibri ≈ fontsize*0.48/72 inches
            avg_cw  = fontsize * 0.48 / 72
            chars   = max(5, int(inner_w / avg_cw))
            lines   = textwrap.wrap(str(label), width=chars) or [str(label)]
            wrapped = "\n".join(lines)
            txt = ax.text(cx, cy, wrapped,
                          ha="center", va="center",
                          fontsize=fontsize, fontweight="normal",   # NOT bold
                          color="#1F2937", zorder=zorder + 1,
                          multialignment="center",
                          linespacing=1.3)
            txt.set_clip_path(rect)
            txt.set_clip_on(True)

        # ── draw_arrow: coordinates in inches ────────────────────────────────
        def draw_arrow(sx, sy, dx, dy, label="", color="#6B7280"):
            ax.annotate("", xy=(dx, dy), xytext=(sx, sy),
                        arrowprops=dict(
                            arrowstyle="-|>",
                            color=color, lw=1.5,
                            connectionstyle="arc3,rad=0.03",
                            mutation_scale=12),
                        zorder=6)
            if label:
                ax.text((sx + dx) / 2, (sy + dy) / 2 + 0.08,
                        label, ha="center", fontsize=9, color="#6B7280", zorder=7)

        # ── TIMELINE ─────────────────────────────────────────────────────────
        if diagram_type == "timeline":
            n    = max(len(elements), 1)
            bw_t = min(1.6, (FIG_W - 2 * MX) / max(n, 1) * 0.78)
            bh_t = 0.72
            # Keep box centres at least bw/2 inside each edge so nothing clips
            x0   = MX + bw_t / 2
            x1   = FIG_W - MX - bw_t / 2
            xs   = [x0 + (x1 - x0) * i / max(n - 1, 1) for i in range(n)]

            mid_y = BODY_CY
            # Baseline runs only between the first and last box centre
            ax.plot([xs[0], xs[-1]], [mid_y, mid_y],
                    color="#1E3A5F", linewidth=2.5, zorder=1)

            for i, (elem, x) in enumerate(zip(elements, xs)):
                above  = (i % 2 == 0)
                cy     = mid_y + (0.82 if above else -0.82)
                _, brd = gc(elem.get("group", "blue"))
                ax.plot([x, x], [mid_y, cy + (-bh_t / 2 if above else bh_t / 2)],
                        color=brd, lw=1.5, zorder=2)
                ax.plot(x, mid_y, "o", color=brd, markersize=9, zorder=3)
                draw_box(x, cy, bw_t, bh_t, elem.get("label", ""),
                         elem.get("group", "blue"), fontsize=13)
                positions[elem["id"]] = (x, cy)

        # ── COMPARISON ───────────────────────────────────────────────────────
        elif diagram_type == "comparison":
            mid       = max(len(elements) // 2, 1)
            left_els  = elements[:mid]
            right_els = elements[mid:]
            cx_l, cx_r = FIG_W * 0.27, FIG_W * 0.73

            ax.text(cx_l, BODY_TOP + 0.05, "BEFORE / CURRENT",
                    ha="center", fontsize=12, fontweight="bold", color="#DC2626")
            ax.text(cx_r, BODY_TOP + 0.05, "AFTER / PROPOSED",
                    ha="center", fontsize=12, fontweight="bold", color="#16A34A")
            ax.axvline(x=FIG_W / 2, ymin=0, ymax=1,
                       color="#E5E7EB", linewidth=1.5, linestyle="--", zorder=1)

            col_bw = (FIG_W / 2 - 2 * MX) * 0.92
            for col_elems, cx_b, def_grp in [
                (left_els, cx_l, "red"), (right_els, cx_r, "green")
            ]:
                n   = max(len(col_elems), 1)
                bh  = min(0.80, (BODY_H - (n - 1) * 0.15) / n)
                gap = (BODY_H - n * bh) / max(n - 1, 1) if n > 1 else 0
                y0  = BODY_BOT + bh / 2
                for j, elem in enumerate(col_elems):
                    cy = y0 + j * (bh + gap)
                    draw_box(cx_b, cy, col_bw, bh,
                             elem.get("label", ""), elem.get("group", def_grp),
                             fontsize=16)
                    positions[elem["id"]] = (cx_b, cy)

        # ── ARCHITECTURE ─────────────────────────────────────────────────────
        elif diagram_type == "architecture":
            groups = defaultdict(list)
            for elem in elements:
                groups[elem.get("group", "blue")].append(elem)
            gkeys = list(groups.keys()) or ["blue"]
            n_g   = len(gkeys)
            col_w = (FIG_W - 2 * MX) / n_g

            for gi, gkey in enumerate(gkeys):
                cx     = MX + gi * col_w + col_w / 2
                fill, border = gc(gkey)
                zone = patches.FancyBboxPatch(
                    (cx - col_w / 2 + 0.06, BODY_BOT), col_w - 0.12, BODY_H,
                    boxstyle="round,pad=0.05",
                    facecolor=fill, edgecolor=border,
                    linewidth=1.5, alpha=0.22, zorder=1)
                ax.add_patch(zone)
                ax.text(cx, BODY_TOP - 0.10, gkey.replace("_", " ").title(),
                        ha="center", fontsize=11, fontweight="normal",
                        color=border, zorder=2)

                col_elems = groups[gkey]
                n   = max(len(col_elems), 1)
                bw  = col_w * 0.82
                bh  = min(0.72, (BODY_H - 0.35 - (n - 1) * 0.15) / n)
                gap = (BODY_H - 0.35 - n * bh) / max(n - 1, 1) if n > 1 else 0
                y0  = BODY_BOT + bh / 2
                for j, elem in enumerate(col_elems):
                    cy = y0 + j * (bh + gap)
                    draw_box(cx, cy, bw, bh,
                             elem.get("label", ""), gkey, fontsize=15, zorder=3)
                    positions[elem["id"]] = (cx, cy)

            for conn in connections:
                s, d = conn.get("from"), conn.get("to")
                if s in positions and d in positions:
                    sx, sy = positions[s]
                    dx, dy = positions[d]
                    _, brd = gc(elem_by_id.get(s, {}).get("group", "blue"))
                    draw_arrow(sx + 0.4, sy, dx - 0.4, dy,
                               conn.get("label", ""), color=brd)

        # ── FLOWCHART: horizontal rectangles, topological left→right layout ──
        else:
            id_set = {e["id"] for e in elements}
            adj    = defaultdict(list)
            in_deg = defaultdict(int)
            for conn in connections:
                s, d = conn.get("from"), conn.get("to")
                if s in id_set and d in id_set:
                    adj[s].append(d)
                    in_deg[d] += 1

            levels = {}
            queue  = deque()
            for e in elements:
                eid = e["id"]
                if in_deg.get(eid, 0) == 0:
                    levels[eid] = 0
                    queue.append(eid)
            while queue:
                node = queue.popleft()
                for nxt in adj[node]:
                    if nxt not in levels:
                        levels[nxt] = levels[node] + 1
                        queue.append(nxt)
            for e in elements:
                levels.setdefault(e["id"], 0)

            level_nodes = defaultdict(list)
            for eid, lv in levels.items():
                level_nodes[lv].append(eid)

            n_levels = max(level_nodes.keys(), default=0) + 1
            max_per  = max((len(v) for v in level_nodes.values()), default=1)

            # Font: 22pt for ≤6 levels, scale down for wider diagrams
            BOX_FONT = 22 if n_levels <= 6 else max(14, int(22 * 6 / n_levels))

            usable_w = FIG_W - 2 * MX
            x_step   = usable_w / n_levels
            # Box is a HORIZONTAL rectangle: bw > bh
            bw = x_step * 0.82

            # Height: 2 lines of text + generous top/bottom padding (0.20" each side)
            line_h = BOX_FONT / 72          # inches per line of text
            V_PAD  = 0.22                   # vertical padding top + bottom
            bh     = line_h * 2 * 1.3 + V_PAD   # 2 lines with spacing + padding
            # Cap so all nodes fit vertically; floor so at least 1 line fits
            bh     = min(bh, (BODY_H - (max_per - 1) * 0.18) / max(max_per, 1))
            bh     = max(bh, line_h * 1.3 + V_PAD)

            # Gap between stacked nodes — minimum 0.18" breathing room
            gap_y  = (BODY_H - max_per * bh) / max(max_per - 1, 1)
            gap_y  = max(0.18, min(gap_y, 0.40))

            for lv in sorted(level_nodes.keys()):
                nodes = level_nodes[lv]
                n  = len(nodes)
                cx = MX + lv * x_step + x_step / 2

                total_h = n * bh + (n - 1) * gap_y
                y_start = BODY_CY - total_h / 2 + bh / 2

                for i, node_id in enumerate(nodes):
                    cy   = y_start + i * (bh + gap_y)
                    elem = elem_by_id.get(node_id, {})
                    draw_box(cx, cy, bw, bh,
                             elem.get("label", node_id),
                             elem.get("group", "blue"),
                             fontsize=BOX_FONT)
                    positions[node_id] = (cx, cy)

            for conn in connections:
                s, d = conn.get("from"), conn.get("to")
                if s in positions and d in positions:
                    sx, sy = positions[s]
                    dx, dy = positions[d]
                    _, brd = gc(elem_by_id.get(s, {}).get("group", "blue"))
                    draw_arrow(sx + bw / 2, sy, dx - bw / 2, dy,
                               conn.get("label", ""), color=brd)

        output_path = os.path.join(self.output_dir, filename)
        # Save at exact figsize — NO bbox_inches='tight' which would resize
        plt.savefig(output_path, dpi=150, facecolor="white")
        plt.close()
        return output_path
