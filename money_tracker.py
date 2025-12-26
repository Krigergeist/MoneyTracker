import tkinter as tk
from tkinter import messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import keyboard
import pandas as pd
from datetime import datetime
import os
import threading
import subprocess

# File untuk menyimpan data
DATA_FILE = 'money_tracker.csv'

# Hotkey default (bisa diubah)
current_hotkey = 'ctrl+shift+a'

# Versi dari Git
def get_git_version():
    try:
        return subprocess.check_output(['git', 'describe', '--tags', '--dirty', '--always']).decode('utf-8').strip()
    except:
        return "dev"
APP_VERSION = get_git_version().replace('v', '')

# Variabel global
current_view_mode = 'both'  # both, raw, delta
auto_mode = False
auto_interval = 60  # default detik
auto_timer = None

# Parse amount dengan singkatan
def parse_amount(input_str):
    suffixes = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12, 'qa': 1e15}
    input_str = input_str.lower().strip()
    for suffix, multiplier in suffixes.items():
        if input_str.endswith(suffix):
            try:
                return float(input_str[:-len(suffix)]) * multiplier
            except ValueError:
                return None
    try:
        return float(input_str)
    except ValueError:
        return None

# Simpan data
def save_data(amount):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=['Timestamp', 'Amount'])
    new_row = pd.DataFrame({'Timestamp': [timestamp], 'Amount': [amount]})
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

# Load data
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=['Timestamp', 'Amount'])

# Popup input
def show_input_popup():
    popup = tk.Toplevel()
    popup.title("Input Jumlah Uang")
    popup.geometry("300x150+{}+{}".format(
        popup.winfo_screenwidth()//2 - 150,
        popup.winfo_screenheight()//2 - 75
    ))
    popup.configure(bg='#2E2E2E')
    popup.attributes('-topmost', True)
    popup.attributes('-alpha', 1.0)
    popup.attributes('-toolwindow', True)
    popup.attributes('-disabled', False)
    popup.focus_force()
    popup.grab_set()
    popup.lift()
    popup.update()

    label = tk.Label(popup, text="Masukkan angka (e.g., 2k, 2qa):", 
                     bg='#2E2E2E', fg='white', font=('Arial', 12, 'bold'))
    label.pack(pady=20)

    entry = tk.Entry(popup, font=('Arial', 14), justify='center', width=20)
    entry.pack(pady=10)
    entry.focus_set()

    def submit():
        amount = parse_amount(entry.get())
        if amount is not None and amount > 0:
            save_data(amount)
            messagebox.showinfo("Sukses", f"Ditambahkan: {amount:,}".replace(',', '.'), parent=popup)
            popup.destroy()
            update_chart()
        elif amount == 0:
            messagebox.showwarning("Peringatan", "Angka tidak boleh 0!", parent=popup)
        else:
            messagebox.showerror("Error", "Input tidak valid!\nContoh: 2k, 5m, 10qa", parent=popup)

    entry.bind('<Return>', lambda event: submit())
    popup.bind('<Escape>', lambda e: popup.destroy())
    popup.protocol("WM_DELETE_WINDOW", popup.destroy)

# Update grafik dengan grid
def update_chart():
    global canvas, fig, ax
    df = load_data()
    if df.empty:
        ax.clear()
        ax.text(0.5, 0.5, 'Belum ada data', ha='center', va='center',
                transform=ax.transAxes, fontsize=16, color='white')
        canvas.draw()
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.sort_values('Timestamp', inplace=True)
    df['Raw'] = df['Amount']
    df['Delta'] = df['Amount'].diff().fillna(0)

    ax.clear()
    for ax_child in fig.axes[1:]:
        fig.delaxes(ax_child)

    show_raw = current_view_mode in ['raw', 'both']
    show_delta = current_view_mode in ['delta', 'both']

    if show_raw:
        ax.plot(df['Timestamp'], df['Raw'], marker='o', color='#2196F3', linewidth=3, label='Nilai Input (Raw)')

    if show_delta:
        ax.plot(df['Timestamp'], df['Delta'], marker='s', color='#F44336', linewidth=2, linestyle='--', label='Selisih (Delta)')

    if show_raw and show_delta:
        ax2 = ax.twinx()
        ax2.plot(df['Timestamp'], df['Delta'], marker='s', color='#F44336', linewidth=2, linestyle='--', label='Selisih (Delta)')
        ax2.set_ylabel('Selisih dari Sebelumnya', color='#F44336', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='#F44336')

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', facecolor='#333333', edgecolor='white', labelcolor='white')
    else:
        ax.legend(loc='upper left', facecolor='#333333', edgecolor='white', labelcolor='white')

    ax.set_title(f'Grafik Uang - Mode: {current_view_mode.capitalize()}', fontsize=14, color='white')
    ax.set_xlabel('Waktu', color='white')
    ax.set_ylabel('Nilai Input', color='#2196F3', fontsize=12)
    ax.tick_params(colors='white')
    ax.set_facecolor('#333333')
    fig.patch.set_facecolor('#2E2E2E')
    ax.grid(True, color='gray', linestyle='--', linewidth=0.5)  # Tambah grid
    plt.xticks(rotation=45)
    plt.tight_layout()
    canvas.draw()

# Window pengaturan shortcut dengan detect key press
def open_settings():
    global current_hotkey
    settings_win = tk.Toplevel()
    settings_win.title("Pengaturan Shortcut")
    settings_win.geometry("400x200")
    settings_win.configure(bg='#2E2E2E')
    settings_win.attributes('-topmost', True)

    tk.Label(settings_win, text="Tekan tombol atau ketik shortcut baru:", bg='#2E2E2E', fg='white', font=('Arial', 12)).pack(pady=20)
    tk.Label(settings_win, text="(Contoh: ctrl+shift+a, f12)", bg='#2E2E2E', fg='gray', font=('Arial', 9)).pack()

    entry = tk.Entry(settings_win, font=('Arial', 12), width=30, justify='center')
    entry.insert(0, current_hotkey)
    entry.pack(pady=10)

    def on_key_press(event):
        # Detect kombinasi tombol menggunakan keyboard lib
        try:
            hotkey = keyboard.get_hotkey_name()
            if hotkey:
                entry.delete(0, tk.END)
                entry.insert(0, hotkey)
        except:
            pass

    settings_win.bind('<Key>', on_key_press)

    def apply_hotkey():
        global current_hotkey
        new_key = entry.get().strip().lower()
        if new_key:
            try:
                keyboard.remove_hotkey(current_hotkey)
            except:
                pass
            try:
                keyboard.add_hotkey(new_key, show_input_popup)
                current_hotkey = new_key
                messagebox.showinfo("Sukses", f"Shortcut diubah menjadi: {new_key.upper()}")
                settings_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Shortcut tidak valid!\nError: {e}")
        else:
            messagebox.showwarning("Peringatan", "Shortcut tidak boleh kosong!")

    tk.Button(settings_win, text="Terapkan", command=apply_hotkey, bg='#4CAF50', fg='white', font=('Arial', 12)).pack(pady=20)

# Fungsi auto popup
def auto_popup():
    global auto_timer
    if auto_mode:
        show_input_popup()
        auto_timer = threading.Timer(auto_interval, auto_popup)
        auto_timer.start()

# Fungsi utama GUI
def main_window():
    global canvas, fig, ax, chart_type_combo, view_mode_combo, auto_mode_combo, interval_entry

    root = tk.Tk()
    root.title(f"Money Tracker v{APP_VERSION}")
    root.geometry("900x700")
    root.configure(bg='#2E2E2E')

    # Grafik dengan toolbar untuk scroll/zoom
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#333333')

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(pady=20)

    # Toolbar untuk scroll/zoom saat hover
    toolbar = NavigationToolbar2Tk(canvas, root)
    toolbar.update()
    toolbar.pack(pady=5)

    control_frame = tk.Frame(root, bg='#2E2E2E')
    control_frame.pack(pady=10)

    tk.Label(control_frame, text="Jenis Grafik:", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
    chart_types = ['Line', 'Bar', 'Area', 'Scatter']
    chart_type_combo = ttk.Combobox(control_frame, values=chart_types, font=('Arial', 10), width=10, state='readonly')
    chart_type_combo.current(0)
    chart_type_combo.pack(side=tk.LEFT, padx=5)

    tk.Label(control_frame, text="Mode Tampilan:", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=20)
    view_modes = ['Both (Dual)', 'Nilai Input Saja', 'Selisih Saja']
    view_mode_combo = ttk.Combobox(control_frame, values=view_modes, font=('Arial', 10), width=18, state='readonly')
    view_mode_combo.current(0)
    view_mode_combo.pack(side=tk.LEFT, padx=5)

    def on_chart_change(event):
        global current_view_mode
        mode_text = view_mode_combo.get()
        if mode_text == 'Both (Dual)':
            current_view_mode = 'both'
        elif mode_text == 'Nilai Input Saja':
            current_view_mode = 'raw'
        else:
            current_view_mode = 'delta'
        update_chart()

    chart_type_combo.bind('<<ComboboxSelected>>', on_chart_change)
    view_mode_combo.bind('<<ComboboxSelected>>', on_chart_change)

    # Frame untuk opsi auto/manual
    auto_frame = tk.Frame(root, bg='#2E2E2E')
    auto_frame.pack(pady=10)

    tk.Label(auto_frame, text="Mode Popup:", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
    auto_options = ['Manual', 'Auto']
    auto_mode_combo = ttk.Combobox(auto_frame, values=auto_options, font=('Arial', 10), width=10, state='readonly')
    auto_mode_combo.current(0)
    auto_mode_combo.pack(side=tk.LEFT, padx=5)

    tk.Label(auto_frame, text="Interval (detik):", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
    interval_entry = tk.Entry(auto_frame, font=('Arial', 10), width=5)
    interval_entry.insert(0, str(auto_interval))
    interval_entry.pack(side=tk.LEFT, padx=5)

    def on_mode_change(event):
        global auto_mode, auto_interval, auto_timer
        if auto_mode_combo.get() == 'Auto':
            try:
                auto_interval = int(interval_entry.get())
                if auto_interval <= 0:
                    raise ValueError
                auto_mode = True
                auto_popup()  # Mulai timer
            except ValueError:
                messagebox.showerror("Error", "Interval harus angka positif!")
                auto_mode_combo.current(0)
        else:
            auto_mode = False
            if auto_timer:
                auto_timer.cancel()
                auto_timer = None

    auto_mode_combo.bind('<<ComboboxSelected>>', on_mode_change)

    # Frame tombol
    btn_frame = tk.Frame(root, bg='#2E2E2E')
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="Refresh Grafik", command=update_chart, bg='#4CAF50', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="Pengaturan Shortcut", command=open_settings, bg='#2196F3', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)

    update_chart()  # Init grafik
    root.mainloop()

# Hotkey listener di thread terpisah
def hotkey_listener():
    keyboard.add_hotkey(current_hotkey, show_input_popup)
    keyboard.wait()

if __name__ == '__main__':
    threading.Thread(target=hotkey_listener, daemon=True).start()
    main_window()