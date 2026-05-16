"""
Indiamart PPT Generator — FastAPI backend
Run: python main.py  →  http://localhost:8000
"""
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import uvicorn
import yaml
from fastapi import Cookie, FastAPI, Form, Request, Response, UploadFile
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from utils.claude_client import ClaudeClient
from core.content_extractor import ContentExtractor
from core.ppt_agent import PPTAgent
from core.chart_generator import ChartGenerator
from core.diagram_generator import DiagramGenerator
from core.ppt_renderer import PPTRenderer

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
PROFILES_DIR = BASE_DIR / "profiles"
OUTPUT_DIR   = BASE_DIR / "output"
TEMP_DIR     = BASE_DIR / "temp"
STATIC_DIR   = BASE_DIR / "static"
CREDENTIALS_PATH = BASE_DIR / "credentials.json"

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

GMAIL_REDIRECT_URI = "http://localhost:8000/auth/gmail/callback"
TOKEN_PATH          = BASE_DIR / "token.json"
GATEWAY_CONFIG_PATH = BASE_DIR / "gateway_config.json"

def _save_gateway_config(url: str, key: str, model: str):
    try:
        GATEWAY_CONFIG_PATH.write_text(
            json.dumps({"gateway_url": url, "api_key": key, "model_name": model}),
            encoding="utf-8")
    except Exception:
        pass

def _load_gateway_config() -> dict:
    try:
        if GATEWAY_CONFIG_PATH.exists():
            return json.loads(GATEWAY_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}

def _save_token(creds_json: str, email: str):
    """Persist Gmail credentials to disk so they survive server restarts."""
    try:
        TOKEN_PATH.write_text(json.dumps({"credentials_json": creds_json, "email": email}),
                              encoding="utf-8")
    except Exception:
        pass

def _load_token() -> tuple[str, str]:
    """Load persisted Gmail credentials. Returns (credentials_json, email) or ('', '')."""
    try:
        if TOKEN_PATH.exists():
            data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
            return data.get("credentials_json", ""), data.get("email", "")
    except Exception:
        pass
    return "", ""

def _delete_token():
    try:
        TOKEN_PATH.unlink(missing_ok=True)
    except Exception:
        pass

# ── In-memory session store ────────────────────────────────────────────────────
_sessions: dict[str, dict] = {}
MAX_SESSIONS = 10

def _new_session() -> dict:
    saved = _load_gateway_config()
    return {
        "gateway_url": saved.get("gateway_url", "https://imllm.intermesh.net/v1"),
        "api_key":     saved.get("api_key",     "-----"),
        "model_name":  saved.get("model_name",  "google/gemini-3-flash-preview"),
        "gmail_creds_data": None,
        "gmail_oauth_state": "",
        "gmail_credentials_json": "",
        "gmail_user_email": "",
        "gmail_emails": [],
        "gmail_thread_cache": {},
        "clients": None,
        "content": None,
        "plan": [],
        "proof_paths": [],
        "proof_caption": "",
        "old_ppt_path": "",
        "output_path": "",
        "output_filename": "",
        "preview_paths": [],
    }

def get_session(sid: str) -> dict:
    if sid not in _sessions:
        if len(_sessions) >= MAX_SESSIONS:
            oldest = next(iter(_sessions))
            del _sessions[oldest]
        _sessions[sid] = _new_session()
    return _sessions[sid]

# ── Background job runner ──────────────────────────────────────────────────────
_jobs: dict[str, dict] = {}
_executor = ThreadPoolExecutor(max_workers=2)

def _run_job(jid: str, fn, *args):
    try:
        fn(_jobs[jid], *args)
    except Exception as exc:
        _jobs[jid].update({"status": "error", "error": str(exc), "progress": 0})

def submit_job(fn, *args) -> str:
    jid = str(uuid.uuid4())
    _jobs[jid] = {"status": "running", "progress": 0, "progress_text": "Starting…", "result": None, "error": None}
    _executor.submit(_run_job, jid, fn, *args)
    return jid

# ── Session middleware ─────────────────────────────────────────────────────────
class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        sid = request.cookies.get("ppt_sid")
        new_cookie = not sid
        if not sid:
            sid = str(uuid.uuid4())
        request.state.session = get_session(sid)
        request.state.sid = sid
        response = await call_next(request)
        if new_cookie:
            response.set_cookie("ppt_sid", sid, httponly=True, samesite="lax")
        return response

# ── Helpers ────────────────────────────────────────────────────────────────────
def load_profiles() -> dict:
    profiles = {}
    for f in PROFILES_DIR.iterdir():
        if f.suffix in (".yml", ".yaml") and not f.name.startswith("Copy"):
            with open(f, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
                profiles[f.stem] = data
    return profiles

def init_clients(api_key: str, base_url: str, model: str) -> dict:
    claude = ClaudeClient(api_key=api_key, base_url=base_url, model=model)
    return {
        "claude": claude,
        "extractor": ContentExtractor(claude),
        "agent": PPTAgent(claude),
        "chart_gen": ChartGenerator(str(TEMP_DIR)),
        "diagram_gen": DiagramGenerator(claude, str(TEMP_DIR)),
    }

def merge_content(base: dict, addition: dict) -> dict:
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

def _add(content, addition):
    return merge_content(content, addition) if content else addition

async def save_upload(file: UploadFile) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", file.filename)
    path = str(TEMP_DIR / safe)
    data = await file.read()
    with open(path, "wb") as f:
        f.write(data)
    return path

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(title="Indiamart PPT Generator")
app.add_middleware(SessionMiddleware)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# ── Static page ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))

# ── Profiles ──────────────────────────────────────────────────────────────────
@app.get("/api/profiles")
async def api_profiles():
    return {"profiles": load_profiles()}

# ── Config ────────────────────────────────────────────────────────────────────
@app.post("/api/config")
async def api_config_save(request: Request):
    body = await request.json()
    sess = request.state.session
    url   = body.get("gateway_url", "")
    key   = body.get("api_key", "")
    model = body.get("model_name", "")
    sess["gateway_url"] = url
    sess["api_key"]     = key
    sess["model_name"]  = model
    sess["clients"]     = None  # force re-init on next analyze
    _save_gateway_config(url, key, model)
    return {"ok": True}

@app.get("/api/config")
async def api_config_get(request: Request):
    sess = request.state.session
    return {
        "gateway_url": sess.get("gateway_url", ""),
        "api_key":     sess.get("api_key", ""),
        "model_name":  sess.get("model_name", ""),
        "configured":  bool(sess.get("api_key") and sess.get("gateway_url")),
    }

# ── Gmail ──────────────────────────────────────────────────────────────────────
@app.get("/api/gmail/status")
async def gmail_status(request: Request):
    sess = request.state.session

    # Auto-load OAuth credentials.json (the app credentials) from disk
    if not sess.get("gmail_creds_data") and CREDENTIALS_PATH.exists():
        try:
            raw = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
            if "installed" in raw or "web" in raw:
                sess["gmail_creds_data"] = raw
        except Exception:
            pass

    # Auto-load persisted user token from token.json (survives page refresh / server restart)
    if not sess.get("gmail_credentials_json"):
        creds_json, email = _load_token()
        if creds_json:
            sess["gmail_credentials_json"] = creds_json
            sess["gmail_user_email"] = email

    return {
        "connected":             bool(sess.get("gmail_credentials_json")),
        "email":                 sess.get("gmail_user_email", ""),
        "has_credentials_file":  bool(sess.get("gmail_creds_data")),
    }

@app.post("/api/gmail/upload-credentials")
async def gmail_upload_creds(request: Request, file: UploadFile):
    sess = request.state.session
    try:
        raw = json.loads((await file.read()).decode("utf-8"))
        if "installed" not in raw and "web" not in raw:
            return JSONResponse({"error": "Invalid credentials.json — must contain 'installed' or 'web' key."}, status_code=400)
        sess["gmail_creds_data"] = raw
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

@app.post("/api/gmail/auth-url")
async def gmail_auth_url(request: Request):
    sess = request.state.session
    creds_data = sess.get("gmail_creds_data")
    if not creds_data:
        return JSONResponse({"error": "No credentials.json loaded"}, status_code=400)
    try:
        from core.gmail_client import get_auth_url
        auth_url, state, code_verifier = get_auth_url(creds_data, GMAIL_REDIRECT_URI)
        sess["gmail_oauth_state"]    = state
        sess["gmail_code_verifier"]  = code_verifier
        return {"auth_url": auth_url}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/auth/gmail/callback")
async def gmail_callback(request: Request, code: str = None, state: str = None, error: str = None):
    sess = request.state.session
    if error:
        return RedirectResponse(url=f"/?gmail_error={error}")
    if not code or not state:
        return RedirectResponse(url="/")
    if state != sess.get("gmail_oauth_state"):
        return RedirectResponse(url="/")
    try:
        from core.gmail_client import (exchange_code, credentials_to_json,
                                        build_gmail_service, get_user_profile)
        creds_data = sess.get("gmail_creds_data")
        if not creds_data:
            return RedirectResponse(url="/?gmail_error=no_credentials")
        code_verifier = sess.get("gmail_code_verifier", "")
        creds = exchange_code(creds_data, code, state, GMAIL_REDIRECT_URI,
                              code_verifier=code_verifier or None)
        creds_json = credentials_to_json(creds)
        svc = build_gmail_service(creds)
        profile = get_user_profile(svc)
        email = profile.get("email", "connected")
        sess["gmail_credentials_json"] = creds_json
        sess["gmail_user_email"] = email
        sess["gmail_code_verifier"] = ""
        sess["gmail_oauth_state"] = ""
        _save_token(creds_json, email)  # persist to disk
    except Exception as e:
        return RedirectResponse(url=f"/?gmail_error={str(e)[:80]}")
    return RedirectResponse(url="/?gmail_connected=true")

@app.post("/api/gmail/disconnect")
async def gmail_disconnect(request: Request):
    sess = request.state.session
    for key in ["gmail_credentials_json", "gmail_user_email", "gmail_oauth_state",
                "gmail_emails", "gmail_thread_cache", "gmail_creds_data"]:
        sess[key] = None if key == "gmail_creds_data" else "" if isinstance(sess.get(key), str) else ([] if isinstance(sess.get(key), list) else {})
    _delete_token()  # remove persisted token from disk
    return {"ok": True}

@app.post("/api/gmail/search")
async def gmail_search(request: Request):
    sess = request.state.session
    if not sess.get("gmail_credentials_json"):
        return JSONResponse({"error": "Not connected"}, status_code=401)
    body = await request.json()
    try:
        from core.gmail_client import (credentials_from_json, build_gmail_service,
                                        build_query, list_emails)
        creds = credentials_from_json(sess["gmail_credentials_json"])
        svc   = build_gmail_service(creds)
        query = build_query(
            keyword=body.get("keyword", ""),
            from_email=body.get("from_email", ""),
            after_date=body.get("after_date"),
            before_date=body.get("before_date"),
            label=body.get("label", "All"),
        )
        emails = list_emails(svc, query, max_results=int(body.get("max_results", 25)))
        sess["gmail_emails"] = emails
        # Update stored credentials if refreshed
        try:
            from core.gmail_client import credentials_to_json
            sess["gmail_credentials_json"] = credentials_to_json(creds)
        except Exception:
            pass
        return {"emails": emails}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/gmail/thread/{thread_id}")
async def gmail_thread(request: Request, thread_id: str):
    sess = request.state.session
    if not sess.get("gmail_credentials_json"):
        return JSONResponse({"error": "Not connected"}, status_code=401)
    cache = sess.setdefault("gmail_thread_cache", {})
    if thread_id in cache:
        return {"messages": cache[thread_id]}
    try:
        from core.gmail_client import credentials_from_json, build_gmail_service, get_thread_messages
        creds = credentials_from_json(sess["gmail_credentials_json"])
        svc   = build_gmail_service(creds)
        msgs  = get_thread_messages(svc, thread_id)
        cache[thread_id] = msgs
        return {"messages": msgs}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

# ── Job status ─────────────────────────────────────────────────────────────────
@app.get("/api/job/{job_id}")
async def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job

# ── Analyze ────────────────────────────────────────────────────────────────────
@app.post("/api/analyze", status_code=202)
async def api_analyze(
    request: Request,
    # Text fields
    primary_mode:          Optional[str]  = Form(None),
    pasted_text:           Optional[str]  = Form(None),
    paste_context:         Optional[str]  = Form(None),
    topic:                 Optional[str]  = Form(None),
    topic_context:         Optional[str]  = Form(None),
    primary_url:           Optional[str]  = Form(None),
    primary_url_ctx:       Optional[str]  = Form(None),
    new_text_for_ppt:      Optional[str]  = Form(None),
    ppt_update_context:    Optional[str]  = Form(None),
    extra_url:             Optional[str]  = Form(None),
    extra_url_ctx:         Optional[str]  = Form(None),
    extra_image_ctx:       Optional[str]  = Form(None),
    github_url:            Optional[str]  = Form(None),
    github_context:        Optional[str]  = Form(None),
    openproject_url:       Optional[str]  = Form(None),
    openproject_project:   Optional[str]  = Form(None),
    openproject_key:       Optional[str]  = Form(None),
    openproject_context:   Optional[str]  = Form(None),
    gsheet_url:            Optional[str]  = Form(None),
    gsheet_context:        Optional[str]  = Form(None),
    gmail_selected_ids:    Optional[str]  = Form(None),
    gmail_focus:           Optional[str]  = Form(None),
    proof_caption:         Optional[str]  = Form(None),
    leader_key:            Optional[str]  = Form(None),
    # File fields
    primary_files:  List[UploadFile] = Form(default=[]),
    old_ppt:        List[UploadFile] = Form(default=[]),
    new_data_files: List[UploadFile] = Form(default=[]),
    extra_docs:     List[UploadFile] = Form(default=[]),
    extra_images:   List[UploadFile] = Form(default=[]),
    extra_data:     List[UploadFile] = Form(default=[]),
    proof_files:    List[UploadFile] = Form(default=[]),
):
    sess = request.state.session

    # Save all uploaded files to disk before handing off to background thread
    primary_paths  = [await save_upload(f) for f in primary_files  if f.filename]
    old_ppt_paths  = [await save_upload(f) for f in old_ppt        if f.filename]
    new_data_paths = [await save_upload(f) for f in new_data_files  if f.filename]
    extra_doc_paths  = [await save_upload(f) for f in extra_docs   if f.filename]
    extra_img_paths  = [await save_upload(f) for f in extra_images if f.filename]
    extra_data_paths = [await save_upload(f) for f in extra_data   if f.filename]
    proof_paths      = [await save_upload(f) for f in proof_files  if f.filename]

    gmail_ids = []
    if gmail_selected_ids:
        try:
            gmail_ids = json.loads(gmail_selected_ids)
        except Exception:
            pass

    inputs = {
        "primary_mode":        primary_mode or "text",
        "pasted_text":         pasted_text or "",
        "paste_context":       paste_context or "",
        "topic":               topic or "",
        "topic_context":       topic_context or "",
        "primary_url":         primary_url or "",
        "primary_url_ctx":     primary_url_ctx or "",
        "new_text_for_ppt":    new_text_for_ppt or "",
        "ppt_update_context":  ppt_update_context or "",
        "extra_url":           extra_url or "",
        "extra_url_ctx":       extra_url_ctx or "",
        "extra_image_ctx":     extra_image_ctx or "",
        "github_url":          github_url or "",
        "github_context":      github_context or "",
        "openproject_url":     openproject_url or "",
        "openproject_project": openproject_project or "",
        "openproject_key":     openproject_key or "",
        "openproject_context": openproject_context or "",
        "gsheet_url":          gsheet_url or "",
        "gsheet_context":      gsheet_context or "",
        "gmail_selected_ids":  gmail_ids,
        "gmail_focus":         gmail_focus or "",
        "proof_caption":       proof_caption or "",
        "leader_key":          leader_key or list(load_profiles().keys())[0],
        # Paths
        "primary_paths":     primary_paths,
        "old_ppt_path":      old_ppt_paths[0] if old_ppt_paths else "",
        "new_data_paths":    new_data_paths,
        "extra_doc_paths":   extra_doc_paths,
        "extra_img_paths":   extra_img_paths,
        "extra_data_paths":  extra_data_paths,
        "proof_paths":       proof_paths,
    }

    jid = submit_job(_run_analyze, inputs, sess)
    return {"job_id": jid}

def _run_analyze(job: dict, inputs: dict, sess: dict):
    def upd(pct, txt):
        job["progress"] = pct
        job["progress_text"] = txt

    upd(3, "Initialising…")
    profiles = load_profiles()
    leader_key = inputs["leader_key"]
    profile = profiles.get(leader_key, list(profiles.values())[0])

    api_key     = sess.get("api_key", "")
    gateway_url = sess.get("gateway_url", "")
    model_name  = sess.get("model_name", "")

    if not api_key or not gateway_url:
        job.update({"status": "error", "error": "LLM gateway not configured. Set URL and API key first."})
        return

    clients = init_clients(api_key, gateway_url, model_name)
    extractor = clients["extractor"]
    content = None

    # ── Primary source ────────────────────────────────────────────────────────
    upd(5, "Extracting primary source…")
    mode = inputs["primary_mode"]

    # Gmail threads alone are a valid source — only require primary source if no Gmail selected
    has_gmail = bool(inputs.get("gmail_selected_ids"))

    if mode == "text":
        if inputs["pasted_text"].strip():
            content = extractor.extract_from_text(inputs["pasted_text"], inputs["paste_context"])
        elif not has_gmail:
            job.update({"status": "error", "error": "Please paste some content, or select emails from Gmail."}); return

    elif mode == "files":
        if inputs["primary_paths"]:
            content = extractor.extract_from_files(inputs["primary_paths"], inputs["primary_url_ctx"] or "")
        elif not has_gmail:
            job.update({"status": "error", "error": "Please upload at least one file."}); return

    elif mode == "topic":
        if inputs["topic"].strip():
            content = extractor.extract_from_topic(inputs["topic"], inputs["topic_context"])
        elif not has_gmail:
            job.update({"status": "error", "error": "Please enter a presentation topic."}); return

    elif mode == "url":
        if inputs["primary_url"].strip():
            content = extractor.extract_from_url(inputs["primary_url"].strip(), inputs["primary_url_ctx"])
        elif not has_gmail:
            job.update({"status": "error", "error": "Please enter a URL."}); return

    elif mode == "update_ppt":
        if inputs["old_ppt_path"]:
            sess["old_ppt_path"] = inputs["old_ppt_path"]
            content = extractor.extract_from_previous_ppt(
                inputs["old_ppt_path"],
                inputs["new_data_paths"],
                inputs["new_text_for_ppt"],
                inputs["ppt_update_context"],
            )
        elif not has_gmail:
            job.update({"status": "error", "error": "Please upload the existing PPT file."}); return

    # ── Additional sources ────────────────────────────────────────────────────
    if inputs["extra_url"].strip():
        upd(20, f"Fetching {inputs['extra_url'].strip()[:50]}…")
        c = extractor.extract_from_url(inputs["extra_url"].strip(), inputs["extra_url_ctx"])
        content = _add(content, c)

    if inputs["extra_doc_paths"]:
        upd(30, "Processing extra documents…")
        c = extractor.extract_from_files(inputs["extra_doc_paths"], "")
        content = _add(content, c)

    if inputs["extra_data_paths"]:
        upd(40, "Processing extra data files…")
        c = extractor.extract_from_files(inputs["extra_data_paths"], "")
        content = _add(content, c)

    if inputs["extra_img_paths"]:
        upd(50, "Processing images…")
        if content is None:
            content = {}
        content.setdefault("_uploaded_images", []).extend(inputs["extra_img_paths"])
        if inputs["extra_image_ctx"].strip():
            img_names = [os.path.basename(p) for p in inputs["extra_img_paths"]]
            img_text = f"Screenshots uploaded: {', '.join(img_names)}\nContext: {inputs['extra_image_ctx']}"
            c = extractor.extract_from_text(img_text, "Incorporate these images into relevant slides.")
            content = merge_content(content, c)

    # ── Integrations ──────────────────────────────────────────────────────────
    upd(60, "Fetching integrations…")
    if inputs["github_url"].strip():
        c = extractor.extract_from_github(inputs["github_url"].strip(), inputs["github_context"])
        content = _add(content, c)

    if inputs["openproject_url"].strip() and inputs["openproject_key"].strip():
        c = extractor.extract_from_openproject(
            inputs["openproject_url"].strip(), inputs["openproject_key"].strip(),
            inputs["openproject_project"].strip() or None, inputs["openproject_context"],
        )
        content = _add(content, c)

    if inputs["gsheet_url"].strip():
        c = extractor.extract_from_google_sheet(inputs["gsheet_url"].strip(), inputs["gsheet_context"])
        content = _add(content, c)

    # ── Gmail ─────────────────────────────────────────────────────────────────
    gmail_ids = inputs.get("gmail_selected_ids", [])
    if gmail_ids and sess.get("gmail_credentials_json"):
        upd(75, f"Fetching {len(gmail_ids)} email thread(s)…")
        try:
            from core.gmail_client import (
                credentials_from_json, build_gmail_service,
                get_thread_messages, format_emails_for_extraction, download_attachment,
            )
            creds = credentials_from_json(sess["gmail_credentials_json"])
            svc   = build_gmail_service(creds)
            thread_meta = {em["threadId"]: em for em in sess.get("gmail_emails", [])}
            email_data  = []
            tcache = sess.setdefault("gmail_thread_cache", {})

            for tid in gmail_ids:
                meta = thread_meta.get(tid, {})
                if tid in tcache:
                    msgs = tcache[tid]
                else:
                    try:
                        msgs = get_thread_messages(svc, tid)
                        tcache[tid] = msgs
                    except Exception:
                        msgs = []
                if msgs:
                    first = msgs[0]
                    email_data.append({
                        "from":    first.get("from", meta.get("from", "")),
                        "subject": meta.get("subject", "(no subject)"),
                        "date":    first.get("date", meta.get("date", "")),
                        "body":    first.get("body", ""),
                        "replies": msgs[1:],
                    })

            if email_data:
                email_text = format_emails_for_extraction(email_data)
                c = extractor.extract_from_emails(email_text, inputs.get("gmail_focus", ""))
                content = _add(content, c)

            # Attachments
            all_atts = []
            for tid in gmail_ids:
                for msg in tcache.get(tid, []):
                    all_atts.extend(msg.get("attachments", []))
            if all_atts:
                att_paths = []
                for att in all_atts:
                    try:
                        data  = download_attachment(svc, att)
                        safe  = re.sub(r"[^A-Za-z0-9._-]", "_", att["filename"])
                        apath = str(TEMP_DIR / f"gmail_att_{safe}")
                        with open(apath, "wb") as f:
                            f.write(data)
                        att_paths.append(apath)
                    except Exception:
                        pass
                if att_paths:
                    att_ctx = (inputs.get("gmail_focus", "") or "") + "\nContent extracted from email attachments."
                    c = extractor.extract_from_files(att_paths, att_ctx.strip())
                    content = _add(content, c)
        except ImportError:
            pass  # Gmail packages not installed — skip
        except Exception as ge:
            job["progress_text"] = f"Gmail extraction warning: {ge}"

    if content is None:
        job.update({"status": "error", "error": "No content could be extracted. Check your inputs."}); return

    # ── Build plan ────────────────────────────────────────────────────────────
    upd(85, f"Designing slide strategy for {profile['name']}…")

    user_instructions = "\n".join(filter(None, [
        inputs["paste_context"], inputs["primary_url_ctx"], inputs["topic_context"],
        inputs["ppt_update_context"], inputs["new_text_for_ppt"],
        inputs["extra_url_ctx"], inputs["extra_image_ctx"],
        inputs["github_context"], inputs["openproject_context"], inputs["gsheet_context"],
        inputs.get("gmail_focus", ""),
    ]))

    plan = clients["agent"].plan(content, profile, user_instructions=user_instructions)

    # Store proof paths
    sess["proof_paths"]  = inputs["proof_paths"]
    sess["proof_caption"] = inputs["proof_caption"]
    sess["content"]      = content
    sess["plan"]         = plan
    sess["clients"]      = clients

    job["progress"]      = 100
    job["progress_text"] = f"✅ Plan ready: {len(plan)} slides"
    job["status"]        = "done"
    job["result"]        = {"plan": plan, "leader_key": leader_key}

# ── Generate ───────────────────────────────────────────────────────────────────
@app.post("/api/generate", status_code=202)
async def api_generate(request: Request):
    sess = request.state.session
    body = await request.json()
    edited_plan = body.get("edited_plan", [])
    leader_key  = body.get("leader_key", "")

    if not sess.get("content"):
        return JSONResponse({"error": "No content in session. Run analyze first."}, status_code=400)

    jid = submit_job(_run_generate, edited_plan, leader_key, sess)
    return {"job_id": jid}

def _run_generate(job: dict, edited_plan: list, leader_key: str, sess: dict):
    def upd(pct, txt):
        job["progress"] = pct
        job["progress_text"] = txt

    profiles = load_profiles()
    profile  = profiles.get(leader_key, list(profiles.values())[0])
    content  = sess["content"]
    clients  = sess.get("clients")

    if not clients:
        api_key     = sess.get("api_key", "")
        gateway_url = sess.get("gateway_url", "")
        model_name  = sess.get("model_name", "")
        clients = init_clients(api_key, gateway_url, model_name)

    upd(10, "Generating full deck content with AI…")
    slide_contents = clients["agent"].generate_all(edited_plan, content, profile)

    # LLM may return fewer slides than requested (token limit truncation).
    # Pad with minimal placeholder dicts so zip() never silently drops plan items.
    while len(slide_contents) < len(edited_plan):
        missing_idx = len(slide_contents)
        plan_item   = edited_plan[missing_idx]
        slide_contents.append({
            "title":         plan_item.get("title", f"Slide {plan_item.get('slide_number', missing_idx + 1)}"),
            "subtitle":      "",
            "bullets":       ["Content could not be generated — please edit in PowerPoint."],
            "key_callout":   "",
            "speaker_notes": "",
            "slide_number":  plan_item.get("slide_number", missing_idx + 1),
            "slide_type":    plan_item.get("slide_type", "content"),
            "layout":        plan_item.get("layout", "bullets"),
        })

    chart_paths   = {}
    diagram_paths = {}
    total = len(edited_plan)

    for i, (plan_item, slide_content) in enumerate(zip(edited_plan, slide_contents)):
        sn   = plan_item["slide_number"]
        pct  = 10 + int((i + 1) / total * 75)
        upd(pct, f"Processing slide {i + 1}/{total}…")

        if slide_content.get("chart_spec"):
            try:
                path = clients["chart_gen"].generate(
                    slide_content["chart_spec"], f"chart_{sn}.png")
                chart_paths[sn] = path
            except Exception:
                pass

        if slide_content.get("diagram_spec"):
            try:
                img_path = clients["diagram_gen"].generate_placeholder_image(
                    slide_content["diagram_spec"], f"diagram_{sn}.png")
                diagram_paths[sn] = img_path
            except Exception:
                pass

    upd(90, "Rendering PPT…")
    renderer = PPTRenderer(profile)

    for plan_item, slide_content in zip(edited_plan, slide_contents):
        sn = plan_item["slide_number"]
        if plan_item["slide_type"] == "title":
            renderer.add_title_slide(
                title=slide_content.get("title", "Presentation"),
                subtitle=slide_content.get("subtitle", ""),
                date=datetime.now().strftime("%B %Y"),
            )
        else:
            renderer.add_content_slide(
                slide_content,
                chart_path=chart_paths.get(sn),
                diagram_path=diagram_paths.get(sn),
            )

    proof_paths   = sess.get("proof_paths", [])
    proof_caption = sess.get("proof_caption", "")
    if proof_paths:
        upd(95, f"Adding {len(proof_paths)} proof screenshot(s)…")
        for idx, img_path in enumerate(proof_paths, start=1):
            renderer.add_proof_slide(
                image_path=img_path, caption=proof_caption,
                index=idx, total=len(proof_paths))

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname       = f"presentation_{profile['name'].replace(' ', '_')}_{timestamp}.pptx"
    output_path = str(OUTPUT_DIR / fname)
    renderer.save(output_path)

    sess["output_path"]     = output_path
    sess["output_filename"] = fname
    sess["preview_paths"]   = []

    # Count slides from the saved file — plan length can diverge if any slide
    # failed to render or the LLM returned fewer items than requested.
    from pptx import Presentation as _Prs
    total_slides = len(_Prs(output_path).slides)
    job["progress"]      = 100
    job["progress_text"] = f"✅ {total_slides} slides generated"
    job["status"]        = "done"
    job["result"]        = {"output_filename": fname, "total_slides": total_slides}

# ── Download ───────────────────────────────────────────────────────────────────
@app.get("/api/download/{filename}")
async def api_download(filename: str):
    # Sanitize filename — no path traversal
    safe = Path(filename).name
    path = OUTPUT_DIR / safe
    if not path.exists():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe,
    )

# ── Preview ────────────────────────────────────────────────────────────────────
@app.post("/api/preview/generate", status_code=202)
async def api_preview_generate(request: Request):
    sess = request.state.session
    body = await request.json()
    filename = body.get("filename", sess.get("output_filename", ""))
    if not filename:
        return JSONResponse({"error": "No filename"}, status_code=400)
    path = str(OUTPUT_DIR / Path(filename).name)
    preview_dir = str(TEMP_DIR / f"preview_{Path(filename).stem}")
    jid = submit_job(_run_preview, path, preview_dir, sess)
    return {"job_id": jid}

def _run_preview(job: dict, pptx_path: str, preview_dir: str, sess: dict):
    job["progress"] = 10
    job["progress_text"] = "Rendering slide previews…"
    from utils.preview_generator import generate_previews
    paths = generate_previews(pptx_path, preview_dir)
    sess["preview_paths"] = paths
    # Convert to URL paths
    rel_paths = []
    for p in paths:
        try:
            rel = Path(p).relative_to(TEMP_DIR)
            rel_paths.append(f"/api/preview-image/{rel.as_posix()}")
        except ValueError:
            rel_paths.append(f"/api/preview-image/{Path(p).name}")
    job["progress"]      = 100
    job["progress_text"] = f"✅ {len(paths)} slides rendered"
    job["status"]        = "done"
    job["result"]        = {"paths": rel_paths, "total": len(rel_paths)}

@app.get("/api/preview/pages")
async def api_preview_pages(request: Request, filename: str = ""):
    sess = request.state.session
    paths = sess.get("preview_paths", [])
    if not paths:
        return {"paths": [], "total": 0}
    rel_paths = []
    for p in paths:
        try:
            rel = Path(p).relative_to(TEMP_DIR)
            rel_paths.append(f"/api/preview-image/{rel.as_posix()}")
        except ValueError:
            rel_paths.append(f"/api/preview-image/{Path(p).name}")
    return {"paths": rel_paths, "total": len(rel_paths)}

@app.get("/api/preview-image/{subpath:path}")
async def api_preview_image(subpath: str):
    # Guard against path traversal
    try:
        target = (TEMP_DIR / subpath).resolve()
        TEMP_DIR.resolve()
        if not str(target).startswith(str(TEMP_DIR.resolve())):
            return JSONResponse({"error": "Forbidden"}, status_code=403)
    except Exception:
        return JSONResponse({"error": "Invalid path"}, status_code=400)
    if not target.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(target), media_type="image/png")

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
