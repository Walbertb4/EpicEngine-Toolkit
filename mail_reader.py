"""
mail_reader.py
==============
Rambler.ru mailinden Epic Games 6 haneli doğrulama kodunu çeker.
INBOX ve Spam klasörlerini eşzamanlı tarayarak kod kaybını önler.
"""

import imaplib
import email
import re
import time
from typing import Optional

IMAP_SERVER = "imap.rambler.ru"
IMAP_PORT   = 993

# Rambler'ın kullanabileceği olası klasör adları
FOLDERS_TO_CHECK = ["INBOX", "Spam", "Junk", "&BCEEPwQwBDw-"]

def _connect(email_address: str, password: str) -> Optional[imaplib.IMAP4_SSL]:
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(email_address, password)
        return mail
    except Exception as e:
        print(f"  [✗] IMAP bağlantı hatası: {e}")
        return None

def _disconnect(mail: imaplib.IMAP4_SSL) -> None:
    try:
        mail.close()
        mail.logout()
    except Exception:
        pass

def _get_mail_body(msg) -> str:
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode("utf-8", errors="ignore")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode("utf-8", errors="ignore")
    return body

def _extract_code(text: str) -> Optional[str]:
    """6 haneli Epic Games kodunu metinden çeker."""
    patterns = [
        r'highlighted-data[^>]*>.*?<p[^>]*>\s*(\d{6})\s*<\/p>',
        r'<div[^>]*font-size:\s*32px[^>]*>\s*(\d{6})\s*<\/div>',
        r'<div[^>]*class="verification-code"[^>]*>\s*(\d{6})\s*<\/div>',
        r'>\s*(\d{6})\s*<',
        r'^\s*(\d{6})\s*$',
        r'\b(\d{6})\b',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if matches:
            code = matches[0].strip()
            if len(code) == 6 and code.isdigit():
                return code
    return None

def _get_start_ids(mail_conn: imaplib.IMAP4_SSL) -> dict:
    """Belirlenen her klasör için başlangıç mail ID'sini sözlük olarak döndürür."""
    start_ids = {}
    for folder in FOLDERS_TO_CHECK:
        try:
            status, _ = mail_conn.select(folder)
            if status != "OK":
                start_ids[folder] = 0
                continue
            
            _, data = mail_conn.search(None, "ALL")
            if data and data[0]:
                ids = data[0].split()
                if ids:
                    start_ids[folder] = int(ids[-1])
                else:
                    start_ids[folder] = 0
            else:
                start_ids[folder] = 0
        except Exception:
            start_ids[folder] = 0
    return start_ids

def _get_new_epic_code(mail_conn: imaplib.IMAP4_SSL, start_ids: dict) -> Optional[str]:
    """Tüm klasörleri gezip start_ids'den büyük olan (yeni) Epic maillerini okur."""
    for folder in FOLDERS_TO_CHECK:
        try:
            status, _ = mail_conn.select(folder)
            if status != "OK":
                continue

            _, data = mail_conn.search(None, "ALL")
            if not data or not data[0]:
                continue

            all_ids = data[0].split()
            min_id = start_ids.get(folder, 0)
            
            # Sadece yeni gelen maillere bak
            new_ids = [mid for mid in all_ids if int(mid) > min_id]

            if not new_ids:
                continue

            # En yeniden başla
            for mail_id in reversed(new_ids):
                _, msg_data = mail_conn.fetch(mail_id, "(RFC822)")
                if not msg_data or not msg_data[0]:
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                
                sender = str(msg.get("From", "")).lower()
                subj = str(msg.get("Subject", "")).lower()

                is_epic = (
                    "epicgames" in sender or
                    "epic" in sender or
                    "verify" in subj or
                    "security" in subj or
                    "code" in subj or
                    "confirm" in subj
                )

                if not is_epic:
                    continue

                body = _get_mail_body(msg)
                code = _extract_code(body)

                if code:
                    print(f"  [✓] Epic maili '{folder}' klasöründe bulundu! (Gönderen: {msg.get('From', '')})")
                    return code

        except Exception:
            continue

    return None

def get_epic_code(email_address: str, password: str, timeout: int = 120, check_interval: int = 5) -> Optional[str]:
    print(f"  [→] Mail bekleniyor: {email_address} (max {timeout}sn)")

    mail_conn = _connect(email_address, password)
    if mail_conn:
        start_ids = _get_start_ids(mail_conn)
        print(f"  [→] Başlangıç ID'leri: {start_ids}")
        _disconnect(mail_conn)
    else:
        return None

    elapsed = 0
    while elapsed < timeout:
        time.sleep(check_interval)
        elapsed += check_interval

        mail_conn = _connect(email_address, password)
        if not mail_conn:
            continue

        try:
            code = _get_new_epic_code(mail_conn, start_ids)
            if code:
                print(f"  [✓] Kod Başarıyla Çekildi: {code}")
                return code

            print(f"  [→] Bekleniyor... ({elapsed}/{timeout}sn)", end="\r")

        except Exception as e:
            print(f"  [!] Hata: {e}")

        finally:
            if mail_conn:
                _disconnect(mail_conn)

    print(f"\n  [✗] {timeout}sn içinde kod gelmedi.")
    return None

if __name__ == "__main__":
    EMAIL    = "kullanici@rambler.ru"
    PASSWORD = "sifre"
    kod = get_epic_code(EMAIL, PASSWORD, timeout=120)
    print(f"Kod: {kod}" if kod else "Kod alınamadı.")