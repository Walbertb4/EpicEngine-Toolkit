"""
Multi_Instance.py
=================
Epic Provisioning Engine için paralel işlem ve Thread-Safe IP Rotasyon Yöneticisi.
Bu modül eski sistemleri bozmadan dışarıdan yöneten (Orchestrator) bir köprüdür.
"""

import concurrent.futures
import threading

import create_epic_acc
import claim_games
from ip_rotator import IPRotator

# Thread kilidi (Race condition ve dosyaya karışık yazmayı önleyici)
lock = threading.Lock()

class MultiCounter:
    """Multi-thread işlemlerinde sayaçların çökmemesi için Lock kullanır."""
    def __init__(self, total: int, ui_callback=None):
        self.total = total
        self.current = 0
        self.success = 0
        self.fail = 0
        self.ui_callback = ui_callback

    def tick(self, email: str, worker_id: int):
        with lock:
            self.current += 1
            print(f"\n[Worker {worker_id}] İşleme başlanıyor -> {email} | Sıra: {self.current}/{self.total}")

    def mark_success(self):
        with lock:
            self.success += 1
            if self.ui_callback: self.ui_callback(self.success, self.fail, self.current)

    def mark_fail(self):
        with lock:
            self.fail += 1
            if self.ui_callback: self.ui_callback(self.success, self.fail, self.current)

def run_multi_batch(accounts_list, mode, target_url, counter, use_rotator, grid_configs, is_retry=False):
    # Rotatörü her grup bittiğinde (3 hesapta bir) 1 kez dönecek şekilde ayarlıyoruz.
    rotator = IPRotator(accounts_per_rotation=1) if use_rotator else None
    failed_accounts = []
    chunk_size = len(grid_configs)
    
    for i in range(0, len(accounts_list), chunk_size):
        chunk = accounts_list[i:i+chunk_size]
        
        # GUI'den Stop sinyali geldiyse ana döngüyü kır
        if not create_epic_acc.SharedState.is_running or not claim_games.SharedState.is_running:
            print("\n[SYSTEM] Multi-Instance operasyonu iptal edildi.")
            break
            
        # --- IP ROTASYON BARİYERİ ---
        # Önceki grubun BÜTÜN THREAD'leri bittiği için artık IP rotasyonu yapmak güvenli.
        if i > 0 and rotator:
            print("\n[IP SYNC] 3'lü grup tamamlandı. Yeni hesaplara geçmeden önce IP Rotasyonu yapılıyor...")
            rotator.rotate()
            
        print(f"\n[MULTI-BATCH] YENİ GRUP BAŞLIYOR... Bu gruptaki hesap sayısı: {len(chunk)}")
        
        # Paralel İşlem Havuzu (3 İşçi)
        with concurrent.futures.ThreadPoolExecutor(max_workers=chunk_size) as executor:
            future_to_acc = {}
            
            for idx, acc in enumerate(chunk):
                worker_id = idx + 1
                pos = grid_configs[idx]
                profile_name = f"worker_{worker_id}"
                
                if mode == "create":
                    email, pwd = acc[0], acc[1]
                    counter.tick(email, worker_id)
                    fut = executor.submit(create_epic_acc.process_account, email, pwd, 2, profile_name, pos)
                else: # claim
                    parts = acc.split(":")
                    email, pwd = parts[-2].strip(), parts[-1].strip()
                    counter.tick(email, worker_id)
                    fut = executor.submit(claim_games.process_account, email, pwd, target_url, 2, profile_name, pos)
                    
                future_to_acc[fut] = acc

            # Tüm işçilerin (Thread) bitmesini bekle ve sonuçları ana thread'de GÜVENLE dosyaya yaz
            for future in concurrent.futures.as_completed(future_to_acc):
                acc = future_to_acc[future]
                try:
                    basarili, sonuc = future.result()
                    
                    if mode == "create":
                        email, pwd = acc[0], acc[1]
                        if basarili:
                            print(f"  [✓ WORKER BAŞARILI] {email} -> {sonuc}")
                            create_epic_acc._save_success(sonuc, email, pwd)
                            counter.mark_success()
                        else:
                            print(f"  [✗ WORKER HATA] {email} -> {sonuc}")
                            if not is_retry:
                                create_epic_acc._save_failed(email, pwd, sonuc)
                                failed_accounts.append(acc)
                            counter.mark_fail()
                            
                    elif mode == "claim":
                        if basarili:
                            print(f"  [✓ WORKER OYUN ALINDI] -> {sonuc}")
                            claim_games._save_success(acc, target_url)
                            counter.mark_success()
                        else:
                            print(f"  [✗ WORKER HATA] -> {sonuc}")
                            if not is_retry:
                                claim_games._save_failed(acc, sonuc, target_url)
                                failed_accounts.append(acc)
                            counter.mark_fail()
                            
                except Exception as e:
                    print(f"  [!] Beklenmedik Thread Hatası: {str(e)}")
                    counter.mark_fail()
                    if not is_retry: failed_accounts.append(acc)
                    
    return failed_accounts

def start_multi_create(credentials_list, use_rotator, grid_configs, ui_callback):
    create_epic_acc.SharedState.is_running = True
    create_epic_acc.SharedState.is_paused = False
    
    counter = MultiCounter(total=len(credentials_list), ui_callback=ui_callback)
    print("\n[MULTI] 3x CREATE ACCOUNTS MODU BAŞLATILDI")
    
    failed_accounts = run_multi_batch(credentials_list, "create", None, counter, use_rotator, grid_configs, is_retry=False)
    
    if create_epic_acc.SharedState.is_running and failed_accounts:
        print(f"\n[SYSTEM] ANA LİSTE BİTTİ. Başarısız olan {len(failed_accounts)} hesap TEKRAR DENENİYOR...")
        counter.total += len(failed_accounts) 
        run_multi_batch(failed_accounts, "create", None, counter, use_rotator, grid_configs, is_retry=True)
    
    if create_epic_acc.SharedState.is_running:
        print("\n[SYSTEM] TÜM MULTI CREATE GÖREVLERİ TAMAMLANDI!")

def start_multi_claim(credentials_list, use_rotator, target_url, grid_configs, ui_callback):
    claim_games.SharedState.is_running = True
    claim_games.SharedState.is_paused = False
    
    counter = MultiCounter(total=len(credentials_list), ui_callback=ui_callback)
    print(f"\n[MULTI] 3x CLAIM GAMES MODU BAŞLATILDI. Hedef: {target_url}")
    
    failed_accounts = run_multi_batch(credentials_list, "claim", target_url, counter, use_rotator, grid_configs, is_retry=False)
    
    if claim_games.SharedState.is_running and failed_accounts:
        print(f"\n[SYSTEM] ANA LİSTE BİTTİ. Başarısız olan {len(failed_accounts)} hesap TEKRAR DENENİYOR...")
        counter.total += len(failed_accounts) 
        run_multi_batch(failed_accounts, "claim", target_url, counter, use_rotator, grid_configs, is_retry=True)
        
    if claim_games.SharedState.is_running:
        print("\n[SYSTEM] TÜM MULTI CLAIM GÖREVLERİ TAMAMLANDI!")