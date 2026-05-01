import customtkinter as ctk
from tkinter import filedialog
import time
import threading
import sys
import os
import urllib.request
import re

# Modüllerimizi import ediyoruz
import create_epic_acc
import claim_games
import check_games
import Multi_Instance  # YENİ MODÜL

# --- THEME SETTINGS ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG_MAIN = "#0F0F0F"       
BG_SIDEBAR = "#141414"    
BG_CARD = "#1C1C1C"       
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#8A8A8A"
ACCENT_GREEN = "#2ECC71"
ACCENT_RED = "#E74C3C"
ACCENT_GOLD = "#F1C40F"
ACCENT_PURPLE = "#9B59B6"

class PrintRedirector:
    def __init__(self, textbox):
        self.textbox = textbox
    def write(self, message):
        if message.strip() != "":
            self.textbox.after(0, self._insert_text, message)
    def _insert_text(self, message):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")
    def flush(self): pass

class EpicBotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Epic Provisioning Engine | Dashboard")
        self.geometry("1150x700")
        self.configure(fg_color=BG_MAIN)
        self.resizable(False, False)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.is_running = False
        self.uptime_seconds = 0
        self.total_accounts = 0
        self.processed_accounts = 0
        self.credentials_list = []
        self.raw_credentials_list = [] 

        self.create_sidebar()
        self.create_main_area()
        self.update_timers()

        sys.stdout = PrintRedirector(self.terminal)
        threading.Thread(target=self.ip_fetch_loop, daemon=True).start()

    def ip_fetch_loop(self):
        while True:
            try:
                ip = urllib.request.urlopen("https://api.ipify.org", timeout=5).read().decode("utf-8").strip()
                self.lbl_ip.after(0, lambda: self.lbl_ip.configure(text=ip, text_color="#3498DB"))
            except Exception:
                self.lbl_ip.after(0, lambda: self.lbl_ip.configure(text="Offline", text_color=ACCENT_RED))
            time.sleep(5)

    def create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="EPIC ENGINE", font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_PRIMARY)
        self.logo_label.grid(row=0, column=0, padx=20, pady=(25, 20))

        self.btn_load_file = ctk.CTkButton(self.sidebar_frame, text="📁 Load Account File", command=self.load_file, fg_color="#2A2A2A", hover_color="#3A3A3A")
        self.btn_load_file.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.lbl_file_name = ctk.CTkLabel(self.sidebar_frame, text="No file selected", text_color=TEXT_SECONDARY, font=("Inter", 11))
        self.lbl_file_name.grid(row=2, column=0, padx=20, pady=(0, 15))

        self.lbl_mode = ctk.CTkLabel(self.sidebar_frame, text="Operation Mode:", font=ctk.CTkFont(weight="bold"), text_color=TEXT_SECONDARY)
        self.lbl_mode.grid(row=3, column=0, padx=20, pady=(15, 10), sticky="w")
        
        self.radio_var = ctk.IntVar(value=0)
        
        self.rb_create = ctk.CTkRadioButton(self.sidebar_frame, text="1. Create Accounts", variable=self.radio_var, value=0)
        self.rb_create.grid(row=4, column=0, padx=20, pady=8, sticky="w")
        
        self.rb_claim = ctk.CTkRadioButton(self.sidebar_frame, text="2. Claim Free Game", variable=self.radio_var, value=1)
        self.rb_claim.grid(row=5, column=0, padx=20, pady=8, sticky="w")
        
        self.rb_check = ctk.CTkRadioButton(self.sidebar_frame, text="3. Check Free Games", variable=self.radio_var, value=2)
        self.rb_check.grid(row=6, column=0, padx=20, pady=8, sticky="w")

        self.switch_ip = ctk.CTkSwitch(self.sidebar_frame, text="Mobile IP Rotator")
        self.switch_ip.select()
        self.switch_ip.grid(row=7, column=0, padx=20, pady=(20, 5), sticky="w")

        self.switch_multi = ctk.CTkSwitch(self.sidebar_frame, text="3x Multi-Instance")
        self.switch_multi.grid(row=8, column=0, padx=20, pady=(5, 15), sticky="w")

        self.btn_start = ctk.CTkButton(self.sidebar_frame, text="▶ START ENGINE", command=self.start_engine, fg_color="#298F4A", hover_color="#1E6E38", font=ctk.CTkFont(weight="bold"))
        self.btn_start.grid(row=10, column=0, padx=20, pady=(20, 5), sticky="ew")
        
        self.btn_pause = ctk.CTkButton(self.sidebar_frame, text="⏸ PAUSE", command=self.pause_engine, fg_color="#D38415", hover_color="#A86A11")
        self.btn_pause.grid(row=11, column=0, padx=20, pady=5, sticky="ew")

        self.btn_stop = ctk.CTkButton(self.sidebar_frame, text="⏹ STOP", command=self.stop_engine, fg_color="#A5332E", hover_color="#7A2521")
        self.btn_stop.grid(row=12, column=0, padx=20, pady=(5, 30), sticky="ew")

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, padx=20, pady=25, sticky="nsew")
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.stats_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.stats_container.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        self.stats_container.grid_columnconfigure((0,1,2,3,4,5), weight=1)

        self.lbl_ip = self.create_metric_card(self.stats_container, 0, "Network IP", "Fetching...", "#3498DB")
        self.lbl_total_accounts = self.create_metric_card(self.stats_container, 1, "Loaded", "0", TEXT_PRIMARY)
        self.lbl_success = self.create_metric_card(self.stats_container, 2, "Success", "0", ACCENT_GREEN)
        self.lbl_fail = self.create_metric_card(self.stats_container, 3, "Failed", "0", ACCENT_RED)
        self.lbl_uptime = self.create_metric_card(self.stats_container, 4, "Uptime", "00:00:00", ACCENT_GOLD)
        self.lbl_eta = self.create_metric_card(self.stats_container, 5, "ETA", "--:--", ACCENT_PURPLE)

        self.progressbar = ctk.CTkProgressBar(self.main_frame, progress_color=ACCENT_GREEN, height=8, fg_color=BG_CARD)
        self.progressbar.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        self.progressbar.set(0)

        self.game_frame = ctk.CTkFrame(self.main_frame, fg_color=BG_CARD, corner_radius=8)
        self.game_frame.grid(row=2, column=0, sticky="ew", pady=(0, 20), ipadx=10, ipady=10)
        self.game_frame.grid_columnconfigure(1, weight=1)
        self.lbl_game = ctk.CTkLabel(self.game_frame, text="Target Game URL:", font=ctk.CTkFont(weight="bold"))
        self.lbl_game.grid(row=0, column=0, padx=15, pady=10)
        self.entry_url = ctk.CTkEntry(self.game_frame, placeholder_text="Paste custom Epic Store URL here...")
        self.entry_url.grid(row=0, column=1, padx=15, pady=10, sticky="ew")

        self.lbl_term = ctk.CTkLabel(self.main_frame, text=">_ SYSTEM TERMINAL", font=ctk.CTkFont(weight="bold", size=14))
        self.lbl_term.grid(row=3, column=0, sticky="nw", pady=(0, 5))
        self.terminal = ctk.CTkTextbox(self.main_frame, font=("Consolas", 13), fg_color="#080808", text_color=TEXT_SECONDARY, corner_radius=8, border_width=1, border_color="#2A2A2A")
        self.terminal.grid(row=4, column=0, sticky="nsew")
        print("[SYSTEM] UI initialized. Network Listener Active.")

    def create_metric_card(self, parent, col, title, initial_val, val_color):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
        card.grid(row=0, column=col, padx=5, sticky="nsew", ipadx=5, ipady=12)
        lbl_title = ctk.CTkLabel(card, text=title, font=("Inter", 11), text_color=TEXT_SECONDARY)
        lbl_title.pack(anchor="center", pady=(0, 2))
        lbl_val = ctk.CTkLabel(card, text=initial_val, font=ctk.CTkFont(size=20, weight="bold"), text_color=val_color)
        lbl_val.pack(anchor="center", expand=True)
        return lbl_val

    def load_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not file_path: return
        
        file_name = file_path.split("/")[-1]
        self.lbl_file_name.configure(text=file_name, text_color=ACCENT_GREEN)
        
        try:
            self.raw_credentials_list = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self.raw_credentials_list.append(line)

            self.total_accounts = len(self.raw_credentials_list)
            self.lbl_total_accounts.configure(text=str(self.total_accounts))
            self.progressbar.set(0)
            self.lbl_eta.configure(text="--:--")
            
            print(f"[FILE] Dosya Yüklendi. {self.total_accounts} hesap hafızaya alındı.")

        except Exception as e:
            print(f"[ERROR] Dosya okunamadı: {str(e)}")

    def update_ui_counters(self, success_count, fail_count, current_count):
        self.processed_accounts = current_count
        self.lbl_success.after(0, lambda: self.lbl_success.configure(text=str(success_count)))
        self.lbl_fail.after(0, lambda: self.lbl_fail.configure(text=str(fail_count)))
        
        if self.total_accounts > 0:
            progress = current_count / self.total_accounts
            self.progressbar.after(0, lambda: self.progressbar.set(progress))

    def _update_eta(self):
        if not self.is_running: return
        kalan_hesap = self.total_accounts - self.processed_accounts
        if kalan_hesap > 0:
            eta_seconds = kalan_hesap * 60
            target_time = time.time() + eta_seconds
            self.lbl_eta.configure(text=time.strftime('%H:%M', time.localtime(target_time)))
        elif kalan_hesap <= 0:
            self.lbl_eta.configure(text="--:--")

    def update_timers(self):
        if self.is_running:
            self.uptime_seconds += 1
            self.lbl_uptime.configure(text=time.strftime('%H:%M:%S', time.gmtime(self.uptime_seconds)))
            self._update_eta()

        self.after(1000, self.update_timers)

    def _run_bot_thread(self):
        use_rotator = bool(self.switch_ip.get() == 1)
        use_multi = bool(self.switch_multi.get() == 1)
        mode = self.radio_var.get()
        
        grid_configs = None
        if use_multi:
            # Ekranı 4'e bölecek matematik hesaplamaları
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = sw // 2, sh // 2
            
            # Arayüzü Sol Üst (Q1) köşeye taşı
            self.geometry(f"{w}x{h}+0+0")
            
            grid_configs = [
                {"x": w, "y": 0, "w": w, "h": h},       # Q2: Sağ Üst
                {"x": 0, "y": h, "w": w, "h": h},       # Q3: Sol Alt
                {"x": w, "y": h, "w": w, "h": h}        # Q4: Sağ Alt
            ]
        else:
            self.geometry("1150x700")

        if mode == 0:
            if use_multi:
                Multi_Instance.start_multi_create(self.credentials_list, use_rotator, grid_configs, self.update_ui_counters)
            else:
                create_epic_acc.start_automation(self.credentials_list, use_rotator, self.update_ui_counters)
        elif mode == 1:
            target_url = self.entry_url.get().strip()
            if use_multi:
                Multi_Instance.start_multi_claim(self.credentials_list, use_rotator, target_url, grid_configs, self.update_ui_counters)
            else:
                claim_games.start_claiming(self.credentials_list, use_rotator, target_url, self.update_ui_counters)
        elif mode == 2:
            target_url = self.entry_url.get().strip()
            check_games.start_checking(self.credentials_list, target_url, self.update_ui_counters)
            
        self.is_running = False
        
        self.btn_start.after(0, lambda: self.btn_start.configure(text="▶ START ENGINE", state="normal"))
        self.lbl_eta.after(0, lambda: self.lbl_eta.configure(text="--:--"))

    def start_engine(self):
        if not hasattr(self, 'raw_credentials_list') or not self.raw_credentials_list:
            print("[!] Lütfen önce sol menüden hesap dosyasını yükleyin.")
            return

        # Üç modülün de Pause durumunu kontrol edip Devam Ettir (Resume)
        if create_epic_acc.SharedState.is_paused or claim_games.SharedState.is_paused or check_games.SharedState.is_paused:
            create_epic_acc.SharedState.is_paused = False
            claim_games.SharedState.is_paused = False
            check_games.SharedState.is_paused = False
            
            self.is_running = True
            self.btn_start.configure(text="⚙ RUNNING...", state="disabled")
            print("[SYSTEM] Motor duraklatmadan DEVAM ediyor...")
            return

        if self.is_running: return

        mode = self.radio_var.get()
        self.credentials_list = []
        skipped = 0

        if mode == 0: # 1. Create Accounts Modu
            success_file = os.path.join(os.path.dirname(__file__), "accounts", "successfull_accounts.txt")
            successful_emails = set()
            if os.path.exists(success_file):
                with open(success_file, "r", encoding="utf-8") as sf:
                    for line in sf:
                        parts = line.strip().split(":")
                        if len(parts) >= 2: successful_emails.add(parts[-2].strip())
                        
            for raw_line in self.raw_credentials_list:
                parts = raw_line.split(":")
                if len(parts) >= 2:
                    email = parts[-2].strip()
                    pwd = parts[-1].strip()
                    if email in successful_emails:
                        skipped += 1
                    else:
                        self.credentials_list.append((email, pwd))
                        
        elif mode == 1: # 2. Claim Free Game Modu
            target_url = self.entry_url.get().strip()
            if not target_url:
                print("\n[!] HATA: Lütfen arayüzden Target Game URL kısmına oyun linkini yapıştırın!")
                self.is_running = False
                self.btn_start.configure(text="▶ START ENGINE", state="normal")
                return
                
            raw_slug = target_url.strip("/").split("?")[0].split("/")[-1]
            game_slug = re.sub(r'-[a-fA-F0-9]{6,}$', '', raw_slug)
            
            success_file = os.path.join(os.path.dirname(__file__), "game_accounts", game_slug, "successfull_accounts.txt")
            
            successful_emails = set()
            if os.path.exists(success_file):
                with open(success_file, "r", encoding="utf-8") as sf:
                    for line in sf:
                        parts = line.strip().split(":")
                        if len(parts) >= 2: successful_emails.add(parts[-2].strip())
                        
            for raw_line in self.raw_credentials_list:
                parts = raw_line.split(":")
                if len(parts) >= 2:
                    email = parts[-2].strip() 
                    if email in successful_emails:
                        skipped += 1
                    else:
                        self.credentials_list.append(raw_line)
                        
        elif mode == 2: # 3. Check Accounts Modu
            target_url = self.entry_url.get().strip()
            if not target_url:
                print("\n[!] HATA: Lütfen arayüzden Target Game URL kısmına kontrol edilecek oyunun linkini yapıştırın!")
                self.is_running = False
                self.btn_start.configure(text="▶ START ENGINE", state="normal")
                return
                
            raw_slug = target_url.strip("/").split("?")[0].split("/")[-1]
            game_slug = re.sub(r'-[a-fA-F0-9]{6,}$', '', raw_slug)
            
            success_file = os.path.join(os.path.dirname(__file__), "game_accounts", game_slug, "checked_accounts.txt")
            
            successful_emails = set()
            if os.path.exists(success_file):
                with open(success_file, "r", encoding="utf-8") as sf:
                    for line in sf:
                        parts = line.strip().split(":")
                        if len(parts) >= 2: successful_emails.add(parts[-2].strip())
                        
            for raw_line in self.raw_credentials_list:
                parts = raw_line.split(":")
                if len(parts) >= 2:
                    email = parts[-2].strip() 
                    if email in successful_emails:
                        skipped += 1
                    else:
                        self.credentials_list.append(raw_line)

        # UI Sayaçlarını Güncelle
        self.total_accounts = len(self.credentials_list)
        self.lbl_total_accounts.configure(text=str(self.total_accounts))
        
        if skipped > 0:
            print(f"\n[FILTER] İlgili klasörde zaten başarılı olan {skipped} hesap atlandı!")
            
        if self.total_accounts == 0:
            print("[SYSTEM] İşlenecek hesap kalmadı.")
            return

        # Üç modülün de durumlarını sıfırla
        create_epic_acc.SharedState.is_running = True
        create_epic_acc.SharedState.is_paused = False
        claim_games.SharedState.is_running = True
        claim_games.SharedState.is_paused = False
        check_games.SharedState.is_running = True
        check_games.SharedState.is_paused = False
        
        self.is_running = True
        self.processed_accounts = 0
        self.uptime_seconds = 0
        self.progressbar.set(0)
        self.lbl_success.configure(text="0")
        self.lbl_fail.configure(text="0")
        
        self.btn_start.configure(text="⚙ RUNNING...", state="disabled")
        
        print(f"[SYSTEM] MOTOR ATEŞLENDİ. Toplam {self.total_accounts} hesap işleniyor...")
        threading.Thread(target=self._run_bot_thread, daemon=True).start()

    def pause_engine(self):
        if self.is_running:
            self.is_running = False
            
            create_epic_acc.SharedState.is_paused = True
            claim_games.SharedState.is_paused = True
            check_games.SharedState.is_paused = True
            
            self.btn_start.configure(text="▶ RESUME", state="normal")
            print("[SYSTEM] ⏸ Motor DURAKLATILDI. Lütfen bekleyin...")

    def stop_engine(self):
        if not self.is_running:
            return

        self.is_running = False
        
        create_epic_acc.SharedState.is_running = False
        create_epic_acc.SharedState.is_paused = False
        claim_games.SharedState.is_running = False
        claim_games.SharedState.is_paused = False
        check_games.SharedState.is_running = False
        check_games.SharedState.is_paused = False
        
        self.uptime_seconds = 0
        self.lbl_uptime.configure(text="00:00:00")
        self.lbl_eta.configure(text="--:--")
        self.progressbar.set(0)
        self.btn_start.configure(text="▶ START ENGINE", state="normal")
        print("[SYSTEM] 🛑 ACİL STOP! Tüm işlemler iptal edildi.")

if __name__ == "__main__":
    app = EpicBotGUI()
    app.mainloop()
