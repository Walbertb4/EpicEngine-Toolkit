"""
human_simulator.py
==================
botasaurus-driver tabanlı insan davranışı simülatörü.

Kurulum:
    pip install botasaurus-driver

Kullanım:
    from human import human_simulator as human

    driver = human.create_driver()
    human.navigate(driver, "https://epicgames.com")
    human.click(driver, "#button")
    human.human_type(driver, "#input", "merhaba")
    driver.close()
"""

import random
import time
import pickle
import string
from pathlib import Path
from typing import Optional

from botasaurus_driver import Driver


# ─────────────────────────────────────────────
# TEMEL DİZİNLER
# ─────────────────────────────────────────────

BASE_DIR        = Path(__file__).parent.resolve()
COOKIES_DIR     = BASE_DIR / "cookies";     COOKIES_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR    = BASE_DIR / "profiles";    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR = BASE_DIR / "screenshots"; SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────
# DRIVER BAŞLATMA
# ─────────────────────────────────────────────

def create_driver(
    headless: bool = False,
    profile_name: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Driver:
    """
    botasaurus Driver oluşturur.

    Args:
        headless     : Arka planda çalıştır
        profile_name : Profil adı → human/profiles/<isim>/
        proxy        : "host:port" formatında proxy

    Returns:
        botasaurus Driver nesnesi
    """
    profile_path = None
    if profile_name:
        profile_path = str(PROFILES_DIR / profile_name)
        Path(profile_path).mkdir(parents=True, exist_ok=True)

    driver = Driver(
        headless=headless,
        profile=profile_path,
        proxy=proxy,
    )

    return driver


# ─────────────────────────────────────────────
# SAYFA YÖNETİMİ
# ─────────────────────────────────────────────

def navigate(driver: Driver, url: str, wait_sec: float = None) -> None:
    """URL'ye gider, insan benzeri gecikme ekler."""
    driver.get(url)
    if wait_sec is None:
        wait_sec = random.uniform(1.5, 2.5)
    time.sleep(wait_sec)


# ─────────────────────────────────────────────
# ELEMENT BEKLEME VE BULMA
# ─────────────────────────────────────────────

def wait_for(driver: Driver, selector: str, timeout: int = 15):
    """CSS selector ile element bekler. Bulunamazsa None döner."""
    try:
        return driver.get_element(selector, wait=timeout)
    except Exception:
        return None


def safe_find(driver: Driver, selector: str):
    """Element bulunamazsa None döner, exception fırlatmaz."""
    try:
        return driver.get_element_or_none(selector)
    except Exception:
        return None


def find_all(driver: Driver, selector: str) -> list:
    """Tüm eşleşen elementleri döndürür."""
    try:
        return driver.get_elements(selector) or []
    except Exception:
        return []


# ─────────────────────────────────────────────
# İNSAN BENZERİ GECIKMELER
# ─────────────────────────────────────────────

def human_sleep(min_sec: float = 0.5, max_sec: float = 1.5) -> None:
    """Rastgele insan benzeri bekleme."""
    time.sleep(random.uniform(min_sec, max_sec))


def micro_pause() -> None:
    """Çok kısa gecikme (100-300ms) — tıklama sonrası."""
    time.sleep(random.uniform(0.1, 0.3))


def think_pause() -> None:
    """Düşünme gecikmesi (2-4 saniye) — sayfa okuma arası."""
    time.sleep(random.uniform(2.0, 4.0))


# ─────────────────────────────────────────────
# TIKLAMA
# ─────────────────────────────────────────────

def click(driver: Driver, selector: str, timeout: int = 10) -> bool:
    """
    Elemente tıklar. Tıklamadan önce ve sonra kısa gecikme ekler.

    Returns:
        True: başarılı, False: element bulunamadı
    """
    try:
        micro_pause()
        driver.click(selector, wait=timeout)
        micro_pause()
        return True
    except Exception as e:
        print(f"  [!] Tıklama hatası ({selector}): {e}")
        return False


def js_click(driver: Driver, element_id: str) -> bool:
    """JavaScript ile tıklar. Checkbox ve hidden elementler için."""
    try:
        driver.run_js(f"document.getElementById('{element_id}').click()")
        micro_pause()
        return True
    except Exception as e:
        print(f"  [!] JS tıklama hatası ({element_id}): {e}")
        return False


# ─────────────────────────────────────────────
# İNSAN BENZERİ YAZMA
# ─────────────────────────────────────────────

def human_type(driver: Driver, selector: str, text: str, wpm: int = None) -> bool:
    """
    İnsan gibi yazar: rastgele hız, noktalama sonrası duraklama.
    Her karakter arasında Gaussian dağılımlı gecikme var.

    Args:
        driver   : botasaurus Driver
        selector : CSS selector
        text     : Yazılacak metin
        wpm      : Dakikadaki kelime (None = rastgele 40-65)

    Returns:
        True: başarılı, False: hata
    """
    if wpm is None:
        wpm = random.randint(40, 65)

    # WPM → karakter gecikmesi
    avg_delay = 60.0 / (wpm * 5)

    try:
        element = wait_for(driver, selector, timeout=10)
        if not element:
            print(f"  [!] human_type: element bulunamadı ({selector})")
            return False

        element.click()
        time.sleep(random.uniform(0.2, 0.5))  # tıklama sonrası kısa bekleme

        for char in text:
            element.send_keys(char)

            # Gaussian dağılımlı gecikme (insan gibi tutarsız hız)
            delay = random.gauss(avg_delay, avg_delay * 0.4)
            delay = max(0.05, min(delay, avg_delay * 3.0))
            time.sleep(delay)

            # Noktalama ve boşluk sonrası ekstra duraklama
            if char in (" ", ".", ",", "!", "?", "@", "\n"):
                time.sleep(random.uniform(0.08, 0.25))

        # Yazmayı bitirince kısa bekleme
        time.sleep(random.uniform(0.2, 0.5))
        return True

    except Exception as e:
        print(f"  [!] human_type hatası ({selector}): {e}")
        return False


def fast_type(driver: Driver, selector: str, text: str, timeout: int = 10) -> bool:
    """
    Hızlı yazma — sayılar ve şifreler için.
    Tüm metni bir anda gönderir ama öncesinde alan temizlenir.

    Returns:
        True: başarılı, False: hata
    """
    try:
        element = wait_for(driver, selector, timeout=timeout)
        if not element:
            print(f"  [!] fast_type: element bulunamadı ({selector})")
            return False
        element.click()
        micro_pause()
        driver.type(selector, text, wait=timeout)
        micro_pause()
        return True
    except Exception as e:
        print(f"  [!] fast_type hatası ({selector}): {e}")
        return False


def clear_and_type(driver: Driver, selector: str, text: str, timeout: int = 10) -> bool:
    """
    Alanı önce JS ile temizler, sonra human_type ile yazar.
    React inputlar için güvenilir yöntem.

    Returns:
        True: başarılı, False: hata
    """
    try:
        element = wait_for(driver, selector, timeout=timeout)
        if not element:
            print(f"  [!] clear_and_type: element bulunamadı ({selector})")
            return False

        # JS ile React state'i sıfırla
        escaped = selector.replace("'", "\\'")
        driver.run_js(f"""
            var el = document.querySelector('{escaped}');
            if (el) {{
                var setter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value').set;
                setter.call(el, '');
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        """)
        micro_pause()

        # Yazmadan önce kısa bekleme
        time.sleep(random.uniform(0.1, 0.3))
        element.send_keys(text)
        micro_pause()
        return True

    except Exception as e:
        print(f"  [!] clear_and_type hatası ({selector}): {e}")
        return False


# ─────────────────────────────────────────────
# SCROLL
# ─────────────────────────────────────────────

def scroll(driver: Driver, direction: str = "down", amount: int = None) -> None:
    """Sayfayı kaydırır."""
    if amount is None:
        amount = random.randint(200, 500)
    sign = 1 if direction == "down" else -1
    driver.run_js(f"window.scrollBy(0, {amount * sign})")
    micro_pause()


# ─────────────────────────────────────────────
# SAYFA KONTROLÜ
# ─────────────────────────────────────────────

def page_contains(driver: Driver, text: str) -> bool:
    """Sayfanın metninde belirtilen text var mı kontrol eder."""
    try:
        body = driver.get_element_or_none("body")
        if body:
            return text in (body.text or "")
        return False
    except Exception:
        return False


def get_current_url(driver: Driver) -> str:
    """Mevcut URL'yi döndürür."""
    try:
        return driver.current_url or ""
    except Exception:
        return ""


def get_element_text(driver: Driver, selector: str) -> str:
    """Element metnini döndürür."""
    try:
        el = driver.get_element_or_none(selector)
        return el.text if el else ""
    except Exception:
        return ""


# ─────────────────────────────────────────────
# EKRAN GÖRÜNTÜSÜ
# ─────────────────────────────────────────────

def take_screenshot(driver: Driver, filename: str = "screenshot.png") -> str:
    """Ekran görüntüsü alır, human/screenshots/ klasörüne kaydeder."""
    path = Path(filename)
    if not path.is_absolute() and len(path.parts) == 1:
        path = SCREENSHOTS_DIR / filename
    try:
        driver.save_screenshot(str(path))
        print(f"  [✓] Ekran görüntüsü → {path}")
    except Exception as e:
        print(f"  [!] Ekran görüntüsü hatası: {e}")
    return str(path)


# ─────────────────────────────────────────────
# ÇEREZ YÖNETİMİ
# ─────────────────────────────────────────────

def save_cookies(driver: Driver, name: str) -> None:
    """Çerezleri human/cookies/<n>.pkl dosyasına kaydeder."""
    try:
        cookies = driver.get_cookies()
        path = COOKIES_DIR / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump(cookies, f)
        print(f"  [✓] Çerezler kaydedildi → {path}")
    except Exception as e:
        print(f"  [!] Çerez kaydetme hatası: {e}")


def load_cookies(driver: Driver, name: str, url: str) -> bool:
    """Kaydedilmiş çerezleri yükler."""
    path = COOKIES_DIR / f"{name}.pkl"
    if not path.exists():
        return False
    try:
        navigate(driver, url, wait_sec=1)
        with open(path, "rb") as f:
            cookies = pickle.load(f)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception:
                pass
        driver.get(url)
        time.sleep(1.5)
        print(f"  [✓] Çerezler yüklendi → {path}")
        return True
    except Exception as e:
        print(f"  [!] Çerez yükleme hatası: {e}")
        return False