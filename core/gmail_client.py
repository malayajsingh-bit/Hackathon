import base64
import json
import os
import re
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

SUPPORTED_ATTACHMENT_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
}
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


def get_auth_url(creds_data: dict, redirect_uri: str) -> tuple[str, str, str]:
    """Returns (auth_url, state, code_verifier). Store code_verifier in session for the callback."""
    import secrets, hashlib, base64
    code_verifier = secrets.token_urlsafe(96)
    flow = Flow.from_client_config(creds_data, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    flow.code_verifier = code_verifier
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state, code_verifier


def exchange_code(creds_data: dict, code: str, state: str, redirect_uri: str,
                  code_verifier: str = None) -> Credentials:
    flow = Flow.from_client_config(creds_data, scopes=SCOPES, state=state)
    flow.redirect_uri = redirect_uri
    if code_verifier:
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    return flow.credentials


def credentials_to_json(credentials: Credentials) -> str:
    return json.dumps({
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else [],
    })


def credentials_from_json(creds_json: str) -> Credentials:
    data = json.loads(creds_json)
    return Credentials(
        token=data["token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data.get("scopes"),
    )


def build_gmail_service(credentials: Credentials):
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    return build("gmail", "v1", credentials=credentials)


def get_user_profile(service) -> dict:
    try:
        return service.users().getProfile(userId="me").execute()
    except HttpError as e:
        return {"email": "unknown", "error": str(e)}


def build_query(
    keyword: str = "",
    from_email: str = "",
    after_date: Optional[str] = None,
    before_date: Optional[str] = None,
    label: str = "All",
) -> str:
    parts = []
    if keyword.strip():
        parts.append(keyword.strip())
    if from_email.strip():
        parts.append(f"from:{from_email.strip()}")
    if after_date:
        parts.append(f"after:{str(after_date).replace('-', '/')}")
    if before_date:
        parts.append(f"before:{str(before_date).replace('-', '/')}")
    label_map = {
        "Inbox": "in:inbox",
        "Sent": "in:sent",
        "Starred": "is:starred",
        "Important": "is:important",
    }
    if label in label_map:
        parts.append(label_map[label])
    return " ".join(parts) if parts else "in:inbox"


def _parse_headers(headers: list) -> dict:
    return {h["name"]: h["value"] for h in headers}


def _format_date(raw_date: str) -> str:
    return raw_date.split(" (")[0].strip() if raw_date else ""


def list_emails(service, query: str, max_results: int = 25) -> list[dict]:
    """Search Gmail threads, return list of summary dicts."""
    try:
        result = service.users().threads().list(
            userId="me", q=query, maxResults=max_results
        ).execute()
    except HttpError:
        return []

    emails = []
    for thread_item in result.get("threads", []):
        tid = thread_item["id"]
        try:
            thread = service.users().threads().get(
                userId="me",
                id=tid,
                format="metadata",
                metadataHeaders=["Subject", "From", "Date"],
            ).execute()
        except HttpError:
            continue

        messages = thread.get("messages", [])
        if not messages:
            continue

        first_msg = messages[0]
        headers = _parse_headers(first_msg.get("payload", {}).get("headers", []))

        emails.append({
            "id": first_msg["id"],
            "threadId": tid,
            "subject": headers.get("Subject", "(no subject)"),
            "from": headers.get("From", ""),
            "date": _format_date(headers.get("Date", "")),
            "snippet": first_msg.get("snippet", "")[:200],
            "thread_count": len(messages),
        })

    return emails


def get_thread_messages(service, thread_id: str) -> list[dict]:
    """Fetch all messages in a thread with decoded bodies."""
    try:
        thread = service.users().threads().get(
            userId="me", id=thread_id, format="full"
        ).execute()
    except HttpError as e:
        return [{"from": "", "date": "", "body": f"[Thread fetch error: {e}]", "snippet": ""}]

    result = []
    for msg in thread.get("messages", []):
        payload = msg.get("payload", {})
        headers = _parse_headers(payload.get("headers", []))
        result.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "date": _format_date(headers.get("Date", "")),
            "snippet": msg.get("snippet", "")[:200],
            "body": decode_mime_body(payload),
            "attachments": extract_attachments_from_payload(payload, msg["id"]),
        })
    return result


def decode_mime_body(payload: dict, _depth: int = 0) -> str:
    """Recursively decode MIME payload to plain text. Prefers text/plain over HTML."""
    if _depth > 10:
        return ""

    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and body_data:
        try:
            text = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
            return text[:5000] + (" [... truncated]" if len(text) > 5000 else "")
        except Exception:
            return ""

    if mime_type == "text/html" and body_data:
        try:
            html = base64.urlsafe_b64decode(body_data + "==").decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            return text[:5000] + (" [... truncated]" if len(text) > 5000 else "")
        except Exception:
            return ""

    if mime_type.startswith("multipart/"):
        plain = ""
        html_fallback = ""
        for part in payload.get("parts", []):
            part_type = part.get("mimeType", "")
            if part_type == "text/plain":
                plain = decode_mime_body(part, _depth + 1)
                if plain:
                    return plain
            elif part_type == "text/html" and not html_fallback:
                html_fallback = decode_mime_body(part, _depth + 1)
            elif part_type.startswith("multipart/"):
                nested = decode_mime_body(part, _depth + 1)
                if nested:
                    return nested
        return plain or html_fallback

    return "(message body not available)"


def format_emails_for_extraction(email_data_list: list[dict]) -> str:
    """Format list of email dicts into structured text block for LLM extraction."""
    lines = []
    for i, em in enumerate(email_data_list, 1):
        lines.append(f"=== EMAIL {i} ===")
        lines.append(f"From: {em.get('from', '')}")
        lines.append(f"Subject: {em.get('subject', '(no subject)')}")
        lines.append(f"Date: {em.get('date', '')}")
        lines.append("---")
        lines.append(em.get("body", "(no body)") or "(no body)")
        lines.append("")

        replies = em.get("replies", [])
        total = len(replies) + 1
        for j, reply in enumerate(replies, 2):
            lines.append(f"=== EMAIL {i} — REPLY {j} of {total} ===")
            lines.append(f"From: {reply.get('from', '')}")
            lines.append(f"Date: {reply.get('date', '')}")
            lines.append("---")
            lines.append(reply.get("body", "(no body)") or "(no body)")
            lines.append("")

    return "\n".join(lines)


def extract_attachments_from_payload(payload: dict, message_id: str) -> list[dict]:
    """Recursively find file attachments in a MIME payload tree."""
    attachments = []
    filename = payload.get("filename", "")
    body     = payload.get("body", {})

    if filename:
        ext  = os.path.splitext(filename)[1].lower()
        size = body.get("size", 0)
        if ext in SUPPORTED_ATTACHMENT_EXTENSIONS and size <= MAX_ATTACHMENT_BYTES:
            attachments.append({
                "filename":      filename,
                "mime_type":     payload.get("mimeType", ""),
                "message_id":    message_id,
                "size":          size,
                "attachment_id": body.get("attachmentId"),
                "inline_data":   body.get("data"),  # present only for small inline attachments
            })

    for part in payload.get("parts", []):
        attachments.extend(extract_attachments_from_payload(part, message_id))

    return attachments


def download_attachment(service, attachment: dict) -> bytes:
    """Return raw bytes for an attachment — handles both inline and server-stored."""
    if attachment.get("inline_data"):
        return base64.urlsafe_b64decode(attachment["inline_data"] + "==")
    result = service.users().messages().attachments().get(
        userId="me",
        messageId=attachment["message_id"],
        id=attachment["attachment_id"],
    ).execute()
    return base64.urlsafe_b64decode(result.get("data", "") + "==")
