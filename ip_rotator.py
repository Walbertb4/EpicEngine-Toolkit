"""
ip_rotator.py
=============
Android telefon üzerinden USB tethering ile İNATÇI IP rotasyonu.
IP değişene kadar dener ve uçak modunda kalma süresini her denemede agresif olarak artırır.
Android 11+ (Örn: S24) için GERÇEK Uçak Modu komutları kullanır.
"""

import subprocess
import time
import socket
import urllib.request
from typing import Optional

# ─────────────────────────────────────────────
# AYARLAR
# ─────────────────────────────────────────────
ADB_PATH = "adb"
AIRPLANE_ON_BASE_WAIT = 5  # Uçak modunda taban bekleme süresi
AIRPLANE_OFF_WAIT     = 8  # Uçak modundan çıkınca internetin gelmesini bekleme süresi
CHECK_HOST = "8.8.8.8"
CHECK_PORT = 53

# ─────────────────────────────────────────────
# ADB KOMUTLARI
# ─────────────────────────────────────────────
def _adb(cmd: list, timeout: int = 10) -> tuple[int, str]:
    """ADB komutu çalıştırır."""
    try:
        result = subprocess.run(
            [ADB_PATH] + cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except Exception as e:
        return -1, str(e)

def check_adb() -> bool:
    """ADB ve telefon bağlantısını kontrol eder."""
    code, out = _adb(["devices"])
    if code != 0:
        print(f"[✗] ADB hatası: {out}")
        return False

    lines = [l for l in out.splitlines() if "device" in l and "List" not in l]
    if not lines:
        print("[✗] Bağlı cihaz bulunamadı! USB Hata Ayıklama açık mı kontrol et.")
        return False
    return True

# ─────────────────────────────────────────────
# GERÇEK UÇAK MODU (S24 / Android 11+ Uyumlu)
# ─────────────────────────────────────────────
def _airplane_mode_on() -> bool:
    """Radyo sinyallerini tamamen keser (Gerçek Uçak Modu)"""
    code, out = _adb(["shell", "cmd", "connectivity", "airplane-mode", "enable"])
    if code == 0:
        print(f"  [→] Uçak Modu AÇILDI ✈️ (Şebeke kesildi)")
        return True
    print(f"  [!] Uçak modu AÇMA hatası: {out}")
    return False

def _airplane_mode_off() -> bool:
    """Radyo sinyallerini geri açar"""
    code, out = _adb(["shell", "cmd", "connectivity", "airplane-mode", "disable"])
    if code == 0:
        print(f"  [→] Uçak Modu KAPATILDI 📶 (Şebeke aranıyor)")
        return True
    print(f"  [!] Uçak modu KAPATMA hatası: {out}")
    return False

def _get_current_ip() -> Optional[str]:
    """Mevcut dış IP adresini alır."""
    try:
        ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode().strip()
        if ip and "." in ip:
            return ip
    except Exception:
        pass
    return None

def _wait_for_connection(timeout: int = 30) -> bool:
    """İnternet bağlantısı gelene kadar bekler."""
    print("  [→] İnternet bekleniyor...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((CHECK_HOST, CHECK_PORT))
            print(" ✓")
            return True
        except Exception:
            print(".", end="", flush=True)
            time.sleep(1)
    print(" ✗")
    return False

# ─────────────────────────────────────────────
# ANA SINIF
# ─────────────────────────────────────────────
class IPRotator:
    def __init__(self, accounts_per_rotation: int = 3):
        self.accounts_per_rotation = accounts_per_rotation
        self._account_count        = 0
        self._rotation_count       = 0

    def is_ready(self) -> bool:
        """ADB bağlantısını kontrol eder ve sistemin ilk açılış rotasyonunu yapar."""
        if check_adb():
            print("\n[✓] ADB Bağlantısı Başarılı!")
            print("[→] Sistem başlatılıyor: ZORUNLU İLK IP ROTASYONU yapılıyor...")
            return self.rotate()
        return False

    def tick(self) -> bool:
        """
        Her hesap açıldığında çağrılır.
        accounts_per_rotation'a ulaşınca IP rotasyonu yapar.
        """
        self._account_count += 1

        if self._account_count % self.accounts_per_rotation == 0:
            print(f"\n  [IP] {self.accounts_per_rotation} hesap tamamlandı → IP rotasyonu yapılıyor...")
            return self.rotate()

        return True

    def rotate(self, max_retries: int = 6) -> bool:
        """IP değişene kadar operatörü zorlayan ve her denemede süreyi uzatan döngü."""
        self._rotation_count += 1
        print(f"\n  ── IP Rotasyonu #{self._rotation_count} ──────────────────")

        for attempt in range(1, max_retries + 1):
            if attempt > 1:
                print(f"  [!] IP inatçı çıktı, operatör zorlanıyor. Deneme: ({attempt}/{max_retries})")

            old_ip = _get_current_ip()
            if old_ip:
                print(f"  [→] Eski IP: {old_ip}")
            else:
                old_ip = "Bilinmiyor"

            # 1. Uçak Modunu Aç (Sinyali Kes)
            _airplane_mode_on()
            
            # 2. Baz istasyonunun IP'yi düşürmesi için bekle (Her denemede +10 saniye ekler)
            # 1. Deneme: 15sn | 2. Deneme: 25sn | 3. Deneme: 35sn...
            bekleme_suresi = AIRPLANE_ON_BASE_WAIT + (attempt * 10)
            print(f"  [→] Operatörün IP'yi sıfırlaması için {bekleme_suresi} saniye uçak modunda bekleniyor...")
            time.sleep(bekleme_suresi) 

            # 3. Uçak Modunu Kapat (Sinyali Geri Getir)
            _airplane_mode_off()
            time.sleep(AIRPLANE_OFF_WAIT)

            # 4. İnternet Geldi mi Kontrol Et
            if not _wait_for_connection(timeout=30):
                print("  [✗] Bağlantı gelmedi, başa sarılıyor.")
                continue

            # 5. Yeni IP'yi Kontrol Et
            new_ip = _get_current_ip()
            
            if new_ip:
                if new_ip != old_ip and old_ip != "Bilinmiyor":
                    print(f"  [✓] IP BAŞARIYLA DEĞİŞTİ: {old_ip} → {new_ip}")
                    print(f"  ─────────────────────────────────────────────\n")
                    return True
                elif new_ip == old_ip:
                    print(f"  [!] IP AYNI KALDI ({new_ip}), süre artırılarak tekrar ediliyor...")
                    continue
                else:
                    print(f"  [✓] Yeni IP alındı: {new_ip}")
                    print(f"  ─────────────────────────────────────────────\n")
                    return True
            else:
                print("  [✗] Yeni IP adresi okunamadı, tekrar denenecek.")

        print("  [✗] Maksimum deneme sayısına ulaşıldı, IP DEĞİŞTİRİLEMEDİ!")
        print(f"  ─────────────────────────────────────────────\n")
        return False

    @property
    def rotation_count(self) -> int:
        return self._rotation_count

if __name__ == "__main__":
    rotator = IPRotator(accounts_per_rotation=3)
    if rotator.is_ready():
        print("[✓] Modül testi başarılı.")