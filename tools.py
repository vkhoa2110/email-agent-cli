import json
import os
import re
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr, getaddresses, make_msgid
from pathlib import Path
from typing import Any, Dict, List


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TOOLS = [
    {
        "type": "function",
        "name": "save_email_draft",
        "description": "Lưu bản nháp email cuối cùng để ứng dụng có thể hiển thị hoặc chuyển tiếp sang hệ thống khác.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Người nhận hoặc mô tả người nhận, ví dụ: 'chị Lan - phòng nhân sự'",
                },
                "subject": {
                    "type": "string",
                    "description": "Tiêu đề email",
                },
                "body": {
                    "type": "string",
                    "description": "Nội dung email hoàn chỉnh",
                },
                "tone": {
                    "type": "string",
                    "description": "Tone của email, ví dụ: lịch sự, thân thiện, trang trọng",
                },
                "language": {
                    "type": "string",
                    "enum": ["vi", "en", "bilingual"],
                    "description": "Ngôn ngữ email",
                },
                "purpose": {
                    "type": "string",
                    "description": "Mục đích email",
                },
            },
            "required": ["to", "subject", "body", "tone", "language", "purpose"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "send_email",
        "description": "Gửi email thật qua SMTP khi người dùng yêu cầu gửi ngay.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Email người nhận. Có thể là một email hoặc nhiều email phân tách bằng dấu phẩy.",
                },
                "subject": {
                    "type": "string",
                    "description": "Tiêu đề email cần gửi",
                },
                "body": {
                    "type": "string",
                    "description": "Nội dung email dạng text/plain",
                },
            },
            "required": ["to", "subject", "body"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def _get_data_dir(name: str) -> Path:
    path = Path(__file__).resolve().parent / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json_record(directory_name: str, prefix: str, payload: Dict[str, Any]) -> str:
    output_dir = _get_data_dir(directory_name)
    record_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    output_path = output_dir / f"{record_id}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(output_path)


def _get_env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _get_required_env(name: str, placeholder: str = "") -> str:
    value = _get_env(name)
    if not value or value == placeholder:
        raise RuntimeError(f"Thiếu cấu hình {name}. Hãy cập nhật file .env trước khi gửi email.")
    return value


def _parse_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise RuntimeError(f"Giá trị boolean không hợp lệ: {value}")


def _parse_recipients(to: str) -> List[str]:
    recipients = [email for _, email in getaddresses([to]) if email.strip()]
    if not recipients:
        raise RuntimeError("Email người nhận không hợp lệ.")
    invalid_recipients = [email for email in recipients if not EMAIL_PATTERN.match(email)]
    if invalid_recipients:
        raise RuntimeError(f"Email người nhận không hợp lệ: {', '.join(invalid_recipients)}")
    return recipients


def save_email_draft(
    to: str,
    subject: str,
    body: str,
    tone: str,
    language: str,
    purpose: str,
) -> Dict[str, Any]:
    draft_id = f"draft_{uuid.uuid4().hex[:8]}"
    payload = {
        "draft_id": draft_id,
        "to": to,
        "subject": subject,
        "body": body,
        "tone": tone,
        "language": language,
        "purpose": purpose,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }

    output_path = _get_data_dir("drafts") / f"{draft_id}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "status": "saved",
        "draft_id": draft_id,
        "path": str(output_path),
        "preview_subject": subject,
    }


def send_email(to: str, subject: str, body: str) -> Dict[str, Any]:
    smtp_host = _get_required_env("SMTP_HOST")
    smtp_port = int(_get_required_env("SMTP_PORT"))
    smtp_from_email = _get_required_env("SMTP_FROM_EMAIL")
    smtp_from_name = _get_env("SMTP_FROM_NAME")
    smtp_username = _get_env("SMTP_USERNAME", smtp_from_email) or smtp_from_email
    smtp_password = _get_required_env("SMTP_PASSWORD", "your_gmail_app_password_here")
    smtp_use_tls = _parse_bool(_get_env("SMTP_USE_TLS", "true"), default=True)
    smtp_use_ssl = _parse_bool(_get_env("SMTP_USE_SSL", "false"), default=False)

    if smtp_use_tls and smtp_use_ssl:
        raise RuntimeError("Chỉ bật một trong hai: SMTP_USE_TLS hoặc SMTP_USE_SSL.")

    recipients = _parse_recipients(to)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((smtp_from_name, smtp_from_email)) if smtp_from_name else smtp_from_email
    message["To"] = ", ".join(recipients)
    message["Message-ID"] = make_msgid()
    message.set_content(body)

    context = ssl.create_default_context()
    try:
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context, timeout=30) as server:
                server.login(smtp_username, smtp_password)
                server.send_message(message, from_addr=smtp_from_email, to_addrs=recipients)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                if smtp_use_tls:
                    server.starttls(context=context)
                    server.ehlo()
                server.login(smtp_username, smtp_password)
                server.send_message(message, from_addr=smtp_from_email, to_addrs=recipients)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError(
            "SMTP username hoặc app password không đúng. Nếu dùng Gmail, hãy dùng App Password thay vì mật khẩu đăng nhập."
        ) from exc
    except smtplib.SMTPException as exc:
        raise RuntimeError(f"SMTP gửi email thất bại: {exc}") from exc
    except OSError as exc:
        raise RuntimeError(f"Không thể kết nối SMTP server: {exc}") from exc

    sent_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "to": recipients,
        "subject": subject,
        "body": body,
        "from_email": smtp_from_email,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "sent_at": sent_at,
        "message_id": message["Message-ID"],
    }
    log_path = _write_json_record("sent_emails", "sent", payload)

    return {
        "status": "sent",
        "to": recipients,
        "from_email": smtp_from_email,
        "subject": subject,
        "sent_at": sent_at,
        "message_id": message["Message-ID"],
        "log_path": log_path,
    }


TOOL_REGISTRY = {
    "save_email_draft": save_email_draft,
    "send_email": send_email,
}
