import os
import re
import json
import yaml
import streamlit as st
from datetime import datetime

from utils.claude_client import ClaudeClient
from core.content_extractor import ContentExtractor
from core.ppt_agent import PPTAgent
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
        "agent": PPTAgent(claude),
        "chart_gen": ChartGenerator(TEMP_DIR),
        "diagram_gen": DiagramGenerator(claude, TEMP_DIR),
    }


def save_uploaded_file(uploaded_file) -> str:
    path = os.path.join(TEMP_DIR, uploaded_file.name)
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return path


def merge_content(base: dict, addition: dict) -> dict:
    """Merge two extracted content dicts — lists are concatenated, primary wins on scalars."""
    list_keys = ["key_metrics", "findings", "achievements", "challenges",
                 "recommendations", "decisions_needed", "chart_data", "diagram_suggestions"]
    for key in list_keys:
        if addition.get(key):
            base[key] = base.get(key, []) + addition[key]
    if not base.get("title_suggestion") and addition.get("title_suggestion"):
        base["title_suggestion"] = addition["title_suggestion"]
    if addition.get("_uploaded_images"):
        base.setdefault("_uploaded_images", []).extend(addition["_uploaded_images"])
    return base


def _add(content: dict | None, addition: dict) -> dict:
    return merge_content(content, addition) if content else addition


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
    .section-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 6px;
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
                            value="sk-fOjolFOnhGoJidHjUlFIHA",
                            placeholder="Your LLM Gateway access key (sk-xxx)")
    model_name = st.text_input("Model Name",
                               value="google/gemini-3-flash-preview",
                               help="Model identifier — use the model you have access to")

    if api_key and gateway_url:
        st.success("Gateway configured")
    elif api_key or gateway_url:
        st.warning("Both URL and API key are required")

    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
    1. **Pick a primary source** — paste text, upload a file, enter a topic, URL, or update an existing PPT
    2. **Add more sources** — combine URL + screenshots + docs freely
    3. **Select leader** — choose who you're presenting to
    4. **Review plan** — edit the slide structure
    5. **Generate PPT** — download your presentation
    """)
    st.markdown("---")
    st.markdown("*Built for Indiamart Hackathon 2026*")

if not api_key or not gateway_url:
    st.warning("👈 Enter your LLM Gateway URL and API key in the sidebar to get started.")
    st.stop()

clients = init_clients(api_key, gateway_url, model_name)
profiles = load_profiles()

# ─── GMAIL OAUTH CALLBACK HANDLER ────────────────────────────────────────────
_gmail_error = st.query_params.get("error")
_gmail_code  = st.query_params.get("code")
_gmail_state = st.query_params.get("state")

if _gmail_error:
    st.error(f"Gmail authorisation was denied: {_gmail_error}. Please try again.")
    st.query_params.clear()
elif _gmail_code and _gmail_state:
    if _gmail_state == st.session_state.get("gmail_oauth_state"):
        try:
            from core.gmail_client import (
                exchange_code as _gmail_exchange,
                credentials_to_json as _creds_to_json,
                build_gmail_service as _build_svc,
                get_user_profile as _get_profile,
            )
            _creds_data = st.session_state.get("gmail_creds_data")
            if _creds_data:
                _creds = _gmail_exchange(_creds_data, _gmail_code, _gmail_state,
                                         "http://localhost:8501")
                st.session_state.gmail_credentials_json = _creds_to_json(_creds)
                _svc = _build_svc(_creds)
                _profile = _get_profile(_svc)
                st.session_state.gmail_user_email = _profile.get("email", "connected")
                st.session_state.pop("gmail_oauth_state", None)
        except Exception as _e:
            st.error(f"Gmail OAuth failed: {_e}")
        st.query_params.clear()
        st.rerun()
    else:
        st.query_params.clear()  # stale or forged redirect — ignore
# ─────────────────────────────────────────────────────────────────────────────

# ─── STEP 1: CONTENT SOURCE ───
st.markdown('<p class="step-header">Step 1: Provide Content</p>', unsafe_allow_html=True)

# ── Primary source picker ──────────────────────────────────────────────────────
st.markdown('<p class="section-label">Primary source</p>', unsafe_allow_html=True)

PRIMARY_OPTIONS = [
    "📝 Paste Text",
    "📁 Upload File  (Excel / CSV / PDF / Doc)",
    "💡 Enter Topic",
    "🌐 URL / Webpage",
    "🔄 Update Existing PPT",
]
primary_choice = st.radio(
    "primary_source_radio",
    PRIMARY_OPTIONS,
    horizontal=True,
    label_visibility="collapsed",
)

st.markdown("")  # breathing room

# Initialise all primary-source variables so they're always defined
pasted_text        = ""
paste_context      = ""
primary_files      = None
primary_file_ctx   = ""
topic              = ""
topic_context      = ""
primary_url        = ""
primary_url_ctx    = ""
old_ppt            = None
new_data_for_ppt   = None
new_text_for_ppt   = ""
ppt_update_context = ""

if primary_choice == "📝 Paste Text":
    pasted_text   = st.text_area("Paste your content here",
                                  placeholder="Paste report data, bullet points, metrics, meeting notes…",
                                  height=220, key="paste_main")
    paste_context = st.text_area("Additional context (optional)",
                                  placeholder="e.g. This is for the quarterly business review",
                                  height=70, key="paste_ctx")

elif primary_choice == "📁 Upload File  (Excel / CSV / PDF / Doc)":
    primary_files    = st.file_uploader(
        "Upload files",
        type=["csv", "xlsx", "xls", "pdf", "docx", "txt", "md"],
        accept_multiple_files=True, key="file_main")
    primary_file_ctx = st.text_area("What should the presentation focus on?",
                                     placeholder="e.g. Compare Q1 vs Q2, highlight top 5 cities…",
                                     height=70, key="file_ctx")

elif primary_choice == "💡 Enter Topic":
    topic         = st.text_input("Presentation topic",
                                   placeholder="e.g. Q1 2026 Seller Engagement Results",
                                   key="topic_main")
    topic_context = st.text_area("Key points and context",
                                  placeholder="e.g. DAU grew 23%, revenue up 1.2 Cr, launched AI lead scoring…",
                                  height=130, key="topic_ctx")

elif primary_choice == "🌐 URL / Webpage":
    primary_url     = st.text_input("Enter webpage URL",
                                     placeholder="https://…",
                                     key="url_main")
    primary_url_ctx = st.text_area("What to extract from this page? (optional)",
                                    placeholder="e.g. Summarise the pricing plans and compare with ours",
                                    height=70, key="url_main_ctx")

elif primary_choice == "🔄 Update Existing PPT":
    old_ppt = st.file_uploader(
        "Upload existing presentation to update",
        type=["pptx"],
        help="AI keeps the same structure and refreshes content with your new data",
        key="old_ppt_main")
    new_data_for_ppt = st.file_uploader(
        "Upload new data (optional)",
        type=["csv", "xlsx", "xls", "pdf", "docx", "txt"],
        accept_multiple_files=True, key="new_data_main")
    new_text_for_ppt   = st.text_area("Or paste new data / updates",
                                       placeholder="e.g. Q2 revenue: ₹4.5 Cr (up from ₹3.8 Cr), DAU now 1.4 M…",
                                       height=80, key="new_text_main")
    ppt_update_context = st.text_area("Update instructions (optional)",
                                       placeholder="e.g. Keep same structure, update all numbers to Q2, add new churn slide",
                                       height=70, key="ppt_ctx_main")
    st.caption("AI reads the old PPT, keeps the same slide structure, and refreshes content with new data.")

# ── Additional sources (always visible, all merged) ───────────────────────────
st.markdown("---")
st.markdown('<p class="section-label">➕ Additional sources &nbsp;—&nbsp; optional, all will be merged</p>',
            unsafe_allow_html=True)

add_col1, add_col2 = st.columns(2)

with add_col1:
    extra_url     = st.text_input("🌐 URL / Webpage",
                                   placeholder="https://…  (leave blank to skip)",
                                   key="extra_url")
    extra_url_ctx = st.text_area("URL focus (optional)",
                                  placeholder="e.g. Extract pricing and feature comparisons",
                                  height=60, key="extra_url_ctx")

    extra_docs = st.file_uploader(
        "📄 Documents (PDF / Word / TXT)",
        type=["pdf", "docx", "txt", "md"],
        accept_multiple_files=True, key="extra_docs")

with add_col2:
    extra_images     = st.file_uploader(
        "🖼️ Screenshots / Images",
        type=["png", "jpg", "jpeg", "gif", "webp", "bmp"],
        accept_multiple_files=True, key="extra_images")
    extra_image_ctx  = st.text_area("Describe these images (optional)",
                                     placeholder="e.g. Screenshot 1 = our dashboard, Screenshot 2 = competitor",
                                     height=60, key="extra_img_ctx")

    extra_data = st.file_uploader(
        "📊 Data Files (Excel / CSV)",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True, key="extra_data")

# ── Integrations (collapsed by default) ───────────────────────────────────────
with st.expander("🔌 Integrations  —  GitHub / OpenProject / Google Sheets / Gmail", expanded=False):
    int_t1, int_t2, int_t3, int_t4 = st.tabs(
        ["🐙 GitHub", "📋 OpenProject", "📊 Google Sheets", "📧 Gmail"]
    )

    with int_t1:
        github_url     = st.text_input("GitHub Repository URL",
                                        placeholder="https://github.com/org/repo",
                                        key="gh_url")
        github_context = st.text_area("What should the presentation focus on?",
                                       placeholder="e.g. Project overview and architecture for CTO review",
                                       height=70, key="gh_ctx")
        st.caption("Reads README, directory structure, config files, source code, and recent commits.")

    with int_t2:
        op_c1, op_c2 = st.columns(2)
        with op_c1:
            openproject_url     = st.text_input("OpenProject Base URL",
                                                 placeholder="https://openproject.indiamart.com",
                                                 key="op_url")
        with op_c2:
            openproject_project = st.text_input("Project ID (optional)",
                                                 placeholder="e.g. seller-engagement",
                                                 key="op_proj")
        openproject_key     = st.text_input("API Key", type="password",
                                             placeholder="Your OpenProject API key",
                                             key="op_key")
        openproject_context = st.text_area("Presentation focus (optional)",
                                            placeholder="e.g. Sprint progress update, blockers and risks…",
                                            height=70, key="op_ctx")
        st.caption("Fetches tickets, status summary, priorities, and assignee data.")

    with int_t3:
        gsheet_url     = st.text_input("Google Sheets URL",
                                        placeholder="https://docs.google.com/spreadsheets/d/…",
                                        key="gs_url")
        gsheet_context = st.text_area("What data to focus on?",
                                       placeholder="e.g. Monthly revenue trend in Sheet1, city-wise breakdown in Sheet2",
                                       height=70, key="gs_ctx")
        st.caption("Sheet must be shared with 'Anyone with the link'. Reads data as CSV.")

    with int_t4:
        _gmail_packages_ok = True
        try:
            from core.gmail_client import (
                get_auth_url as _get_auth_url,
                credentials_from_json as _creds_from_json,
                build_gmail_service as _build_gmail_svc,
                build_query as _build_gmail_query,
                list_emails as _list_emails,
                get_thread_messages as _get_thread_msgs,
                format_emails_for_extraction as _fmt_emails,
            )
        except ImportError:
            _gmail_packages_ok = False
            st.error(
                "Gmail integration requires additional packages. Run:\n"
                "`pip install google-auth-oauthlib google-api-python-client google-auth-httplib2`"
            )

        if _gmail_packages_ok:
            _is_connected = bool(st.session_state.get("gmail_credentials_json"))

            if not _is_connected:
                # Auto-load credentials.json from project root if present
                _creds_path = os.path.join(BASE_DIR, "credentials.json")
                if not st.session_state.get("gmail_creds_data") and os.path.exists(_creds_path):
                    try:
                        with open(_creds_path, encoding="utf-8") as _cf:
                            _raw = json.load(_cf)
                        if "installed" in _raw or "web" in _raw:
                            st.session_state.gmail_creds_data = _raw
                    except Exception:
                        pass

                if st.session_state.get("gmail_creds_data"):
                    # Show prominent login button
                    st.markdown("")
                    _col_btn, _col_gap = st.columns([2, 3])
                    with _col_btn:
                        if st.button("🔐 Login with Google", key="gmail_connect_btn",
                                     use_container_width=True, type="primary"):
                            try:
                                _auth_url, _state = _get_auth_url(
                                    st.session_state.gmail_creds_data, "http://localhost:8501"
                                )
                                st.session_state.gmail_oauth_state = _state
                                st.session_state.gmail_auth_url = _auth_url
                            except Exception as _e:
                                st.error(f"Could not generate auth URL: {_e}")

                    if st.session_state.get("gmail_auth_url"):
                        st.markdown(
                            f'<a href="{st.session_state.gmail_auth_url}" target="_blank">'
                            f'➡️ Click here to complete Google sign-in (opens new tab)</a>',
                            unsafe_allow_html=True,
                        )
                        st.caption("After sign-in, Google redirects back to this page automatically.")
                else:
                    st.info(
                        "Place your `credentials.json` (OAuth 2.0 Web/Desktop App) in the project "
                        "folder, or upload it below."
                    )
                    _creds_file = st.file_uploader(
                        "Upload credentials.json", type=["json"], key="gmail_creds_upload"
                    )
                    if _creds_file is not None:
                        try:
                            _raw = json.loads(_creds_file.read().decode("utf-8"))
                            if "installed" not in _raw and "web" not in _raw:
                                st.error("Invalid credentials.json — must contain 'installed' or 'web' key.")
                            else:
                                st.session_state.gmail_creds_data = _raw
                                st.rerun()
                        except Exception as _e:
                            st.error(f"Could not parse credentials.json: {_e}")

            else:
                # ── Connected ─────────────────────────────────────────────────
                _user_email = st.session_state.get("gmail_user_email", "Gmail Account")
                _conn_col, _disc_col = st.columns([4, 1])
                with _conn_col:
                    st.success(f"Connected as: **{_user_email}**")
                with _disc_col:
                    if st.button("Disconnect", key="gmail_disconnect"):
                        for _k in [
                            "gmail_credentials_json", "gmail_user_email",
                            "gmail_creds_data", "gmail_oauth_state",
                            "gmail_emails", "gmail_threads_expanded",
                            "gmail_thread_cache", "gmail_searched",
                        ]:
                            st.session_state.pop(_k, None)
                        # Clear checkbox keys
                        for _k in list(st.session_state.keys()):
                            if _k.startswith("gmail_chk_"):
                                del st.session_state[_k]
                        st.rerun()

                # ── Filters ───────────────────────────────────────────────────
                st.markdown("**Search Emails**")
                _fc1, _fc2, _fc3, _fc4 = st.columns(4)
                with _fc1:
                    _kw = st.text_input("Keywords", placeholder="e.g. invoice Q1", key="gmail_kw")
                with _fc2:
                    _from = st.text_input("From", placeholder="sender@example.com", key="gmail_from")
                with _fc3:
                    _after = st.date_input("After", value=None, key="gmail_after")
                with _fc4:
                    _before = st.date_input("Before", value=None, key="gmail_before")

                _fc5, _fc6, _fc7 = st.columns([2, 1, 1])
                with _fc5:
                    _label = st.selectbox(
                        "Label", ["All", "Inbox", "Sent", "Starred", "Important"],
                        key="gmail_label"
                    )
                with _fc6:
                    _max_r = st.selectbox("Max results", [10, 25, 50], index=1, key="gmail_max")
                with _fc7:
                    _search_clicked = st.button(
                        "Search", key="gmail_search", use_container_width=True
                    )

                if _search_clicked:
                    try:
                        _creds = _creds_from_json(st.session_state.gmail_credentials_json)
                        _svc   = _build_gmail_svc(_creds)
                        _query = _build_gmail_query(
                            keyword=_kw, from_email=_from,
                            after_date=str(_after) if _after else None,
                            before_date=str(_before) if _before else None,
                            label=_label,
                        )
                        with st.spinner("Searching emails…"):
                            _emails = _list_emails(_svc, _query, max_results=_max_r)
                        st.session_state.gmail_emails = _emails
                        st.session_state.gmail_searched = True
                        # Clear old checkboxes
                        for _k in list(st.session_state.keys()):
                            if _k.startswith("gmail_chk_"):
                                del st.session_state[_k]
                        st.session_state.gmail_threads_expanded = set()
                        st.session_state.gmail_thread_cache = {}
                    except Exception as _e:
                        st.error(f"Email search failed: {_e}")

                # ── Email list ────────────────────────────────────────────────
                _emails = st.session_state.get("gmail_emails", [])
                if not _emails and st.session_state.get("gmail_searched"):
                    st.info("No emails found matching your search.")

                if _emails:
                    st.markdown(f"**Results — {len(_emails)} thread(s)**")

                    if "gmail_threads_expanded" not in st.session_state:
                        st.session_state.gmail_threads_expanded = set()
                    if "gmail_thread_cache" not in st.session_state:
                        st.session_state.gmail_thread_cache = {}

                    for _em in _emails:
                        _tid   = _em["threadId"]
                        _tcount = _em.get("thread_count", 1)
                        _is_expanded = _tid in st.session_state.gmail_threads_expanded

                        _chk_col, _info_col = st.columns([0.5, 9.5])
                        with _chk_col:
                            st.checkbox("", key=f"gmail_chk_{_tid}")
                        with _info_col:
                            _badge = f"&nbsp;🔗 {_tcount}" if _tcount > 1 else ""
                            st.markdown(
                                f"**{_em.get('from', '')}**&nbsp;&nbsp;·&nbsp;&nbsp;"
                                f"{_em.get('subject', '(no subject)')}&nbsp;&nbsp;·&nbsp;&nbsp;"
                                f"*{_em.get('date', '')}*{_badge}",
                                unsafe_allow_html=True,
                            )
                            st.caption(_em.get("snippet", ""))

                            if _tcount > 1:
                                _btn_label = "▲ Hide thread" if _is_expanded else "▼ Show thread"
                                if st.button(_btn_label, key=f"gmail_thread_btn_{_tid}"):
                                    _exp_set = st.session_state.gmail_threads_expanded
                                    if _is_expanded:
                                        _exp_set.discard(_tid)
                                    else:
                                        _exp_set.add(_tid)
                                    st.session_state.gmail_threads_expanded = _exp_set
                                    st.rerun()

                            if _is_expanded:
                                if _tid not in st.session_state.gmail_thread_cache:
                                    try:
                                        _creds2 = _creds_from_json(
                                            st.session_state.gmail_credentials_json
                                        )
                                        _svc2 = _build_gmail_svc(_creds2)
                                        _msgs  = _get_thread_msgs(_svc2, _tid)
                                        st.session_state.gmail_thread_cache[_tid] = _msgs
                                    except Exception as _te:
                                        st.warning(f"Could not load thread: {_te}")
                                        _msgs = []
                                else:
                                    _msgs = st.session_state.gmail_thread_cache[_tid]

                                for _r in _msgs[1:]:
                                    st.markdown(
                                        f"&nbsp;&nbsp;&nbsp;└─ **{_r.get('from', '')}** "
                                        f"*({_r.get('date', '')})*"
                                    )
                                    st.caption(
                                        f"     {_r.get('snippet', '')[:150]}"
                                    )

                    # Selection counter
                    _sel_count = sum(
                        1 for _em in _emails
                        if st.session_state.get(f"gmail_chk_{_em['threadId']}", False)
                    )
                    if _sel_count:
                        st.markdown(f"**Selected: {_sel_count} email thread(s)**")
                    else:
                        st.caption("No emails selected yet — check boxes above to select.")

                # ── Focus context ─────────────────────────────────────────────
                st.text_area(
                    "Focus (optional)",
                    placeholder="What should we focus on from these emails? e.g. Summarise action items and key decisions",
                    height=60,
                    key="gmail_focus",
                )
                st.caption(
                    "Select emails above, then click **'Analyze Content & Create Plan'** to include them."
                )

# ── Proof of work screenshots ──────────────────────────────────────────────────
st.markdown("---")
st.markdown("**📸 Proof of Work / Demo Screenshots** *(Optional)*")
st.caption("Each screenshot gets its own slide appended after the main deck.")

proof_files = st.file_uploader(
    "Upload screenshots",
    type=["png", "jpg", "jpeg", "webp", "gif", "bmp"],
    accept_multiple_files=True, key="proof_upload",
    help="Each screenshot gets its own slide. Aspect ratio is preserved.")
proof_caption = st.text_input(
    "Caption / label for these screenshots (optional)",
    placeholder="e.g. Live demo on staging — May 2026",
    key="proof_caption_input")
if proof_files:
    st.info(f"{len(proof_files)} screenshot(s) uploaded — will be appended as proof slides after the main deck.")

# ─── STEP 2: SELECT LEADER ───
st.markdown('<p class="step-header">Step 2: Select Audience</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])

with col1:
    leader_key = st.selectbox(
        "Presenting to",
        options=list(profiles.keys()),
        format_func=lambda x: f"{profiles[x]['name']} ({profiles[x]['role']})")

with col2:
    p    = profiles[leader_key]
    prefs = p["content_preferences"]
    vis   = p["visual_preferences"]

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
    extractor = clients["extractor"]
    content   = None

    with st.spinner("🔍 Extracting content from sources…"):

        # ── Primary source ────────────────────────────────────────────────────
        if primary_choice == "📝 Paste Text":
            if pasted_text.strip():
                content = extractor.extract_from_text(pasted_text, paste_context)
            else:
                st.error("Please paste some content in the text area.")
                st.stop()

        elif primary_choice == "📁 Upload File  (Excel / CSV / PDF / Doc)":
            if primary_files:
                paths   = [save_uploaded_file(f) for f in primary_files]
                content = extractor.extract_from_files(paths, primary_file_ctx)
            else:
                st.error("Please upload at least one file.")
                st.stop()

        elif primary_choice == "💡 Enter Topic":
            if topic.strip():
                content = extractor.extract_from_topic(topic, topic_context)
            else:
                st.error("Please enter a presentation topic.")
                st.stop()

        elif primary_choice == "🌐 URL / Webpage":
            if primary_url.strip():
                content = extractor.extract_from_url(primary_url.strip(), primary_url_ctx)
            else:
                st.error("Please enter a URL.")
                st.stop()

        elif primary_choice == "🔄 Update Existing PPT":
            if old_ppt:
                old_ppt_path = save_uploaded_file(old_ppt)
                st.session_state.old_ppt_path = old_ppt_path
                new_paths = [save_uploaded_file(f) for f in new_data_for_ppt] if new_data_for_ppt else []
                content = extractor.extract_from_previous_ppt(
                    old_ppt_path, new_paths, new_text_for_ppt, ppt_update_context)
            else:
                st.error("Please upload the existing PPT file.")
                st.stop()
        else:
            st.session_state.pop("old_ppt_path", None)

        # ── Additional sources — each merged into content ─────────────────────
        if extra_url.strip():
            with st.spinner(f"🌐 Fetching {extra_url.strip()}…"):
                c       = extractor.extract_from_url(extra_url.strip(), extra_url_ctx)
                content = _add(content, c)

        if extra_docs:
            paths   = [save_uploaded_file(f) for f in extra_docs]
            c       = extractor.extract_from_files(paths, "")
            content = _add(content, c)

        if extra_data:
            paths   = [save_uploaded_file(f) for f in extra_data]
            c       = extractor.extract_from_files(paths, "")
            content = _add(content, c)

        if extra_images:
            img_paths = [save_uploaded_file(f) for f in extra_images]
            if content is None:
                content = {}
            content.setdefault("_uploaded_images", []).extend(img_paths)
            if extra_image_ctx.strip():
                img_text = (f"Screenshots uploaded: {', '.join(f.name for f in extra_images)}\n"
                            f"Context: {extra_image_ctx}")
                c       = extractor.extract_from_text(img_text,
                                                       "Incorporate these images into relevant slides.")
                content = merge_content(content, c)

        # ── Integrations ──────────────────────────────────────────────────────
        if github_url.strip():
            with st.spinner("🐙 Reading GitHub repo…"):
                c       = extractor.extract_from_github(github_url.strip(), github_context)
                content = _add(content, c)

        if openproject_url.strip() and openproject_key.strip():
            with st.spinner("📋 Fetching OpenProject tickets…"):
                c       = extractor.extract_from_openproject(
                                openproject_url.strip(), openproject_key.strip(),
                                openproject_project.strip() or None, openproject_context)
                content = _add(content, c)

        if gsheet_url.strip():
            with st.spinner("📊 Reading Google Sheet…"):
                c       = extractor.extract_from_google_sheet(gsheet_url.strip(), gsheet_context)
                content = _add(content, c)

        # ── Gmail ─────────────────────────────────────────────────────────────
        _gmail_sel_ids  = [
            em["threadId"]
            for em in st.session_state.get("gmail_emails", [])
            if st.session_state.get(f"gmail_chk_{em['threadId']}", False)
        ]
        _gmail_focus_ctx = st.session_state.get("gmail_focus", "")

        if _gmail_sel_ids and st.session_state.get("gmail_credentials_json"):
            with st.spinner(f"📧 Fetching {len(_gmail_sel_ids)} email thread(s)…"):
                try:
                    from core.gmail_client import (
                        credentials_from_json as _g_creds_from_json,
                        build_gmail_service as _g_build_svc,
                        get_thread_messages as _g_get_thread,
                        format_emails_for_extraction as _g_fmt,
                        download_attachment as _g_dl_att,
                    )
                    _g_creds   = _g_creds_from_json(st.session_state.gmail_credentials_json)
                    _g_svc     = _g_build_svc(_g_creds)
                    _thread_meta = {
                        em["threadId"]: em
                        for em in st.session_state.get("gmail_emails", [])
                    }
                    _email_data   = []
                    _thread_cache = st.session_state.setdefault("gmail_thread_cache", {})

                    for _tid in _gmail_sel_ids:
                        _meta = _thread_meta.get(_tid, {})
                        if _tid in _thread_cache:
                            _msgs = _thread_cache[_tid]
                        else:
                            try:
                                _msgs = _g_get_thread(_g_svc, _tid)
                                _thread_cache[_tid] = _msgs  # cache for attachment pass below
                            except Exception as _te:
                                st.warning(f"Could not fetch thread {_tid}: {_te}")
                                _msgs = []

                        if _msgs:
                            _first = _msgs[0]
                            _email_data.append({
                                "from":    _first.get("from", _meta.get("from", "")),
                                "subject": _meta.get("subject", "(no subject)"),
                                "date":    _first.get("date", _meta.get("date", "")),
                                "body":    _first.get("body", ""),
                                "replies": _msgs[1:],
                            })

                    # ── Extract email body text ───────────────────────────────
                    if _email_data:
                        _email_text = _g_fmt(_email_data)
                        c           = extractor.extract_from_emails(_email_text, _gmail_focus_ctx)
                        content     = _add(content, c)

                    # ── Extract attachment content ────────────────────────────
                    _all_atts = []
                    for _tid in _gmail_sel_ids:
                        for _msg in _thread_cache.get(_tid, []):
                            _all_atts.extend(_msg.get("attachments", []))

                    if _all_atts:
                        st.spinner(f"📎 Extracting {len(_all_atts)} attachment(s)…")
                        _att_paths = []
                        for _att in _all_atts:
                            try:
                                _bytes    = _g_dl_att(_g_svc, _att)
                                _safe     = re.sub(r"[^A-Za-z0-9._-]", "_", _att["filename"])
                                _att_path = os.path.join(TEMP_DIR, f"gmail_att_{_safe}")
                                with open(_att_path, "wb") as _f:
                                    _f.write(_bytes)
                                _att_paths.append(_att_path)
                            except Exception as _ae:
                                st.warning(f"Could not download '{_att['filename']}': {_ae}")
                        if _att_paths:
                            _att_ctx = (_gmail_focus_ctx or "") + "\nContent extracted from email attachments."
                            c        = extractor.extract_from_files(_att_paths, _att_ctx.strip())
                            content  = _add(content, c)

                except ImportError:
                    st.warning("Gmail packages not installed — skipping email extraction.")
                except Exception as _ge:
                    st.warning(f"Gmail extraction failed: {_ge}")

        if content is None:
            st.error("No content could be extracted. Please check your inputs and try again.")
            st.stop()

        st.session_state.content = content

    with st.spinner("📋 Designing narrative strategy for " + p["name"] + "…"):
        # Collect every context/instruction the user typed across all inputs
        user_instructions = "\n".join(filter(None, [
            paste_context, primary_file_ctx, topic_context,
            primary_url_ctx, ppt_update_context, new_text_for_ppt,
            extra_url_ctx, extra_image_ctx,
            github_context, openproject_context, gsheet_context,
            st.session_state.get("gmail_focus", ""),
        ]))

        plan = clients["agent"].plan(
            content, profiles[leader_key],
            user_instructions=user_instructions,
        )
        st.session_state.plan       = plan
        st.session_state.leader_key = leader_key

        if proof_files:
            st.session_state.proof_paths   = [save_uploaded_file(f) for f in proof_files]
            st.session_state.proof_caption = proof_caption
        else:
            st.session_state.proof_paths   = []
            st.session_state.proof_caption = ""

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
            updated_slide["title"]      = new_title
            updated_slide["slide_type"] = slide_type
            edited_plan.append(updated_slide)

    st.session_state.edited_plan = edited_plan
    st.info(f"📝 {len(edited_plan)} slides will be generated")

    # ─── STEP 5: GENERATE PPT ───
    st.markdown('<p class="step-header">Step 5: Generate Presentation</p>', unsafe_allow_html=True)

    if st.button("⚡ Generate PPT", type="primary", use_container_width=True):
        profile  = profiles[st.session_state.leader_key]
        plan     = st.session_state.edited_plan
        content  = st.session_state.content

        progress    = st.progress(0, text="Starting generation…")
        total_steps = len(plan) + 2

        progress.progress(1 / total_steps, text="Generating full deck content with AI…")
        slide_contents = clients["agent"].generate_all(plan, content, profile)

        chart_paths   = {}
        diagram_paths = {}

        for i, (plan_item, slide_content) in enumerate(zip(plan, slide_contents)):
            step = i + 2
            progress.progress(step / total_steps,
                              text=f"Processing slide {i + 1}/{len(plan)}…")

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
                    spec     = slide_content["diagram_spec"]
                    img_path = clients["diagram_gen"].generate_placeholder_image(
                        spec, f"diagram_{plan_item['slide_number']}.png")
                    diagram_paths[plan_item["slide_number"]] = img_path
                except Exception as e:
                    st.warning(f"Diagram generation failed for slide {plan_item['slide_number']}: {e}")

        progress.progress((total_steps - 1) / total_steps, text="Rendering PPT…")
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

        proof_paths   = st.session_state.get("proof_paths", [])
        proof_caption = st.session_state.get("proof_caption", "")
        if proof_paths:
            progress.progress((total_steps - 1) / total_steps,
                              text=f"Adding {len(proof_paths)} proof screenshot(s)…")
            for idx, img_path in enumerate(proof_paths, start=1):
                renderer.add_proof_slide(
                    image_path=img_path,
                    caption=proof_caption,
                    index=idx,
                    total=len(proof_paths))

        timestamp       = datetime.now().strftime("%Y%m%d_%H%M%S")
        leader_name     = profile["name"].replace(" ", "_")
        output_filename = f"presentation_{leader_name}_{timestamp}.pptx"
        output_path     = os.path.join(OUTPUT_DIR, output_filename)
        renderer.save(output_path)

        st.session_state.output_path     = output_path
        st.session_state.output_filename = output_filename

        progress.progress(1.0, text="Done!")

        total_slides = len(plan) + len(proof_paths)
        st.success(f"Presentation generated: {total_slides} slides for {profile['name']}"
                   + (f" (incl. {len(proof_paths)} proof slide(s))" if proof_paths else ""))

        col_dl, col_pv = st.columns(2)
        with col_dl:
            with open(output_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download Presentation",
                    data=f,
                    file_name=output_filename,
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    type="primary",
                    use_container_width=True)
        with col_pv:
            if st.button("👁️ Preview in Browser", type="secondary", use_container_width=True):
                st.session_state.show_preview = True

        st.markdown("---")
        st.markdown("### Generate for Another Leader")
        st.markdown("Change the leader in Step 2 and click **Generate PPT** again — same content, different style!")

        with st.expander("View Generated Slide Content", expanded=False):
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

# ─── IN-BROWSER SLIDE PREVIEW ────────────────────────────────────────────────
if st.session_state.get("show_preview") and st.session_state.get("output_path"):
    out_path = st.session_state.output_path
    out_name = st.session_state.get("output_filename", "presentation.pptx")

    st.markdown("---")
    st.markdown("## Slide Preview")

    col_hdr, col_close = st.columns([5, 1])
    with col_hdr:
        st.caption(f"Previewing: **{out_name}**")
    with col_close:
        if st.button("✕ Close", use_container_width=True):
            st.session_state.show_preview = False
            st.rerun()

    if not os.path.exists(out_path):
        st.warning("Presentation file not found. Please regenerate.")
    else:
        with st.spinner("Rendering slide previews…"):
            from utils.preview_generator import generate_previews
            preview_dir   = os.path.join(
                TEMP_DIR,
                "preview_" + os.path.splitext(os.path.basename(out_path))[0])
            preview_paths = generate_previews(out_path, preview_dir)

        if not preview_paths:
            st.warning("Could not render previews. Please download and open in PowerPoint.")
        else:
            total_p = len(preview_paths)
            st.caption(f"{total_p} slide(s) — 2 per row")

            PER_PAGE = 10
            page_key = "preview_page"
            if page_key not in st.session_state:
                st.session_state[page_key] = 0

            page      = st.session_state[page_key]
            start     = page * PER_PAGE
            end       = min(start + PER_PAGE, total_p)
            page_imgs = preview_paths[start:end]

            for row_start in range(0, len(page_imgs), 2):
                cols = st.columns(2)
                for ci, col in enumerate(cols):
                    idx = row_start + ci
                    if idx < len(page_imgs):
                        with col:
                            st.image(
                                page_imgs[idx],
                                caption=f"Slide {start + idx + 1}",
                                use_container_width=True)

            if total_p > PER_PAGE:
                max_page = (total_p - 1) // PER_PAGE
                p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
                with p_col1:
                    if page > 0:
                        if st.button("← Prev", use_container_width=True):
                            st.session_state[page_key] -= 1
                            st.rerun()
                with p_col2:
                    st.markdown(
                        f"<div style='text-align:center;padding-top:6px'>"
                        f"Page {page + 1} / {max_page + 1}</div>",
                        unsafe_allow_html=True)
                with p_col3:
                    if page < max_page:
                        if st.button("Next →", use_container_width=True):
                            st.session_state[page_key] += 1
                            st.rerun()
