import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from utils.config import BRAND, FONT_FAMILY, FOOTER_TEXT, SLIDE_DIMENSIONS


class PPTRenderer:
    def __init__(self, profile: dict):
        self.prs = Presentation()
        self.prs.slide_width = SLIDE_DIMENSIONS["width"]
        self.prs.slide_height = SLIDE_DIMENSIONS["height"]
        self.profile = profile
        self.vis = profile["visual_preferences"]
        self.min_font = self.vis["font_size_minimum"]

    def add_title_slide(self, title: str, subtitle: str, date: str):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # blank

        bg = slide.background.fill
        bg.solid()
        bg.fore_color.rgb = BRAND["primary"]

        self._add_textbox(slide, title,
                          left=Inches(1), top=Inches(2.2), width=Inches(11), height=Inches(1.5),
                          font_size=Pt(40), color=BRAND["white"], bold=True, alignment=PP_ALIGN.LEFT)

        sub_text = f"{subtitle}\n{date}" if subtitle else date
        self._add_textbox(slide, sub_text,
                          left=Inches(1), top=Inches(3.8), width=Inches(11), height=Inches(1),
                          font_size=Pt(20), color=BRAND["light_bg"], alignment=PP_ALIGN.LEFT)

        self._add_textbox(slide, FOOTER_TEXT,
                          left=Inches(1), top=Inches(6.5), width=Inches(11), height=Inches(0.5),
                          font_size=Pt(10), color=BRAND["light_bg"], alignment=PP_ALIGN.LEFT)

        self._add_brand_bar(slide)

    def add_content_slide(self, slide_content: dict, chart_path: str = None,
                          diagram_path: str = None):
        slide_type = slide_content.get("slide_type", "content")

        if slide_type == "executive_summary":
            self._add_summary_slide(slide_content)
        elif slide_type == "chart" or chart_path:
            self._add_chart_slide(slide_content, chart_path)
        elif slide_type == "diagram" or diagram_path:
            self._add_diagram_slide(slide_content, diagram_path)
        elif slide_type == "comparison":
            self._add_comparison_slide(slide_content)
        elif slide_type == "ask":
            self._add_ask_slide(slide_content)
        else:
            self._add_bullet_slide(slide_content)

    def _add_summary_slide(self, content: dict):
        slide = self._create_base_slide(content.get("title", "Executive Summary"))

        bullets = content.get("bullets", [])
        metrics = [b for b in bullets if any(c in b for c in ["₹", "%", "+", "-", "x"])]
        non_metrics = [b for b in bullets if b not in metrics]

        if metrics:
            n = len(metrics)
            box_width = min(3.5, 10 / n)
            gap = (10 - n * box_width) / (n + 1)

            for i, metric in enumerate(metrics):
                left = Inches(1 + gap + i * (box_width + gap))
                self._add_metric_card(slide, metric, left, Inches(2.0), Inches(box_width), Inches(1.8))

        if non_metrics:
            y_start = 4.2 if metrics else 2.0
            self._add_bullets(slide, non_metrics,
                              left=Inches(1), top=Inches(y_start),
                              width=Inches(11), height=Inches(2.5))

        self._add_callout(slide, content.get("key_callout", ""))
        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _add_bullet_slide(self, content: dict):
        slide = self._create_base_slide(content.get("title", ""))

        bullets = content.get("bullets", [])
        if bullets:
            self._add_bullets(slide, bullets,
                              left=Inches(1), top=Inches(1.8),
                              width=Inches(11), height=Inches(3.8))

        self._add_callout(slide, content.get("key_callout", ""))
        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _add_chart_slide(self, content: dict, chart_path: str):
        slide = self._create_base_slide(content.get("title", ""))

        if chart_path and os.path.exists(chart_path):
            slide.shapes.add_picture(
                chart_path,
                left=Inches(0.5), top=Inches(1.6),
                width=Inches(7.5), height=Inches(4.8))

            bullets = content.get("bullets", [])
            if bullets:
                self._add_bullets(slide, bullets,
                                  left=Inches(8.5), top=Inches(2.0),
                                  width=Inches(4.3), height=Inches(3.5))
        else:
            bullets = content.get("bullets", [])
            if bullets:
                self._add_bullets(slide, bullets,
                                  left=Inches(1), top=Inches(1.8),
                                  width=Inches(11), height=Inches(4))

        self._add_callout(slide, content.get("key_callout", ""))
        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _add_diagram_slide(self, content: dict, diagram_path: str):
        slide = self._create_base_slide(content.get("title", ""))

        if diagram_path and os.path.exists(diagram_path):
            slide.shapes.add_picture(
                diagram_path,
                left=Inches(0.5), top=Inches(1.5),
                width=Inches(12), height=Inches(5.2))
        else:
            self._add_textbox(slide, "[Diagram placeholder]",
                              left=Inches(2), top=Inches(3), width=Inches(9), height=Inches(1),
                              font_size=Pt(18), color=BRAND["text_muted"],
                              alignment=PP_ALIGN.CENTER)

        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _add_comparison_slide(self, content: dict):
        slide = self._create_base_slide(content.get("title", ""))

        bullets = content.get("bullets", [])
        mid = len(bullets) // 2
        left_items = bullets[:mid] if mid > 0 else bullets
        right_items = bullets[mid:] if mid > 0 else []

        shape_left = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.5), Inches(1.8), Inches(5.8), Inches(4.2))
        shape_left.fill.solid()
        shape_left.fill.fore_color.rgb = RGBColor(0xFF, 0xE4, 0xE4)
        shape_left.line.color.rgb = BRAND["danger"]

        if left_items:
            self._add_textbox(slide, "BEFORE / CURRENT",
                              left=Inches(1), top=Inches(1.9), width=Inches(5), height=Inches(0.5),
                              font_size=Pt(16), color=BRAND["danger"], bold=True)
            self._add_bullets(slide, left_items,
                              left=Inches(1), top=Inches(2.5),
                              width=Inches(5), height=Inches(3))

        shape_right = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(6.8), Inches(1.8), Inches(5.8), Inches(4.2))
        shape_right.fill.solid()
        shape_right.fill.fore_color.rgb = RGBColor(0xE4, 0xFF, 0xE4)
        shape_right.line.color.rgb = BRAND["success"]

        if right_items:
            self._add_textbox(slide, "AFTER / PROPOSED",
                              left=Inches(7.3), top=Inches(1.9), width=Inches(5), height=Inches(0.5),
                              font_size=Pt(16), color=BRAND["success"], bold=True)
            self._add_bullets(slide, right_items,
                              left=Inches(7.3), top=Inches(2.5),
                              width=Inches(5), height=Inches(3))

        self._add_callout(slide, content.get("key_callout", ""))
        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _add_ask_slide(self, content: dict):
        slide = self._create_base_slide(content.get("title", "Decision Needed"))

        bg_shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(1.5), Inches(1.8), Inches(10), Inches(4))
        bg_shape.fill.solid()
        bg_shape.fill.fore_color.rgb = RGBColor(0xEF, 0xF6, 0xFF)
        bg_shape.line.color.rgb = BRAND["primary"]
        bg_shape.line.width = Pt(2)

        bullets = content.get("bullets", [])
        if bullets:
            self._add_bullets(slide, bullets,
                              left=Inches(2), top=Inches(2.5),
                              width=Inches(9), height=Inches(3),
                              color=BRAND["dark"])

        self._add_speaker_notes(slide, content.get("speaker_notes", ""))

    def _create_base_slide(self, title: str):
        slide = self.prs.slides.add_slide(self.prs.slide_layouts[6])  # blank

        self._add_textbox(slide, title,
                          left=Inches(0.8), top=Inches(0.4), width=Inches(11), height=Inches(0.9),
                          font_size=Pt(28), color=BRAND["dark"], bold=True, alignment=PP_ALIGN.LEFT)

        line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                      Inches(0.8), Inches(1.25), Inches(2), Pt(3))
        line.fill.solid()
        line.fill.fore_color.rgb = BRAND["primary"]
        line.line.fill.background()

        self._add_footer(slide)
        return slide

    def _add_bullets(self, slide, bullets: list, left, top, width, height, color=None):
        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame
        tf.word_wrap = True

        for i, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.text = f"  {bullet}"
            p.font.size = Pt(max(self.min_font, 18))
            p.font.color.rgb = color or BRAND["text"]
            p.font.name = FONT_FAMILY
            p.space_after = Pt(10)
            p.level = 0

            bullet_run = p.runs[0] if p.runs else p.add_run()
            p.text = ""
            run_bullet = p.add_run()
            run_bullet.text = "•  "
            run_bullet.font.color.rgb = BRAND["primary"]
            run_bullet.font.size = Pt(max(self.min_font, 18))
            run_bullet.font.name = FONT_FAMILY
            run_text = p.add_run()
            run_text.text = bullet
            run_text.font.color.rgb = color or BRAND["text"]
            run_text.font.size = Pt(max(self.min_font, 18))
            run_text.font.name = FONT_FAMILY

    def _add_metric_card(self, slide, metric_text: str, left, top, width, height):
        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor(0xEF, 0xF6, 0xFF)
        shape.line.color.rgb = BRAND["primary"]
        shape.line.width = Pt(1.5)

        tf = shape.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER

        p = tf.paragraphs[0]
        p.text = metric_text
        p.font.size = Pt(max(self.min_font - 2, 16))
        p.font.color.rgb = BRAND["dark"]
        p.font.name = FONT_FAMILY
        p.font.bold = True
        p.alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].space_before = Pt(15)

    def _add_callout(self, slide, text: str):
        if not text:
            return

        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.8), Inches(6.0), Inches(11.5), Inches(0.8))
        shape.fill.solid()
        shape.fill.fore_color.rgb = BRAND["primary"]
        shape.line.fill.background()

        tf = shape.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = f"KEY INSIGHT:  {text}"
        run.font.color.rgb = BRAND["white"]
        run.font.size = Pt(16)
        run.font.bold = True
        run.font.name = FONT_FAMILY
        p.alignment = PP_ALIGN.LEFT
        tf.margin_left = Inches(0.3)

    def _add_brand_bar(self, slide):
        bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), Inches(0), Inches(13.333), Pt(6))
        bar.fill.solid()
        bar.fill.fore_color.rgb = BRAND["accent"]
        bar.line.fill.background()

    def _add_footer(self, slide):
        self._add_textbox(slide, FOOTER_TEXT,
                          left=Inches(0.8), top=Inches(6.9), width=Inches(5), height=Inches(0.4),
                          font_size=Pt(9), color=BRAND["text_muted"], alignment=PP_ALIGN.LEFT)

        slide_num = len(self.prs.slides)
        self._add_textbox(slide, str(slide_num),
                          left=Inches(12), top=Inches(6.9), width=Inches(0.8), height=Inches(0.4),
                          font_size=Pt(9), color=BRAND["text_muted"], alignment=PP_ALIGN.RIGHT)

    def _add_textbox(self, slide, text: str, left, top, width, height,
                     font_size=Pt(14), color=None, bold=False, alignment=PP_ALIGN.LEFT):
        txBox = slide.shapes.add_textbox(left, top, width, height)
        tf = txBox.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.text = text
        p.font.size = font_size
        p.font.color.rgb = color or BRAND["text"]
        p.font.bold = bold
        p.font.name = FONT_FAMILY
        p.alignment = alignment

    def _add_speaker_notes(self, slide, notes: str):
        if notes:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = notes

    def save(self, output_path: str):
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        self.prs.save(output_path)
        return output_path
