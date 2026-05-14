import os
import json
import yaml
import streamlit as st
from datetime import datetime

from utils.claude_client import ClaudeClient
from core.content_extractor import ContentExtractor
from core.slide_planner import SlidePlanner
from core.slide_generator import SlideGenerator
from core.chart_generator import ChartGenerator
from core.diagram_generator import DiagramGenerator
from core.ppt_renderer import PPTRenderer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def load_profiles():
    profiles = {}
    for f in os.listdir(PROFILES_DIR):
        if f.endswith(".yml") or f.endswith(".yaml"):
            path = os.path.join(PROFILES_DIR, f)
            with open(path, "r") as fh:
                data = yaml.safe_load(fh)
                key = os.path.splitext(f)[0]
                profiles[key] = data
    return profiles


def init_clients(api_key: str, base_url: str, model: str):
    claude = ClaudeClient(api_key=api_key, base_url=base_url, model=model)
    return {
        "claude": claude,
        "extractor": ContentExtractor(claude),
        "planner": SlidePlanner(claude),
        "generator": SlideGenerator(claude),
        "chart_gen": ChartGenerator(TEMP_DIR),
        "diagram_gen": DiagramGenerator(claude, TEMP_DIR),
    }


def save_uploaded_file(uploaded_file) -> str:
    path = os.path.join(TEMP_DIR, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path


# ─── PAGE CONFIG ───
st.set_page_config(
    page_title="Indiamart PPT Generator",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CUSTOM CSS ───
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #6B7280;
        margin-top: -10px;
    }
    .profile-card {
        background: #EFF6FF;
        border: 1px solid #2563EB;
        border-radius: 10px;
        padding: 15px;
        margin: 5px 0;
    }
    .step-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2563EB;
        border-bottom: 2px solid #2563EB;
        padding-bottom: 5px;
        margin-top: 20px;
    }
    .stButton>button {
        background-color: #2563EB;
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 25px;
        font-weight: 600;
    }
    .stButton>button:hover {
        background-color: #1E3A5F;
    }
</style>
""", unsafe_allow_html=True)

# ─── HEADER ───
st.markdown('<p class="main-header">📊 Indiamart Presentation Generator</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">AI-powered PPTs tailored to your leadership\'s preferences</p>',
            unsafe_allow_html=True)
st.markdown("---")

# ─── SIDEBAR: LLM GATEWAY CONFIG ───
with st.sidebar:
    st.header("⚙️ LLM Gateway Configuration")
    gateway_url = st.text_input("Gateway Base URL",
                                value="https://imllm.intermesh.net/v1",
                                help="Indiamart LLM Gateway (OpenAI-compatible)")
    api_key = st.text_input("API Key", type="password",
                            placeholder="Your LLM Gateway access key (sk-xxx)")
    model_name = st.text_input("Model Name",
                               value="openrouter/qwen/qwen3-32b",
                               help="Model identifier — use the model you have access to")

    if api_key and gateway_url:
        st.success("Gateway configured")
    elif api_key or gateway_url:
        st.warning("Both URL and API key are required")

    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
    1. **Provide content** — upload files, paste text, URL, GitHub, etc.
    2. **Select leader** — choose who you're presenting to
    3. **Review plan** — edit the slide structure
    4. **Generate PPT** — download your presentation
    """)
    st.markdown("---")
    st.markdown("*Built for Indiamart Hackathon 2026*")

if not api_key or not gateway_url:
    st.warning("👈 Enter your LLM Gateway URL and API key in the sidebar to get started.")
    st.stop()

clients = init_clients(api_key, gateway_url, model_name)
profiles = load_profiles()

# ─── STEP 1: CONTENT SOURCE ───
st.markdown('<p class="step-header">Step 1: Provide Content</p>', unsafe_allow_html=True)

st.markdown("**P0 — Primary Inputs**")
tab_p0_1, tab_p0_2, tab_p0_3, tab_p0_4 = st.tabs(
    ["📝 Paste Text", "📊 Excel / CSV", "💡 Enter Topic", "🔄 Update Existing PPT"])

with tab_p0_1:
    pasted_text = st.text_area("Paste your content here",
                               placeholder="Paste report data, bullet points, metrics, meeting notes, or any content...",
                               height=250, key="pasted_text")
    paste_context = st.text_area("Additional context (optional)",
                                 placeholder="e.g., This is for the quarterly business review",
                                 key="paste_context", height=80)

with tab_p0_2:
    data_files = st.file_uploader(
        "Upload data files",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help="Upload metrics, KPI data, or any tabular data",
        key="data_upload"
    )
    data_context = st.text_area("What should the presentation focus on?",
                                placeholder="e.g., Compare Q1 vs Q2 performance, highlight top 5 cities...",
                                key="data_context", height=80)

with tab_p0_3:
    topic = st.text_input("Presentation topic",
                          placeholder="e.g., Q1 2026 Seller Engagement Results")
    topic_context = st.text_area("Key points and context",
                                 placeholder="e.g., DAU grew 23%, revenue up 1.2Cr, launched AI lead scoring...",
                                 height=150, key="topic_context")

with tab_p0_4:
    old_ppt = st.file_uploader(
        "Upload existing presentation to update",
        type=["pptx"],
        help="Upload last quarter's PPT — AI will keep the structure and update the content",
        key="old_ppt_upload"
    )
    new_data_for_ppt = st.file_uploader(
        "Upload new data (optional)",
        type=["csv", "xlsx", "xls", "pdf", "docx", "txt"],
        accept_multiple_files=True,
        help="New metrics or reports to update the PPT with",
        key="new_data_upload"
    )
    new_text_for_ppt = st.text_area("Or paste new data / updates",
                                     placeholder="e.g., Q2 revenue: ₹4.5Cr (up from ₹3.8Cr), DAU now 1.4M...",
                                     key="new_ppt_text", height=100)
    ppt_update_context = st.text_area("Update instructions (optional)",
                                       placeholder="e.g., Keep same structure, update all numbers to Q2, add new seller churn slide",
                                       key="ppt_update_context", height=80)
    st.caption("AI reads the old PPT, keeps the same slide structure, and refreshes content with new data.")

st.markdown("---")
st.markdown("**P1 — Document & Visual Inputs**")
tab_p1_1, tab_p1_2, tab_p1_3 = st.tabs(
    ["📁 Documents (PDF/Word)", "🖼️ Screenshots / Images", "🌐 URL / Webpage"])

with tab_p1_1:
    doc_files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True,
        help="BRDs, PRDs, reports, meeting notes — any text document",
        key="doc_upload"
    )
    doc_context = st.text_area("Presentation focus (optional)",
                               placeholder="e.g., Focus on the seller onboarding section of the BRD",
                               key="doc_context", height=80)

with tab_p1_2:
    image_files = st.file_uploader(
        "Upload screenshots or images",
        type=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
        accept_multiple_files=True,
        help="Product screenshots, competitor pages, mockups — will be embedded in slides",
        key="image_upload"
    )
    image_context = st.text_area("Describe these images (optional)",
                                 placeholder="e.g., Screenshot 1 is our seller dashboard, Screenshot 2 is competitor's pricing page",
                                 key="image_context", height=80)
    st.caption("Images will be embedded directly into your presentation slides.")

with tab_p1_3:
    url_input = st.text_input("Enter webpage URL",
                              placeholder="e.g., https://competitor.com/pricing or any article URL",
                              key="url_input")
    url_context = st.text_area("What to extract from this page?",
                               placeholder="e.g., Summarize the pricing plans and compare with ours",
                               key="url_context", height=80)
    st.caption("AI reads the webpage and extracts relevant content for your slides.")

st.markdown("---")
st.markdown("**P2 — Project & Code Inputs**")
tab_p2_1, tab_p2_2 = st.tabs(["📋 OpenProject", "🐙 GitHub Repo"])

with tab_p2_1:
    op_col1, op_col2 = st.columns(2)
    with op_col1:
        openproject_url = st.text_input("OpenProject Base URL",
                                        placeholder="e.g., https://openproject.indiamart.com")
    with op_col2:
        openproject_project = st.text_input("Project ID (optional)",
                                            placeholder="e.g., seller-engagement")
    openproject_key = st.text_input("API Key", type="password",
                                    placeholder="Your OpenProject API key",
                                    key="op_api_key")
    openproject_context = st.text_area("Presentation focus (optional)",
                                       placeholder="e.g., Sprint progress update, blockers and risks...",
                                       key="op_context", height=80)
    st.caption("Fetches tickets, status summary, priorities, and assignee data.")

with tab_p2_2:
    github_url = st.text_input("GitHub Repository URL",
                               placeholder="e.g., https://github.com/org/repo")
    github_context = st.text_area("What should the presentation focus on?",
                                  placeholder="e.g., Project overview and architecture for CTO review...",
                                  key="github_context", height=100)
    st.caption("Reads README, directory structure, config files, source code, and recent commits.")

st.markdown("---")
st.markdown("**P3 — External Data**")
tab_p3_1 = st.tabs(["📊 Google Sheets"])[0]

with tab_p3_1:
    gsheet_url = st.text_input("Google Sheets URL",
                               placeholder="e.g., https://docs.google.com/spreadsheets/d/abc123/edit",
                               key="gsheet_url")
    gsheet_context = st.text_area("What data to focus on?",
                                  placeholder="e.g., Monthly revenue trend in Sheet1, city-wise breakdown in Sheet2",
                                  key="gsheet_context", height=80)
    st.caption("Sheet must be shared with 'Anyone with the link'. Reads data as CSV.")

# ─── STEP 2: SELECT LEADER ───
st.markdown('<p class="step-header">Step 2: Select Audience</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])

with col1:
    leader_key = st.selectbox(
        "Presenting to",
        options=list(profiles.keys()),
        format_func=lambda x: f"{profiles[x]['name']} ({profiles[x]['role']})")

with col2:
    p = profiles[leader_key]
    prefs = p["content_preferences"]
    vis = p["visual_preferences"]

    st.markdown(f"""
    <div class="profile-card">
        <strong>{p['name']}</strong> — {p['role']}<br>
        📊 Max slides: <strong>{prefs['max_slides']}</strong> |
        📝 Depth: <strong>{prefs['depth']}</strong> |
        🔤 Min font: <strong>{vis['font_size_minimum']}pt</strong><br>
        🎯 Tone: <strong>{p['tone']['language']}</strong> |
        📈 Prefers: <strong>{'Charts' if vis['prefers_charts_over_tables'] else 'Tables'}</strong>
    </div>
    """, unsafe_allow_html=True)

# ─── STEP 3: EXTRACT & PLAN ───
st.markdown('<p class="step-header">Step 3: Generate Slide Plan</p>', unsafe_allow_html=True)

if st.button("🚀 Analyze Content & Create Plan", type="primary", use_container_width=True):
    with st.spinner("🔍 Extracting content from sources..."):
        content = None
        uploaded_image_paths = []

        # P0: Paste Text
        if pasted_text:
            content = clients["extractor"].extract_from_text(pasted_text, paste_context)

        # P0: Excel / CSV
        elif data_files:
            file_paths = [save_uploaded_file(f) for f in data_files]
            content = clients["extractor"].extract_from_files(file_paths, data_context)

        # P0: Topic
        elif topic:
            content = clients["extractor"].extract_from_topic(topic, topic_context)

        # P0: Update Existing PPT
        elif old_ppt:
            old_ppt_path = save_uploaded_file(old_ppt)
            new_paths = [save_uploaded_file(f) for f in new_data_for_ppt] if new_data_for_ppt else []
            content = clients["extractor"].extract_from_previous_ppt(
                old_ppt_path, new_paths, new_text_for_ppt, ppt_update_context)

        # P1: Documents
        elif doc_files:
            file_paths = [save_uploaded_file(f) for f in doc_files]
            content = clients["extractor"].extract_from_files(file_paths, doc_context)

        # P1: Screenshots / Images
        elif image_files:
            uploaded_image_paths = [save_uploaded_file(f) for f in image_files]
            img_description = image_context or "Product screenshots and visuals for the presentation"
            file_info = ", ".join([f.name for f in image_files])
            content = clients["extractor"].extract_from_text(
                f"Images uploaded: {file_info}\n\nContext: {img_description}",
                "Create a presentation that incorporates these images into relevant slides.")

        # P1: URL / Webpage
        elif url_input:
            content = clients["extractor"].extract_from_url(url_input, url_context)

        # P2: OpenProject
        elif openproject_url and openproject_key:
            content = clients["extractor"].extract_from_openproject(
                openproject_url, openproject_key,
                openproject_project or None, openproject_context)

        # P2: GitHub Repo
        elif github_url:
            content = clients["extractor"].extract_from_github(github_url, github_context)

        # P3: Google Sheets
        elif gsheet_url:
            content = clients["extractor"].extract_from_google_sheet(gsheet_url, gsheet_context)

        else:
            st.error("Please provide content in one of the input tabs above.")
            st.stop()

        if uploaded_image_paths:
            content["_uploaded_images"] = uploaded_image_paths

        st.session_state.content = content

    with st.spinner("📋 Planning slides for " + p["name"] + "..."):
        plan = clients["planner"].plan(content, profiles[leader_key])
        st.session_state.plan = plan
        st.session_state.leader_key = leader_key

    st.success(f"✅ Plan created: {len(plan)} slides for {p['name']}")

# ─── STEP 4: REVIEW & EDIT PLAN ───
if "plan" in st.session_state:
    st.markdown('<p class="step-header">Step 4: Review & Edit Plan</p>', unsafe_allow_html=True)

    content = st.session_state.content

    with st.expander("📊 Extracted Content Summary", expanded=False):
        st.json(content)

    st.markdown("**Edit slide titles, reorder, or remove slides:**")

    edited_plan = []
    for slide in st.session_state.plan:
        sn = slide["slide_number"]
        col_a, col_b, col_c = st.columns([0.5, 3, 1])

        with col_a:
            keep = st.checkbox("", value=True, key=f"keep_{sn}")

        with col_b:
            new_title = st.text_input(
                f"Slide {sn} ({slide['slide_type']})",
                value=slide.get("title", ""),
                key=f"title_{sn}")

        with col_c:
            slide_type = st.selectbox(
                "Type",
                options=["title", "executive_summary", "content", "chart",
                         "diagram", "comparison", "ask"],
                index=["title", "executive_summary", "content", "chart",
                        "diagram", "comparison", "ask"].index(
                    slide.get("slide_type", "content")),
                key=f"type_{sn}")

        if keep:
            updated_slide = slide.copy()
            updated_slide["title"] = new_title
            updated_slide["slide_type"] = slide_type
            edited_plan.append(updated_slide)

    st.session_state.edited_plan = edited_plan
    st.info(f"📝 {len(edited_plan)} slides will be generated")

    # ─── STEP 5: GENERATE PPT ───
    st.markdown('<p class="step-header">Step 5: Generate Presentation</p>', unsafe_allow_html=True)

    if st.button("⚡ Generate PPT", type="primary", use_container_width=True):
        profile = profiles[st.session_state.leader_key]
        plan = st.session_state.edited_plan
        content = st.session_state.content

        progress = st.progress(0, text="Starting generation...")
        total_steps = len(plan) + 2

        # Generate slide content
        progress.progress(1 / total_steps, text="Generating slide content with AI...")
        slide_contents = clients["generator"].generate_all(plan, content, profile)

        # Generate charts and diagrams
        chart_paths = {}
        diagram_paths = {}

        for i, (plan_item, slide_content) in enumerate(zip(plan, slide_contents)):
            step = i + 2
            progress.progress(step / total_steps,
                              text=f"Processing slide {i + 1}/{len(plan)}...")

            if slide_content.get("chart_spec"):
                try:
                    path = clients["chart_gen"].generate(
                        slide_content["chart_spec"],
                        f"chart_{plan_item['slide_number']}.png")
                    chart_paths[plan_item["slide_number"]] = path
                except Exception as e:
                    st.warning(f"Chart generation failed for slide {plan_item['slide_number']}: {e}")

            if slide_content.get("diagram_spec"):
                try:
                    spec = slide_content["diagram_spec"]
                    img_path = clients["diagram_gen"].generate_placeholder_image(
                        spec, f"diagram_{plan_item['slide_number']}.png")
                    diagram_paths[plan_item["slide_number"]] = img_path
                except Exception as e:
                    st.warning(f"Diagram generation failed for slide {plan_item['slide_number']}: {e}")

        # Render PPT
        progress.progress((total_steps - 1) / total_steps, text="Rendering PPT...")
        renderer = PPTRenderer(profile)

        for plan_item, slide_content in zip(plan, slide_contents):
            sn = plan_item["slide_number"]

            if plan_item["slide_type"] == "title":
                renderer.add_title_slide(
                    title=slide_content.get("title", "Presentation"),
                    subtitle=slide_content.get("subtitle", ""),
                    date=datetime.now().strftime("%B %Y"))
            else:
                renderer.add_content_slide(
                    slide_content,
                    chart_path=chart_paths.get(sn),
                    diagram_path=diagram_paths.get(sn))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        leader_name = profile["name"].replace(" ", "_")
        output_filename = f"presentation_{leader_name}_{timestamp}.pptx"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        renderer.save(output_path)

        progress.progress(1.0, text="Done!")

        st.success(f"🎉 Presentation generated: {len(plan)} slides for {profile['name']}")

        with open(output_path, "rb") as f:
            st.download_button(
                label="⬇️ Download Presentation",
                data=f,
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                use_container_width=True)

        st.markdown("---")
        st.markdown("### 🔄 Generate for Another Leader")
        st.markdown("Change the leader in Step 2 and click **Generate PPT** again — same content, different style!")

        with st.expander("📄 View Generated Slide Content", expanded=False):
            for sc in slide_contents:
                st.markdown(f"**Slide {sc.get('slide_number', '?')}: {sc.get('title', '')}**")
                if sc.get("bullets"):
                    for b in sc["bullets"]:
                        st.markdown(f"  - {b}")
                if sc.get("key_callout"):
                    st.info(f"Key insight: {sc['key_callout']}")
                if sc.get("speaker_notes"):
                    st.caption(f"Speaker notes: {sc['speaker_notes']}")
                st.markdown("---")
