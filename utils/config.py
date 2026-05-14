from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor

BRAND = {
    "primary": RGBColor(0x25, 0x63, 0xEB),
    "dark": RGBColor(0x1E, 0x3A, 0x5F),
    "accent": RGBColor(0xFF, 0x6B, 0x35),
    "text": RGBColor(0x1F, 0x29, 0x37),
    "text_muted": RGBColor(0x6B, 0x72, 0x80),
    "light_bg": RGBColor(0xF8, 0xF9, 0xFA),
    "white": RGBColor(0xFF, 0xFF, 0xFF),
    "success": RGBColor(0x16, 0xA3, 0x4A),
    "danger": RGBColor(0xDC, 0x26, 0x26),
}

BRAND_HEX = {
    "primary": "#2563EB",
    "dark": "#1E3A5F",
    "accent": "#FF6B35",
    "text": "#1F2937",
    "light_bg": "#F8F9FA",
    "success": "#16A34A",
    "danger": "#DC2626",
}

CHART_COLORS = ["#2563EB", "#FF6B35", "#1E3A5F", "#10B981", "#8B5CF6", "#EC4899"]

SLIDE_DIMENSIONS = {
    "width": Inches(13.333),
    "height": Inches(7.5),
}

FONT_FAMILY = "Calibri"

FOOTER_TEXT = "Confidential - Indiamart Intermesh Ltd."

DEFAULT_MODEL = "openrouter/qwen/qwen3-32b"
DEFAULT_GATEWAY_URL = "https://imllm.intermesh.net/v1"
