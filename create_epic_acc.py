"""
create_epic_acc.py
==================
Epic Games hesap oluşturma scripti. (GUI Entegreli, Auto-Retry Sürümü)
"""

import random
import string
import time
import sys
import json
from pathlib import Path
import os

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

BASE_DIR     = Path(__file__).parent.resolve()
ACCOUNTS_DIR = BASE_DIR / "accounts"
ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True) 

SUCCESS_FILE = ACCOUNTS_DIR / "successfull_accounts.txt"
FAILED_FILE  = ACCOUNTS_DIR / "failed_accounts.txt"

# ─────────────────────────────────────────────
# SAYAÇ VE GUI GÜNCELLEYİCİ
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

# (İSİM LİSTELERİ)
ERKEK_ISIMLER = ["Ahmet", "Mehmet", "Ali", "Mustafa", "Hasan", "Ibrahim", "Ismail", "Omer", "Yusuf", "Murat", "Emre", "Burak", "Kemal", "Serkan", "Tarik", "Oguz", "Tolga", "Enes", "Kaan", "Berkay", "Furkan", "Yigit", "Berk", "Onur", "Umut", "Cagri", "Alper", "Arda", "Deniz", "Cem", "Selim", "Okan", "Baris", "Erkan", "Volkan", "Sinan", "Gokhan", "Taner", "Ugur"]
KADIN_ISIMLER = ["Ayse", "Fatma", "Zeynep", "Emine", "Hatice", "Elif", "Merve", "Esra", "Busra", "Selin", "Gamze", "Derya", "Ozlem", "Sibel", "Tuba", "Gulsen", "Neslihan", "Ebru", "Cansu", "Ilknur", "Hulya", "Sevgi", "Nuray", "Arzu", "Pinar", "Ceren", "Sevinc", "Dilek", "Leyla", "Yasemin", "Songul"]
SOYISIMLER = ["Yilmaz", "Kaya", "Demir", "Sahin", "Celik", "Yildiz", "Yildirim", "Ozturk", "Aydin", "Ozdemir", "Arslan", "Dogan", "Kilic", "Aslan", "Cetin", "Koc", "Kurt", "Ozkan", "Simsek", "Polat", "Erdogan", "Gunes", "Tekin", "Acar", "Bulut", "Duman", "Karaca", "Guler", "Aktas", "Kaplan"]
DN_WORDS = ["Mert", "Kaya", "Bora", "Arda", "Emre", "Kaan", "Onur", "Berk", "Enes", "Ozan", "Umut", "Alp", "Cem", "Can", "Eren", "Emir", "Tuna", "Yuce", "Doga", "Kurt", "Demir", "Aslan", "Polat", "Bulut", "Kartal", "Bozkurt", "Tekin", "Keskin", "Yilmaz", "Duman", "Tuncer", "Akin", "Sarp", "Yigit", "Alper", "Serkan", "Volkan", "Tarik", "Koray", "Meral", "Selin", "Ceren", "Melis", "Nisan", "Ilgaz", "Deniz", "Pelin"]

def _load_used_display_names() -> set:
    if not SUCCESS_FILE.exists(): return set()
    used = set()
    with open(SUCCESS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and ":" in line:
                used.add(line.split(":")[0])
    return used

def _save_success(display_name: str, email: str, password: str) -> None:
    prefix = ""
    if os.path.exists(SUCCESS_FILE) and os.path.getsize(SUCCESS_FILE) > 0:
        with open(SUCCESS_FILE, "r", encoding="utf-8") as r:
            r.seek(os.path.getsize(SUCCESS_FILE) - 1)
            last_char = r.read(1)
            if last_char != "\n":
                prefix = "\n"

    with open(SUCCESS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{prefix}{display_name}:{email}:{password}\n")

def _save_failed(email: str, password: str, reason: str) -> None:
    reason_clean = reason.replace(":", " ").strip()[:80]
    
    prefix = ""
    if os.path.exists(FAILED_FILE) and os.path.getsize(FAILED_FILE) > 0:
        with open(FAILED_FILE, "rb") as f_check:
            f_check.seek(-1, os.SEEK_END)
            if f_check.read(1) != b"\n":
                prefix = "\n"

    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(f"{prefix}{email}:{password}:{reason_clean}\n")
    
    print(f"   [✗] BAŞARISIZ DOSYASINA YAZILDI -> {email} | {reason_clean}")

def generate_display_name(used_names: set) -> str:
    digits = string.digits
    def _make() -> str:
        fmt = random.randint(1, 5)
        word = random.choice(DN_WORDS)
        if fmt == 1: return word + "_" + "".join(random.choices(digits, k=random.randint(3, 4)))
        elif fmt == 2: return word + "." + "".join(random.choices(digits, k=random.randint(3, 5)))
        elif fmt == 3: return word + random.choice(DN_WORDS) + "".join(random.choices(digits, k=random.randint(2, 3)))
        elif fmt == 4: return word + "-" + "".join(random.choices(digits, k=random.randint(3, 4)))
        else: return word + "".join(random.choices(digits, k=random.randint(3, 5)))
    for _ in range(1000):
        name = _make()
        if not (3 <= len(name) <= 16): continue
        if any(a in "-_." and b in "-_." for a, b in zip(name, name[1:])): continue
        if name[0] in "-_." or name[-1] in "-.": continue
        if name not in used_names: return name
    raise RuntimeError("Display name üretilemedi!")

def generate_person() -> dict:
    cinsiyet = random.choice(["erkek", "kadin"])
    first_name = random.choice(ERKEK_ISIMLER if cinsiyet == "erkek" else KADIN_ISIMLER)
    return {"first_name": first_name, "last_name": random.choice(SOYISIMLER)}

def check_incorrect_response(driver) -> bool:
    if human.page_contains(driver, "Incorrect response"):
        print("  [✗] 'Incorrect response' — bu hesap atlanıyor.")
        return False
    return True

def check_and_handle_captcha(driver) -> bool:
    try:
        check_gui_signals()
        result = driver.run_js("""
            var el = document.getElementById('talon_container_registration_prod');
            if (!el) return false;
            var s = el.style;
            if (s.visibility === 'hidden' || s.opacity === '0' || s.zIndex === '-1') return false;
            return el.offsetParent !== null;
        """)
        if result:
            print("\n  [!] CAPTCHA ALGILANDI! Lütfen açılan tarayıcıda captcha'yı çözün.")
            while SharedState.is_running:
                check_gui_signals()
                is_still_there = driver.run_js("var el = document.getElementById('talon_container_registration_prod'); return el && el.offsetParent !== null;")
                if not is_still_there:
                    print("  [✓] Captcha geçildi, devam ediliyor!")
                    return True
                time.sleep(2)
            return False
    except Exception: pass
    return True

def step_date_of_birth(driver) -> bool:
    try:
        check_gui_signals()
        human.navigate(driver, "https://www.epicgames.com/id/register/date-of-birth", wait_sec=2.0)
        if not human.click(driver, "button[title='Open']", timeout=10): return False
        human.human_sleep(0.4, 0.8)
        ay = random.randint(1, 12)
        if not human.click(driver, f"ul[role='listbox'] li:nth-child({ay})", timeout=5): return False
        human.human_sleep(0.5, 0.9)
        
        gun, yil = random.randint(1, 28), random.randint(1990, 2003)
        driver.run_js(f"var el = document.getElementById('day'); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, '{gun}'); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }}));")
        driver.run_js(f"var el = document.getElementById('year'); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, '{yil}'); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }}));")
        
        human.human_sleep(0.5, 1.0)
        if not human.click(driver, "#continue", timeout=10): return False
        
        for _ in range(30):
            check_gui_signals()
            time.sleep(0.5)
            url = human.get_current_url(driver)
            if "date-of-birth" not in url or driver.run_js("return document.getElementById('email') !== null"): break
        else: return False
        
        print(f"  [✓] Doğum tarihi: {gun}/{ay}/{yil}")
        return True
    except Exception: return False

def step_email_page(driver, email: str) -> bool:
    try:
        check_gui_signals()
        human.human_sleep(1.5, 2.5)
        if not driver.run_js("return document.getElementById('email') !== null;"): return False
        
        driver.run_js(f"var el = document.getElementById('email'); el.focus(); var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, '{email}'); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('blur', {{ bubbles: true }}));")
        human.human_sleep(0.8, 1.2)
        
        for _ in range(30):
            if not driver.run_js("return document.getElementById('send') ? document.getElementById('send').disabled : true"): break
            time.sleep(0.2)
            
        driver.run_js("document.getElementById('send').click()")
        
        for _ in range(30):
            check_gui_signals()
            time.sleep(0.5)
            if driver.run_js("return document.getElementById('name') !== null") or human.page_contains(driver, "Incorrect response"): break
            
        if not check_and_handle_captcha(driver): return False
        print(f"  [✓] Email girildi: {email}")
        return True
    except Exception: return False

def step_register_form(driver, email: str, password: str) -> str | None:
    try:
        check_gui_signals()
        used_names = _load_used_display_names()
        person = generate_person()
        
        for _ in range(40):
            check_gui_signals()
            if driver.run_js("return document.getElementById('name') !== null && document.getElementById('lastName') !== null && document.getElementById('password') !== null"): break
            time.sleep(0.5)
        else: return None

        def js_set(field_id: str, value: str):
            # YENİ: json.dumps ile JS injection risklerini (ve özel karakter kaynaklı çökmeleri) sıfırlıyoruz
            safe_val = json.dumps(value)
            driver.run_js(f"var el = document.getElementById('{field_id}'); if (el) {{ var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, {safe_val}); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); el.dispatchEvent(new Event('blur', {{ bubbles: true }})); }}")

        js_set("email", email)
        if not human.human_type(driver, "#name", person["first_name"], wpm=55): js_set("name", person["first_name"])
        if not human.human_type(driver, "#lastName", person["last_name"], wpm=55): js_set("lastName", person["last_name"])
        js_set("password", password)
        
        display_name = generate_display_name(used_names)
        for attempt in range(1, 16):
            js_set("displayName", display_name)
            human.human_sleep(2.5, 3.5)
            error_text = human.get_element_text(driver, "#displayName-helper-text").lower()
            if "already in use" in error_text or "already taken" in error_text:
                used_names.add(display_name)
                display_name = generate_display_name(used_names)
                continue
            break
        else: return None

        human.human_sleep(0.4, 0.7)
        human.js_click(driver, "tos")
        human.human_sleep(0.3, 0.5)
        
        for _ in range(30):
            if not driver.run_js("return document.getElementById('btn-submit') ? document.getElementById('btn-submit').disabled : true"): break
            time.sleep(0.2)
            
        driver.run_js("document.getElementById('btn-submit').click()")
        human.human_sleep(2.0, 3.0)
        
        if not check_incorrect_response(driver) or not check_and_handle_captcha(driver): return None
        print(f"  [✓] Form gönderildi! Display: {display_name}")
        return display_name
    except Exception: return None

def _step_email_verify(driver, email: str, password: str) -> bool:
    try:
        from mail_reader import get_epic_code
        for _ in range(30):
            check_gui_signals()
            time.sleep(0.5)
            if driver.run_js("return document.querySelector('input[name=\"code-input-0\"]') !== null"): break
        else: return False

        kod = get_epic_code(email, password, timeout=120, check_interval=5)
        if not kod: return False

        for i, digit in enumerate(kod):
            driver.run_js(f"var el = document.querySelector('input[name=\"code-input-{i}\"]'); if (el) {{ var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set; setter.call(el, '{digit}'); el.dispatchEvent(new Event('input', {{ bubbles: true }})); el.dispatchEvent(new Event('change', {{ bubbles: true }})); }}")
            time.sleep(random.uniform(0.1, 0.3))

        for _ in range(20):
            if not driver.run_js("return document.getElementById('continue') ? document.getElementById('continue').disabled : true"): break
            time.sleep(0.3)

        driver.run_js("document.getElementById('continue').click()")
        
        # YENİ: Kod sayfasından tamamen çıkana kadar bekleme mekanizması
        for _ in range(40):
            check_gui_signals()
            time.sleep(0.5)
            if human.page_contains(driver, "incorrect") or human.page_contains(driver, "invalid"): 
                return False
            
            # Eğer 2FA kodu girilen input silinmişse, kod sayfasından çıkılmış demektir
            if not driver.run_js("return document.querySelector('input[name=\"code-input-0\"]') !== null"):
                return True
                
        return False
    except Exception: return False

def process_account(email: str, password: str, max_retries: int = 2, profile_name: str = None, grid_pos: dict = None) -> tuple[bool, str]:
    for attempt in range(1, max_retries + 1):
        try: check_gui_signals()
        except InterruptedError: return False, "Sistem Durduruldu"

        if attempt > 1: print(f"  [→] Form yenileniyor ({attempt}/{max_retries})...")
        
        driver = None
        try:
            # 1. Bütün koordinat işini human_simulator hallediyor, biz sadece yolluyoruz.
            driver = human.create_driver(profile_name=profile_name, grid_pos=grid_pos)

            # 3. İşlemlere normal devam et
            if not step_date_of_birth(driver):
                if attempt < max_retries: continue
                return False, "Doğum tarihi adımı başarısız"

            if not step_email_page(driver, email):
                if attempt < max_retries: continue
                return False, "Email sayfası başarısız"

            display_name = step_register_form(driver, email, password)
            if not display_name:
                if attempt < max_retries: continue
                return False, "Kayıt formu başarısız"

            if not _step_email_verify(driver, email, password):
                return False, "Email doğrulama başarısız"

            return True, display_name
        finally:
            if driver:
                try: driver.close()
                except: pass

    return False, "Max deneme"

def run_batch(credentials: list, counter: Counter, use_rotator: bool, is_retry: bool = False) -> list:
    rotator = IPRotator(accounts_per_rotation=3) if use_rotator else None
    failed_this_run = []
    
    for idx, (email, password) in enumerate(credentials):
        try: check_gui_signals()
        except InterruptedError:
            print("[SYSTEM] Operasyon iptal edildi.")
            break

        counter.tick(email)

        if idx > 0 and idx % 3 == 0 and rotator:
            print("  [IP] IP Rotasyonu tetikleniyor...")
            rotator.rotate()

        try:
            basarili, sonuc = process_account(email, password)
            if basarili:
                _save_success(sonuc, email, password)
                counter.mark_success()
            else:
                print(f"  [✗] BAŞARISIZ: {sonuc}") 
                
                if not is_retry: 
                    _save_failed(email, password, sonuc) 
                    failed_this_run.append((email, password))
                counter.mark_fail()
        except Exception as e:
            print(f"  [!] BEKLENMEDİK HATA: {str(e)}") 
            
            if not is_retry:
                _save_failed(email, password, str(e)) 
                failed_this_run.append((email, password))
            counter.mark_fail()
            
    return failed_this_run

def start_automation(credentials: list, use_rotator: bool, ui_callback):
    SharedState.is_running = True
    SharedState.is_paused = False
    
    counter = Counter(total=len(credentials), ui_callback=ui_callback)
    
    failed_accounts = run_batch(credentials, counter, use_rotator, is_retry=False)
    
    if SharedState.is_running and failed_accounts:
        print(f"\n[SYSTEM] ANA LİSTE BİTTİ. Başarısız olan {len(failed_accounts)} hesap TEKRAR DENENİYOR...")
        counter.total += len(failed_accounts) 
        run_batch(failed_accounts, counter, use_rotator, is_retry=True)
    
    if SharedState.is_running:
        print("\n[SYSTEM] TÜM GÖREVLER TAMAMLANDI!")
