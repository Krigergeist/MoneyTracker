import tkinter as tk
from tkinter import messagebox, ttk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import keyboard
import pandas as pd
from datetime import datetime
import os
import threading

# File untuk menyimpan data
DATA_FILE = 'money_tracker.csv'

# Fungsi untuk parse angka dengan singkatan
def parse_amount(input_str):
    suffixes = {
        'k': 1e3,    # thousand
        'm': 1e6,    # million
        'b': 1e9,    # billion
        't': 1e12,   # trillion
        'qa': 1e15,  # quadrillion
    }
    input_str = input_str.lower().strip()
    for suffix, multiplier in suffixes.items():
        if input_str.endswith(suffix):
            try:
                num = float(input_str[:-len(suffix)])
                return num * multiplier
            except ValueError:
                return None
    try:
        return float(input_str)
    except ValueError:
        return None

# Fungsi untuk simpan data ke CSV
def save_data(amount):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=['Timestamp', 'Amount'])
    new_row = pd.DataFrame({'Timestamp': [timestamp], 'Amount': [amount]})
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

# Fungsi untuk load data
def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=['Timestamp', 'Amount'])

# Fungsi popup input
def show_input_popup():
    popup = tk.Toplevel()
    popup.title("Input Jumlah Uang")
    popup.geometry("300x150+{}+{}".format(
        popup.winfo_screenwidth()//2 - 150,  # Tengah horizontal
        popup.winfo_screenheight()//2 - 75   # Tengah vertikal
    ))
    popup.configure(bg='#2E2E2E')
    
    # === PENGATURAN PENTING UNTUK SELALU DI ATAS ===
    popup.attributes('-topmost', True)        # Selalu di atas semua window
    popup.attributes('-alpha', 1.0)           # Opacity penuh (bisa diubah jadi 0.95 jika mau sedikit transparan)
    
    # Untuk Windows: agar muncul di atas taskbar dan program fullscreen
    popup.attributes('-toolwindow', True)     # Hilangkan dari taskbar (opsional)
    popup.attributes('-disabled', False)      # Pastikan tidak disabled
    
    # Fokus paksa ke popup
    popup.focus_force()                       # Paksa ambil fokus keyboard
    popup.grab_set()                          # Blokir interaksi ke window lain sampai popup ditutup
    
    # Agar popup muncul di tengah layar dan langsung aktif
    popup.lift()                              # Angkat ke atas
    popup.update()                            # Refresh agar langsung terlihat

    label = tk.Label(popup, text="Masukkan angka (e.g., 2k, 2qa):", 
                     bg='#2E2E2E', fg='white', font=('Arial', 12, 'bold'))
    label.pack(pady=20)

    entry = tk.Entry(popup, font=('Arial', 14), justify='center', width=20)
    entry.pack(pady=10)
    entry.focus_set()  # Langsung bisa ketik tanpa klik dulu

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

    def on_enter(event):
        submit()

    entry.bind('<Return>', on_enter)
    
    # Optional: Tekan ESC untuk batal
    popup.bind('<Escape>', lambda e: popup.destroy())
    
    # Pastikan popup tetap di atas sampai ditutup
    popup.protocol("WM_DELETE_WINDOW", popup.destroy)

# Fungsi untuk update grafik
def update_chart():
    global canvas, fig, ax, current_chart_type
    df = load_data()
    if df.empty:
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.sort_values('Timestamp', inplace=True)
    df['Cumulative'] = df['Amount'].cumsum()  # Hitung kumulatif untuk grafik

    ax.clear()
    if current_chart_type == 'bar':
        ax.bar(df['Timestamp'], df['Cumulative'], color='#4CAF50')
    elif current_chart_type == 'line':
        ax.plot(df['Timestamp'], df['Cumulative'], marker='o', color='#2196F3')
    elif current_chart_type == 'area':
        ax.fill_between(df['Timestamp'], df['Cumulative'], color='#FF9800', alpha=0.5)
    elif current_chart_type == 'scatter':
        ax.scatter(df['Timestamp'], df['Cumulative'], color='#E91E63')
    else:
        ax.plot(df['Timestamp'], df['Cumulative'], color='#9C27B0')  # Default line

    ax.set_title('Grafik Jumlah Uang Kumulatif per Waktu', fontsize=14, color='white')
    ax.set_xlabel('Waktu', color='white')
    ax.set_ylabel('Jumlah Uang', color='white')
    ax.tick_params(colors='white')
    ax.set_facecolor('#333333')
    fig.patch.set_facecolor('#2E2E2E')
    plt.xticks(rotation=45)
    canvas.draw()

# Fungsi untuk ganti jenis chart
def change_chart_type(event):
    global current_chart_type
    current_chart_type = chart_type_combo.get().lower()
    update_chart()

# Fungsi utama GUI
def main_window():
    global canvas, fig, ax, current_chart_type, chart_type_combo
    current_chart_type = 'line'

    root = tk.Tk()
    root.title("Money Tracker")
    root.geometry("800x600")
    root.configure(bg='#2E2E2E')  # Tampilan modern gelap

    # Frame untuk grafik
    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#333333')

    canvas = FigureCanvasTkAgg(fig, master=root)
    canvas.get_tk_widget().pack(pady=20)

    # Combo box untuk pilih jenis grafik
    chart_types = ['Bar', 'Line', 'Area', 'Scatter']
    chart_type_combo = ttk.Combobox(root, values=chart_types, font=('Arial', 12), state='readonly')
    chart_type_combo.current(1)  # Default Line
    chart_type_combo.pack(pady=10)
    chart_type_combo.bind('<<ComboboxSelected>>', change_chart_type)

    # Tombol refresh manual
    refresh_button = tk.Button(root, text="Refresh Grafik", command=update_chart, bg='#4CAF50', fg='white', font=('Arial', 12))
    refresh_button.pack(pady=10)

    update_chart()  # Init grafik
    root.mainloop()

# Fungsi untuk deteksi hotkey di background
def hotkey_listener():
    keyboard.add_hotkey('ctrl+shift+a', show_input_popup)  # Ganti hotkey jika perlu
    keyboard.wait()

# Jalankan listener di thread terpisah agar tidak blok GUI
if __name__ == '__main__':
    threading.Thread(target=hotkey_listener, daemon=True).start()
    main_window()