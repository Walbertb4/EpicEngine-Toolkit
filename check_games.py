"""
check_games.py
==============
Rambler IMAP üzerinden Epic Games fatura maillerini tarayarak
oyunun alınıp alınmadığını kontrol eden modül. (Son 15 Mail Tarama & Otomatik Skip)
"""

import imaplib
import email
import time
import sys
import re
import os
from pathlib import Path

class SharedState:
    is_running = True
    is_paused = False

def check_gui_signals():
    if not SharedState.is_running:
        raise InterruptedError("Sistem durduruldu.")
    while SharedState.is_paused and SharedState.is_running:
        time.sleep(1)

BASE_DIR = Path(__file__).parent.resolve()

def get_game_paths(target_game_url: str):
    raw_slug = target_game_url.strip("/").split("?")[0].split("/")[-1]
    game_slug = re.sub(r'-[a-fA-F0-9]{6,}$', '', raw_slug) 
    
    game_dir = BASE_DIR / "game_accounts" / game_slug
    game_dir.mkdir(parents=True, exist_ok=True)
    
    return game_dir / "checked_accounts.txt", game_dir / "failed_buy_accounts.txt", game_slug

def _save_result(filepath, acc_line: str, reason: str = ""):
    prefix = ""
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        with open(filepath, "rb") as f_check:
            f_check.seek(-1, os.SEEK_END)
            if f_check.read(1) != b"\n":
                prefix = "\n"

    with open(filepath, "a", encoding="utf-8") as f:
        if reason:
            f.write(f"{prefix}{acc_line}:{reason}\n")
        else:
            f.write(f"{prefix}{acc_line}\n")

def get_already_checked_emails(filepath) -> set:
    """Zaten check edilmiş e-postaları bir küme (set) olarak döndürür."""
    checked_emails = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(":")
                # Format: DisplayName:Email:Password
                if len(parts) >= 2:
                    checked_emails.add(parts[1].strip())
    return checked_emails

def check_receipt_in_mail(email_address: str, password: str, game_slug: str) -> tuple[bool, str]:
    try:
        check_gui_signals()
        
        mail = imaplib.IMAP4_SSL("imap.rambler.ru", 993)
        mail.login(email_address, password)

        # Rambler'da faturaların düşebileceği kesin klasörler
        # &BCEEPwQwBDw- -> "Чеки" (Makbuzlar) klasörünün IMAP kodudur.
        folders_to_check = ["INBOX", "&BCEEPwQwBDw-", "Spam", "Junk"]

        found = False
        msg_result = ""

        for folder in folders_to_check:
            if found: break
            try:
                check_gui_signals()
                status, _ = mail.select(f'"{folder}"', readonly=True)
                if status != 'OK': continue

                # Arama filtresi kullanmadan doğrudan tüm mailleri al (Rambler filtreleme bug'ını aşmak için)
                status, messages = mail.search(None, 'ALL')
                if status != 'OK' or not messages[0]: continue

                # En yeni 15 maili al ve incele
                msg_nums = messages[0].split()[::-1][:15]
                
                for num in msg_nums:
                    check_gui_signals()
                    typ, data = mail.fetch(num, '(RFC822)')
                    raw_email = data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    # Gönderici kontrolü (Epic Games'ten mi gelmiş?)
                    sender = str(msg.get("From", "")).lower()
                    if "epicgames" not in sender:
                        continue

                    # Mailin içini oku
                    body = ""
                    for part in msg.walk():
                        if part.get_content_maintype() == 'text':
                            try:
                                payload = part.get_payload(decode=True)
                                if payload: 
                                    charset = part.get_content_charset() or 'utf-8'
                                    try: body += payload.decode(charset, errors='ignore')
                                    except: body += payload.decode('utf-8', errors='ignore')
                            except:
                                pass

                    body_lower = body.lower()
                    body_clean = re.sub(r'<[^>]+>', ' ', body_lower) # HTML etiketlerini sil
                    body_clean = " ".join(body_clean.split())

                    # Epic Games Faturası mı?
                    if "receipt" in body_clean or "invoice" in body_clean or "order id" in body_clean or "sipariş" in body_clean:
                        found = True
                        folder_display = "Чеки (Makbuzlar)" if folder == "&BCEEPwQwBDw-" else folder
                        msg_result = f"Fatura bulundu -> [{folder_display}]"
                        break

            except Exception:
                continue

        try:
            mail.close()
            mail.logout()
        except: pass

        if found:
            return True, msg_result
        else:
            return False, "Fatura bulunamadı (Son 15 mail tarandı)."

    except imaplib.IMAP4.error:
        return False, "Mail giriş hatası (Yanlış Şifre / Kilitli)"
    except Exception as e:
        return False, f"IMAP Hatası: {str(e)}"

def start_checking(accounts_list: list, target_game_url: str, ui_callback):
    SharedState.is_running = True
    SharedState.is_paused = False
    
    checked_file, failed_file, game_slug = get_game_paths(target_game_url)
    
    # Zaten taranmış ve başarılı bulunmuş e-postaları hafızaya al
    already_checked_emails = get_already_checked_emails(checked_file)
    
    total = len(accounts_list)
    success_count = 0
    fail_count = 0

    print(f"\n[SYSTEM] Hızlı Mail Check Motoru Başlatıldı. Hedef: {game_slug}")

    for idx, acc_line in enumerate(accounts_list):
        try:
            check_gui_signals()
            current = idx + 1
            
            parts = acc_line.split(":")
            if len(parts) < 3:
                fail_count += 1
                ui_callback(success_count, fail_count, current)
                continue
                
            email_addr = parts[1].strip()
            pwd = parts[2].strip()

            # --- OTOMATİK ATLAYICI (SKIP) ---
            if email_addr in already_checked_emails:
                print(f"  [{current}/{total}] {email_addr} -> [FILTER] Zaten kontrol edilmiş, atlanıyor.")
                success_count += 1
                ui_callback(success_count, fail_count, current)
                continue

            print(f"  [{current}/{total}] Kontrol ediliyor: {email_addr} ... ", end="")
            sys.stdout.flush()

            is_claimed, msg = check_receipt_in_mail(email_addr, pwd, game_slug)

            if is_claimed:
                print(f" [✓] OYUN VAR ({msg})")
                _save_result(checked_file, acc_line)
                # Kümeye ekle ki aynı çalışmada tekrar gelirse yine atlasın
                already_checked_emails.add(email_addr)
                success_count += 1
            else:
                print(f" [✗] {msg}")
                _save_result(failed_file, acc_line, msg)
                fail_count += 1

            ui_callback(success_count, fail_count, current)
            time.sleep(0.3)

        except InterruptedError:
            print("\n[SYSTEM] Check işlemi iptal edildi.")
            break
        except Exception as e:
            print(f" [!] Kritik hata: {e}")
            fail_count += 1
            ui_callback(success_count, fail_count, current)
            
    if SharedState.is_running:
        print("\n[SYSTEM] Check işlemi tamamlandı!")