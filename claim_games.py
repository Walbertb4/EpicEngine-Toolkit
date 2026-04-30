"""
claim_games.py
==============
Epic Games Oyun Toplama Modülü. (Final - İnsan Taklitli, EULA & Yeni Buton Korumalı)
"""

import random
import time
import sys
import json
import re
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import human_simulator as human
from ip_rotator import IPRotator

# ─────────────────────────────────────────────
# ORTAK HAFIZA & DURDURMA MEKANİZMASI
# ─────────────────────────────────────────────
class SharedState:
    is_running = True
    is_paused = False

def check_gui_signals():
    """Botun Pause ve Stop komutlarına anında tepki vermesini sağlar"""
    if not SharedState.is_running:
        raise InterruptedError("Sistem durduruldu.")
    while SharedState.is_paused and SharedState.is_running:
        time.sleep(1)

BASE_DIR = Path(__file__).parent.resolve()

def get_game_paths(target_game_url: str):
    """URL'den oyunun adını çeker ve klasör yollarını döndürür."""
    raw_slug = target_game_url.strip("/").split("?")[0].split("/")[-1]
    game_slug = re.sub(r'-[a-fA-F0-9]{6,}$', '', raw_slug) 
    
    game_dir = BASE_DIR / "game_accounts" / game_slug
    game_dir.mkdir(parents=True, exist_ok=True)
    
    return game_dir / "successfull_accounts.txt", game_dir / "failed_accounts.txt"

def _save_success(acc_line: str, target_game_url: str) -> None:
    success_file, _ = get_game_paths(target_game_url)
    prefix = ""
    if os.path.exists(success_file) and os.path.getsize(success_file) > 0:
        with open(success_file, "rb") as f_check:
            f_check.seek(-1, os.SEEK_END)
            if f_check.read(1) != b"\n":
                prefix = "\n"

    with open(success_file, "a", encoding="utf-8") as f:
        f.write(f"{prefix}{acc_line}\n")

def _save_failed(acc_line: str, reason: str, target_game_url: str) -> None:
    _, failed_file = get_game_paths(target_game_url)
    reason_clean = reason.replace(":", " ").strip()[:80]
    
    prefix = ""
    if os.path.exists(failed_file) and os.path.getsize(failed_file) > 0:
        with open(failed_file, "rb") as f_check:
            f_check.seek(-1, os.SEEK_END)
            if f_check.read(1) != b"\n":
                prefix = "\n"

    with open(failed_file, "a", encoding="utf-8") as f:
        f.write(f"{prefix}{acc_line}:{reason_clean}\n")

# ─────────────────────────────────────────────
# SAYAÇ
# ─────────────────────────────────────────────
class Counter:
    def __init__(self, total: int, ui_callback=None):
        self.total   = total
        self.current = 0
        self.success = 0
        self.fail    = 0
        self.ui_callback = ui_callback

    def tick(self, email: str):
        self.current += 1
        print("\n" + "═" * 55)
        print(f"  Hesap  : {self.current}/{self.total}")
        print(f"  Mail   : {email}")
        print("═" * 55)

    def mark_success(self):
        self.success += 1
        if self.ui_callback: self.ui_callback(self.success, self.fail, self.current)

    def mark_fail(self):
        self.fail += 1
        if self.ui_callback: self.ui_callback(self.success, self.fail, self.current)

# ─────────────────────────────────────────────
# GÜVENLİK & ENGEL TEMİZLEYİCİ
# ─────────────────────────────────────────────
def check_and_handle_captcha(driver) -> bool:
    try:
        check_gui_signals()
        result = driver.run_js("""
            var el = document.getElementById('talon_container_login_prod');
            if (!el) return false;
            if (el.style.visibility === 'hidden' || el.style.opacity === '0' || el.style.zIndex === '-1') return false;
            return el.offsetParent !== null;
        """)
        if result:
            print("\n  [!] CAPTCHA ALGILANDI! Lütfen açılan tarayıcıda captcha'yı çözün.")
            while SharedState.is_running:
                check_gui_signals()
                is_still_there = driver.run_js("var el = document.getElementById('talon_container_login_prod'); return el && el.offsetParent !== null && el.style.visibility !== 'hidden';")
                if not is_still_there:
                    print("  [✓] Captcha geçildi, devam ediliyor!")
                    return True
                time.sleep(2)
            return False
    except Exception: pass
    return True

def clear_epic_modals(driver):
    """Ekranda EULA veya 18+ uyarısı varsa bunları temizler."""
    try:
        # EULA Kontrolü
        has_eula = driver.run_js("var el = document.getElementById('accept'); return el && el.offsetParent !== null;")
        if has_eula:
            print("  [!] Sözleşme (EULA) Ekranda, onaylanıyor...")
            human.human_sleep(1.0, 2.0)
            driver.run_js("document.getElementById('accept').click()")
            time.sleep(3)
            
        # 18+ Yaş Kontrolü
        has_age_gate = driver.run_js("var el = document.querySelector('button[data-testid=\"age-gate-continue\"]'); return el && el.offsetParent !== null;")
        if has_age_gate:
            print("  [!] 18+ Yaş Uyarısı geçiliyor...")
            human.human_sleep(1.0, 2.0)
            driver.run_js("document.querySelector('button[data-testid=\"age-gate-continue\"]').click()")
            time.sleep(3)
    except: pass

# --- ADIM 1: GİRİŞ (LOGIN) ---
def step_login(driver, email: str, password: str) -> bool:
    try:
        check_gui_signals()
        human.navigate(driver, "https://www.epicgames.com/id/login?lang=en-US", wait_sec=2.0)
        
        # Email kutucuğunu bekle
        for _ in range(40):
            check_gui_signals()
            if driver.run_js("return document.getElementById('email') !== null;"): break
            time.sleep(0.5)
        else: 
            print("  [✗] Email kutusu bulunamadı.")
            return False

        human.human_sleep(1.0, 2.0)
        
        # Güvenli JS Fallback (Şifre/Mail içindeki özel karakterler için json.dumps)
        safe_email = json.dumps(email)
        driver.run_js(f"var el = document.getElementById('email'); el.focus(); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, {safe_email}); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('blur', {{ bubbles: true }}));")
            
        human.human_sleep(0.5, 1.0)
        
        for _ in range(30):
            if not driver.run_js("return document.getElementById('continue') ? document.getElementById('continue').disabled : true"): break
            time.sleep(0.2)
            
        human.human_sleep(0.5, 1.5)
        driver.run_js("document.getElementById('continue').click()")
        
        # Şifre kutucuğunu bekle
        for _ in range(40):
            check_gui_signals()
            if driver.run_js("return document.getElementById('password') !== null;"): break
            time.sleep(0.5)
        else: 
            print("  [✗] Şifre kutusu bulunamadı.")
            return False

        human.human_sleep(1.0, 2.0)
        
        safe_pwd = json.dumps(password)
        driver.run_js(f"var el = document.getElementById('password'); el.focus(); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, {safe_pwd}); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('blur', {{ bubbles: true }}));")
            
        human.human_sleep(0.5, 1.0)
        
        for _ in range(30):
            if not driver.run_js("return document.getElementById('sign-in') ? document.getElementById('sign-in').disabled : true"): break
            time.sleep(0.2)
            
        human.human_sleep(0.5, 1.5)
        driver.run_js("document.getElementById('sign-in').click()")
        
        print("  [✓] Login bilgileri girildi.")
        return True
    except Exception as e: 
        print(f"  [!] Login adımında hata: {str(e)}")
        return False

# --- ADIM 2: ONAYLAR VE 2FA ---
def step_handle_post_login(driver, email: str, password: str) -> bool:
    from mail_reader import get_epic_code
    print("  [→] Giriş onay ekranları kontrol ediliyor...")
    
    start_wait = time.time()
    while time.time() - start_wait < 120:
        check_gui_signals()
        
        if human.page_contains(driver, "Incorrect response") or human.page_contains(driver, "Sorry, the credentials"):
            print("  [✗] Hatalı şifre veya e-posta.")
            return False

        check_and_handle_captcha(driver)

        # 2FA Kontrolü
        if driver.run_js("return document.querySelector('input[name=\"code-input-0\"]') !== null"):
            print("  [!] 2FA Kodu mailden bekleniyor...")
            kod = get_epic_code(email, password, timeout=120, check_interval=5)
            if not kod: return False

            human.human_sleep(1.5, 3.0)
            for i, digit in enumerate(kod):
                driver.run_js(f"var el = document.querySelector('input[name=\"code-input-{i}\"]'); if (el) {{ var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, '{digit}'); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
                time.sleep(random.uniform(0.1, 0.3))

            human.human_sleep(0.5, 1.5)

            for _ in range(20):
                if not driver.run_js("return document.getElementById('continue') ? document.getElementById('continue').disabled : true"): break
                time.sleep(0.3)
                
            driver.run_js("document.getElementById('continue').click()")
            
            # Sayfadan çıkılana kadar bekle
            for _ in range(40):
                check_gui_signals()
                time.sleep(0.5)
                if human.page_contains(driver, "incorrect") or human.page_contains(driver, "invalid"): return False
                if not driver.run_js("return document.querySelector('input[name=\"code-input-0\"]') !== null"): break
            else: return False
            
            print("  [✓] 2FA kodu girildi.")
            continue

        # Ekstra Onay Ekranları
        for selector, msg in [
            ("#yes", "Hesap onayı (Yes)"),
            ("#login-reminder-prompt-setup-tfa-continue", "2FA metot onayı (Confirm)"),
            ("#accept", "EULA Sözleşmesi (Accept)"),
            ("#link-success", "Hesap bağlama onayı (Done linking)")
        ]:
            if driver.run_js(f"return document.getElementById('{selector.replace('#', '')}') !== null"):
                human.human_sleep(1.0, 2.0)
                driver.run_js(f"document.getElementById('{selector.replace('#', '')}').click()")
                print(f"  [✓] {msg} geçildi.")
                time.sleep(3)
                break 

        # Giriş tamamlandı mı kontrolü
        current_url = driver.current_url
        if "/id/login" not in current_url and "epicgames.com" in current_url:
            print("  [✓] Oturum başarıyla açıldı.")
            return True
            
        time.sleep(1)
        
    return False

# --- ADIM 3: OYUN ALMA ---
def step_claim_game(driver, target_game_url: str) -> str | None:
    try:
        check_gui_signals()
        print(f"  [→] Oyun sayfasına gidiliyor...")
        human.navigate(driver, target_game_url, wait_sec=4.0)

        # Oyun sayfasında bile çıkma ihtimaline karşı EULA ve Yaş Uyarısı temizliği
        for _ in range(5):
            check_gui_signals()
            clear_epic_modals(driver)
            time.sleep(0.5)

        get_button_selector = 'button[data-testid="purchase-cta-button"]'
        
        # Get Butonunun yüklenmesini bekle
        for _ in range(40):
            check_gui_signals()
            clear_epic_modals(driver) # Beklerken de çıkabilir
            if driver.run_js(f"return document.querySelector('{get_button_selector}') !== null"): break
            time.sleep(0.5)
        else: return "Oyun sayfasında 'Get' butonu bulunamadı"

        btn_text = driver.run_js(f"return document.querySelector('{get_button_selector}').innerText").lower()
        if "owned" in btn_text or "in library" in btn_text or "kütüphanede" in btn_text:
            return "SUCCESS_ALREADY_OWNED"

        human.human_sleep(1.0, 2.5)
        
        # GET Butonuna bas
        driver.run_js(f"document.querySelector('{get_button_selector}').click()")
        print("  [✓] 'Get' butonuna basıldı. Onay ekranı kontrol ediliyor...")

        time.sleep(3)

        # Oturum düşme (Epic Güvenliği) kontrolü
        if "login" in driver.current_url.lower():
            return "Oturum düştü, login sayfasına geri attı (Epic Güvenliği)."

        # --- 1. ADIM: YENİ EPIC UI - "It's all yours" EKRANINI BEKLE ---
        # Bazı oyunlarda Epic artık Place Order penceresi çıkarmıyor,
        # Get'e basınca direkt onay ekranı geliyor. Önce bunu kontrol et.
        def check_success_screen():
            page_html = driver.run_js("return document.body.innerHTML;") or ""
            classic = (
                "Thanks for your order!" in page_html or
                "Order number" in page_html or
                "Ready to install" in page_html or
                "Siparişiniz için teşekkürler" in page_html
            )
            new_ui = driver.run_js("""
                var el = document.querySelector('[data-testid="checkout-success-title"]');
                if (el && el.offsetParent !== null) return true;
                var spans = document.querySelectorAll('h3 span, span');
                for (var i = 0; i < spans.length; i++) {
                    var t = (spans[i].innerText || spans[i].textContent || "").trim();
                    if (t === "It's all yours") return true;
                }
                return false;
            """) or False
            return classic or new_ui

        print("  [→] Yeni Epic UI onay ekranı bekleniyor ('It's all yours')...")
        start_wait = time.time()
        got_new_ui = False
        while time.time() - start_wait < 10:
            check_gui_signals()
            if check_success_screen():
                got_new_ui = True
                break
            time.sleep(1)

        if got_new_ui:
            print("  [✓] Sipariş başarıyla tamamlandı! (Yeni Epic UI)")
            time.sleep(2)
            return "SUCCESS_CLAIMED"

        # --- 2. ADIM: ESKİ AKIŞ - PLACE ORDER PENCERESİNİ ARA ---
        print("  [→] Yeni UI gelmedi, Place Order penceresi aranıyor...")
        time.sleep(5)  # Sayfanın yüklenmesi için ek bekleme

        start_wait = time.time()
        order_clicked = False
        while time.time() - start_wait < 30:
            check_gui_signals()
            clicked = driver.run_js("""
                var clicked = false;
                function checkAndClick(btn) {
                    if (btn && !btn.disabled) {
                        var text = (btn.innerText || btn.textContent || "").toLowerCase();
                        var cls = (btn.className || "").toLowerCase();
                        if (text.includes('place order') || text.includes('sipariş ver') || text.includes('confirm') || cls.includes('payment-btn')) {
                            setTimeout(function() { btn.click(); }, 500 + Math.random() * 1000);
                            return true;
                        }
                    }
                    return false;
                }
                // Ana DOM
                var btns = document.querySelectorAll('button');
                for (var j = 0; j < btns.length; j++) {
                    if (checkAndClick(btns[j])) { clicked = true; break; }
                }
                // Iframe içi
                if (!clicked) {
                    var frames = document.getElementsByTagName('iframe');
                    for (var i = 0; i < frames.length; i++) {
                        try {
                            var iframeBtns = frames[i].contentWindow.document.querySelectorAll('button');
                            for (var j = 0; j < iframeBtns.length; j++) {
                                if (checkAndClick(iframeBtns[j])) { clicked = true; break; }
                            }
                        } catch(e) {}
                        if (clicked) break;
                    }
                }
                return clicked;
            """)
            if clicked:
                order_clicked = True
                print("  [✓] Sipariş ver (Place Order) butonuna basıldı.")
                break
            time.sleep(1)

        if not order_clicked:
            return "Place Order butonu bulunamadı"

        # --- 3. ADIM: ESKİ AKIŞ ONAY EKRANINI BEKLE ---
        print("  [→] Siparişin tamamlanması bekleniyor...")
        start_wait = time.time()
        while time.time() - start_wait < 45:
            check_gui_signals()
            if check_success_screen():
                print("  [✓] Sipariş başarıyla tamamlandı!")
                time.sleep(2)
                return "SUCCESS_CLAIMED"
            time.sleep(2)

        return "Sipariş onay ekranı ('Thanks for your order!') gelmedi."
    except Exception as e:
        return f"Oyun alma hatası: {str(e)}"

# ─────────────────────────────────────────────
# ANA MOTOR VE LİSTE İŞLEME
# ─────────────────────────────────────────────
def process_account(email: str, password: str, target_game_url: str, max_retries: int = 2) -> tuple[bool, str]:
    for attempt in range(1, max_retries + 1):
        try: check_gui_signals()
        except InterruptedError: return False, "Sistem Durduruldu"

        if attempt > 1: print(f"  [→] Motor yenileniyor ({attempt}/{max_retries})...")
        driver = human.create_driver()

        try:
            if not step_login(driver, email, password):
                if attempt < max_retries: continue
                return False, "Login başarısız"

            if not step_handle_post_login(driver, email, password):
                if attempt < max_retries: continue
                return False, "Onay ekranları geçilemedi"

            result = step_claim_game(driver, target_game_url)
            if result == "SUCCESS_ALREADY_OWNED":
                return True, "Zaten kütüphanede"
            elif result == "SUCCESS_CLAIMED":
                return True, "Oyun başarıyla alındı"
            else:
                if attempt < max_retries: continue
                return False, result

        finally:
            try: driver.close()
            except: pass

    return False, "Max deneme"

def run_batch(accounts_list: list, target_game_url: str, counter: Counter, use_rotator: bool, is_retry: bool = False) -> list:
    rotator = IPRotator(accounts_per_rotation=3) if use_rotator else None
    failed_this_run = []
    
    for idx, acc_line in enumerate(accounts_list):
        try: check_gui_signals()
        except InterruptedError:
            print("[SYSTEM] Operasyon iptal edildi.")
            break

        parts = acc_line.split(":")
        if len(parts) < 3:
            counter.mark_fail()
            continue
            
        email = parts[1].strip()
        password = parts[2].strip()

        counter.tick(email)

        if idx > 0 and idx % 3 == 0 and rotator:
            print("  [IP] IP Rotasyonu tetikleniyor...")
            rotator.rotate()

        try:
            basarili, sonuc = process_account(email, password, target_game_url)
            if basarili:
                print(f"  [✓] OYUN EKLENDİ: {sonuc}")
                _save_success(acc_line, target_game_url)
                counter.mark_success()
            else:
                print(f"  [✗] BAŞARISIZ: {sonuc}")
                if not is_retry: 
                    _save_failed(acc_line, sonuc, target_game_url)
                    failed_this_run.append(acc_line)
                counter.mark_fail()
        except Exception as e:
            print(f"  [!] BEKLENMEDİK HATA: {str(e)}")
            if not is_retry:
                _save_failed(acc_line, str(e), target_game_url)
                failed_this_run.append(acc_line)
            counter.mark_fail()
            
    return failed_this_run

def start_claiming(accounts_list: list, use_rotator: bool, target_game_url: str, ui_callback):
    """GUI'den çağrılan Ana Motor"""
    SharedState.is_running = True
    SharedState.is_paused = False
    
    counter = Counter(total=len(accounts_list), ui_callback=ui_callback)
    
    # 1. Aşama: Ana Listeyi İşle
    failed_accounts = run_batch(accounts_list, target_game_url, counter, use_rotator, is_retry=False)
    
    # 2. Aşama: Başarısız Olanları Kurtarmak İçin Son Bir Kez Retry Yap
    if SharedState.is_running and failed_accounts:
        print(f"\n[SYSTEM] ANA LİSTE BİTTİ. Başarısız olan {len(failed_accounts)} hesap TEKRAR DENENİYOR...")
        counter.total += len(failed_accounts) 
        run_batch(failed_accounts, target_game_url, counter, use_rotator, is_retry=True)
    
    if SharedState.is_running:
        print("\n[SYSTEM] Oyun toplama işlemi tamamlandı!")
