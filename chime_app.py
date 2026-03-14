import tkinter as tk
from tkinter import ttk, messagebox
import pygame
import time
import threading
import os
from datetime import datetime
import sys
import socket
import json
from PIL import Image
import pystray
from pystray import MenuItem as item

# 二重起動防止用のソケット保持用
lock_socket = None
CONFIG_FILE = "config.json"

# キャラクター定義 (folder_name: display_name)
CHARACTERS = {
    "zundamon": "ずんだもん",
    "metan": "四国めたん",
    "tsumugi": "春日部つむぎ",
    "mochiko": "もち子さん",
    "whitecul": "WhiteCUL",
    "nurse_t": "ナースロボ＿タイプT",
    "no7": "No.7"
}

def resource_path(relative_path):
    """ リソースの絶対パスを取得する（PyInstaller用） """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {
        "mode": "interval",
        "interval": 1,
        "specific_minute": "",
        "date_format": 0,
        "always_on_top": False,
        "prevent_multiple": True,
        "volume": 0.5,
        "geometry": "260x400+100+100",
        "character": "zundamon",
        "minimize_to_tray": True
    }

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except:
        pass

def check_singleton():
    """ ソケットを用いて二重起動をチェック・ブロックする """
    global lock_socket
    try:
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock_socket.bind(('127.0.0.1', 65432))
    except socket.error:
        return False
    return True

class ChimeApp:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.root.title("voicevox_chime")
        
        # ジオメトリの復元
        geom = config.get("geometry", "260x400+100+100")
        self.root.geometry(geom)
        self.root.resizable(True, True)
        
        # アイコンの読み込み
        self.icon_path = resource_path("jihou.ico")
        if os.path.exists(self.icon_path):
            try:
                self.root.iconbitmap(self.icon_path)
            except:
                pass
        
        # 状態保持
        self.mode = tk.StringVar(value=config.get("mode", "interval"))
        self.interval = tk.IntVar(value=config.get("interval", 1))
        self.specific_minute = tk.StringVar(value=config.get("specific_minute", ""))
        self.date_format = tk.IntVar(value=config.get("date_format", 0))
        self.always_on_top = tk.BooleanVar(value=config.get("always_on_top", False))
        self.prevent_multiple = tk.BooleanVar(value=config.get("prevent_multiple", True))
        self.volume = tk.DoubleVar(value=config.get("volume", 0.5))
        self.character = tk.StringVar(value=config.get("character", "zundamon"))
        self.minimize_to_tray = tk.BooleanVar(value=config.get("minimize_to_tray", True))
        
        self.last_played_minute = -1
        self.last_countdown_sec = -1
        
        # Pygame Mixer初期化
        pygame.mixer.init()
        
        self.create_widgets()
        self.update_clock()
        self.toggle_on_top()
        
        # システムトレイの初期化
        self.tray_icon = None
        self.setup_tray()
        
        # 起動音
        self.play_sound("startup.wav")

        # 設定変更時の保存用トレース
        vars_to_trace = [self.mode, self.interval, self.specific_minute, 
                         self.date_format, self.always_on_top, 
                         self.prevent_multiple, self.volume, self.character,
                         self.minimize_to_tray]
        for v in vars_to_trace:
            v.trace_add("write", lambda *args: self.trigger_save())

        # ウィンドウイベントのバインド
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.bind("<Unmap>", self.on_minimize)

    def create_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding="5")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # 日付表示
        self.date_label = ttk.Label(self.main_frame, text="----.--.-- ---", font=("Helvetica", 11))
        self.date_label.pack(pady=(5, 0))
        self.date_label.bind("<Button-1>", self.toggle_date_format)

        # 時刻表示
        self.time_label = ttk.Label(self.main_frame, text="00:00:00", font=("Helvetica", 28, "bold"))
        self.time_label.pack(pady=(0, 2), expand=True)

        # キャラクター選択
        char_frame = ttk.Frame(self.main_frame)
        char_frame.pack(fill=tk.X, pady=2)
        ttk.Label(char_frame, text="声:", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=5)
        self.char_combobox = ttk.Combobox(char_frame, values=list(CHARACTERS.values()), state="readonly", width=18)
        self.char_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.char_combobox.set(CHARACTERS.get(self.character.get(), "ずんだもん"))
        self.char_combobox.bind("<<ComboboxSelected>>", self.on_char_change)

        # 音量スライダー
        vol_frame = ttk.Frame(self.main_frame)
        vol_frame.pack(fill=tk.X, pady=2)
        ttk.Label(vol_frame, text="音量:", font=("Helvetica", 9)).pack(side=tk.LEFT, padx=5)
        self.vol_scale = ttk.Scale(vol_frame, from_=0.0, to=1.0, variable=self.volume, orient=tk.HORIZONTAL)
        self.vol_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # モード選択
        mode_frame = ttk.LabelFrame(self.main_frame, text="通知設定", padding="2")
        mode_frame.pack(fill=tk.X, pady=2)
        
        ttk.Radiobutton(mode_frame, text="間隔", variable=self.mode, value="interval", command=self.update_ui).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="指定", variable=self.mode, value="specific", command=self.update_ui).pack(side=tk.LEFT, padx=5)

        self.settings_frame = ttk.Frame(mode_frame)
        self.settings_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.update_ui()

        # オプションエリア
        opt_frame = ttk.LabelFrame(self.main_frame, text="オプション", padding="2")
        opt_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(opt_frame, text="最前面", variable=self.always_on_top, command=self.toggle_on_top).grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Checkbutton(opt_frame, text="重複防止", variable=self.prevent_multiple).grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Checkbutton(opt_frame, text="最小化でトレイ格納", variable=self.minimize_to_tray).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=5)

        # ステータス
        self.status_label = ttk.Label(self.main_frame, text="稼働中", foreground="green", font=("Helvetica", 9))
        self.status_label.pack(pady=2)

    def setup_tray(self):
        # トレイ用アイコンの画像作成
        if os.path.exists(self.icon_path):
            image = Image.open(self.icon_path)
        else:
            image = Image.new('RGB', (64, 64), color=(255, 255, 255))

        menu = pystray.Menu(
            item('アプリを開く', self.show_window, default=True),
            item('READMEを表示', self.open_readme),
            item('終了', self.quit_app)
        )
        self.tray_icon = pystray.Icon("ChimeApp", image, "時報アプリ", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self, icon=None, item=None):
        self.root.after(0, self.root.deiconify)
        self.root.after(0, self.root.lift)

    def on_minimize(self, event):
        if self.minimize_to_tray.get() and self.root.state() == 'iconic':
            self.root.withdraw()

    def open_readme(self, icon=None, item=None):
        readme_path = resource_path("README.md")
        if os.path.exists(readme_path):
            os.startfile(readme_path)

    def quit_app(self, icon=None, item=None):
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.after(0, self.root.destroy)

    def on_char_change(self, event):
        selected_name = self.char_combobox.get()
        for k, v in CHARACTERS.items():
            if v == selected_name:
                self.character.set(k)
                self.play_sound("test.wav")
                break

    def update_ui(self):
        for widget in self.settings_frame.winfo_children():
            widget.destroy()

        if self.mode.get() == "interval":
            combo = ttk.Combobox(self.settings_frame, values=[1,2,3,5,10,15,20,30,60], textvariable=self.interval, width=3)
            combo.pack(side=tk.LEFT, padx=2)
            ttk.Label(self.settings_frame, text="分ごと").pack(side=tk.LEFT)
        else:
            entry = ttk.Entry(self.settings_frame, textvariable=self.specific_minute, width=3)
            entry.pack(side=tk.LEFT, padx=2)
            ttk.Label(self.settings_frame, text="分に通知").pack(side=tk.LEFT)

    def toggle_date_format(self, event=None):
        current = self.date_format.get()
        self.date_format.set((current + 1) % 2)
        self.update_clock()

    def toggle_on_top(self):
        self.root.attributes("-topmost", self.always_on_top.get())

    def trigger_save(self):
        new_config = {
            "mode": self.mode.get(),
            "interval": self.interval.get(),
            "specific_minute": self.specific_minute.get(),
            "date_format": self.date_format.get(),
            "always_on_top": self.always_on_top.get(),
            "prevent_multiple": self.prevent_multiple.get(),
            "volume": self.volume.get(),
            "character": self.character.get(),
            "minimize_to_tray": self.minimize_to_tray.get(),
            "geometry": self.root.geometry()
        }
        save_config(new_config)

    def on_closing(self):
        self.quit_app()

    def update_clock(self):
        now = datetime.now()
        days_en = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        days_jp = ["日", "月", "火", "水", "木", "金", "土"]
        
        if self.date_format.get() == 0:
            date_str = now.strftime("%Y.%m.%d") + f" {days_en[now.weekday()]}"
        else:
            date_str = now.strftime("%Y年%m月%d日") + f" ({days_jp[now.weekday()]})"
            
        self.date_label.config(text=date_str)
        self.time_label.config(text=now.strftime("%H:%M:%S"))
        
        self.check_countdown(now)
        self.check_chime(now)
        self.root.after(100, self.update_clock)

    def check_countdown(self, now):
        s = now.second
        m = now.minute
        next_m = (m + 1) % 60
        
        will_chime = False
        if self.mode.get() == "interval":
            if next_m % self.interval.get() == 0:
                will_chime = True
        else:
            try:
                if int(self.specific_minute.get()) == next_m:
                    will_chime = True
            except:
                pass
        
        if not will_chime:
            return

        if 55 <= s <= 59:
            if self.last_countdown_sec != s:
                self.last_countdown_sec = s
                file = "beep_long.wav" if s == 59 else "beep_short.wav"
                self.play_sound(file, is_common=True)
                if s == 59:
                    self.status_label.config(text="まもなく時報", foreground="orange")
                else:
                    self.status_label.config(text=f"あと {60-s}秒", foreground="blue")

    def check_chime(self, now):
        s = now.second
        m = now.minute
        if s != 0 or m == self.last_played_minute:
            return
        should_play = False
        if self.mode.get() == "interval":
            if m % self.interval.get() == 0:
                should_play = True
        else:
            try:
                if int(self.specific_minute.get()) == m:
                    should_play = True
            except:
                pass
        if should_play:
            self.last_played_minute = m
            self.status_label.config(text="再生中", foreground="red")
            threading.Thread(target=self.play_sequential, args=(now.hour, m)).start()

    def play_sequential(self, h, m):
        hour_file = f"{h:02d}hour.wav"
        min_file = f"{m:02d}min.wav"
        self.play_sound(hour_file, wait=True)
        self.play_sound(min_file, wait=False)
        self.root.after(5000, lambda: self.status_label.config(text="稼働中", foreground="green"))

    def play_sound(self, filename, wait=False, is_common=False):
        if is_common:
            path = resource_path(os.path.join("audio", filename))
        else:
            char_subdir = self.character.get()
            path = resource_path(os.path.join("audio", char_subdir, filename))
        if not os.path.exists(path):
            return
        try:
            sound = pygame.mixer.Sound(path)
            sound.set_volume(self.volume.get())
            sound.play()
            if wait:
                time.sleep(sound.get_length())
        except:
            pass

if __name__ == "__main__":
    current_config = load_config()
    if current_config.get("prevent_multiple", True):
        if not check_singleton():
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("警告", "アプリはすでに起動しています。")
            sys.exit()
    root = tk.Tk()
    app = ChimeApp(root, current_config)
    root.mainloop()
