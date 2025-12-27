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
import sys
import json  # Untuk simpan/load pengaturan
from odf import text, teletype
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableRow, TableCell

# File untuk menyimpan data dan pengaturan
DATA_FILE = 'money_tracker.csv'
CONFIG_FILE = 'config.json'  # File baru untuk simpan pengaturan

# Hotkey default
current_hotkey = 'ctrl+shift+a'

# Versi dari Git
def get_git_version():
    try:
        return subprocess.check_output(['git', 'describe', '--tags', '--dirty', '--always']).decode('utf-8').strip()
    except:
        return "dev"
APP_VERSION = get_git_version().replace('v', '')

# Variabel global
current_view_mode = 'both'
auto_mode = False
auto_interval = 60
auto_warning_seconds = 5
auto_timer = None
warning_timer = None
hover_connection_id = None
root_window = None

# Load pengaturan dari file jika ada
def load_config():
    global current_hotkey, auto_interval, auto_warning_seconds
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            current_hotkey = config.get('hotkey', current_hotkey)
            auto_interval = config.get('auto_interval', auto_interval)
            auto_warning_seconds = config.get('auto_warning_seconds', auto_warning_seconds)

# Simpan pengaturan ke file
def save_config():
    config = {
        'hotkey': current_hotkey,
        'auto_interval': auto_interval,
        'auto_warning_seconds': auto_warning_seconds
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

# Parse amount
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

# Simpan & load data
def save_data(amount):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(columns=['Timestamp', 'Amount'])
    new_row = pd.DataFrame({'Timestamp': [timestamp], 'Amount': [amount]})
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

def load_data():
    if os.path.exists(DATA_FILE):
        return pd.read_csv(DATA_FILE)
    return pd.DataFrame(columns=['Timestamp', 'Amount'])

# Popup input
def show_input_popup():
    popup = tk.Toplevel()
    popup.title("Input Jumlah Uang")
    popup.geometry("300x150+{}+{}".format(popup.winfo_screenwidth()//2 - 150, popup.winfo_screenheight()//2 - 75))
    popup.configure(bg='#2E2E2E')
    popup.attributes('-topmost', True)
    popup.attributes('-toolwindow', True)
    popup.focus_force()
    popup.grab_set()
    popup.lift()

    tk.Label(popup, text="Masukkan angka (e.g., 2k, 2qa):", bg='#2E2E2E', fg='white', font=('Arial', 12, 'bold')).pack(pady=20)
    entry = tk.Entry(popup, font=('Arial', 14), justify='center', width=20)
    entry.pack(pady=10)
    entry.focus_set()

    def submit():
        amount = parse_amount(entry.get())
        if amount and amount > 0:
            save_data(amount)
            messagebox.showinfo("Sukses", f"Ditambahkan: {amount:,}".replace(',', '.'), parent=popup)
            popup.destroy()
            update_chart()
        elif amount == 0:
            messagebox.showwarning("Peringatan", "Angka tidak boleh 0!", parent=popup)
        else:
            messagebox.showerror("Error", "Input tidak valid!", parent=popup)

    entry.bind('<Return>', lambda e: submit())
    popup.bind('<Escape>', lambda e: popup.destroy())

# Popup countdown peringatan
def show_countdown_warning(remaining):
    if remaining <= 0:
        show_input_popup()
        return

    warning = tk.Toplevel()
    warning.title("Peringatan")
    warning.geometry("250x100+{}+{}".format(warning.winfo_screenwidth()//2 - 125, warning.winfo_screenheight()//2 - 50))
    warning.configure(bg='#1e1e1e')
    warning.attributes('-topmost', True)
    warning.attributes('-toolwindow', True)
    warning.overrideredirect(True)

    label = tk.Label(warning, text=f"Popup input akan muncul dalam\n{remaining} detik", 
                     bg='#1e1e1e', fg='yellow', font=('Arial', 16, 'bold'))
    label.pack(expand=True)

    global warning_timer
    warning_timer = threading.Timer(1.0, lambda: [warning.destroy(), show_countdown_warning(remaining - 1)])
    warning_timer.start()

# Auto popup dengan peringatan
def auto_popup():
    global auto_timer, warning_timer
    if not auto_mode:
        return

    if auto_warning_seconds > 0:
        show_countdown_warning(auto_warning_seconds)
    else:
        show_input_popup()

    auto_timer = threading.Timer(auto_interval, auto_popup)
    auto_timer.start()

# Update grafik dengan hover fix dan margin
def update_chart():
    global canvas, fig, ax, hover_connection_id

    df = load_data()
    if df.empty:
        ax.clear()
        ax.text(0.5, 0.5, 'Belum ada data', ha='center', va='center', transform=ax.transAxes, fontsize=16, color='white')
        canvas.draw()
        return

    df['Timestamp'] = pd.to_datetime(df['Timestamp'])
    df.sort_values('Timestamp', inplace=True)
    df['Raw'] = df['Amount']
    df['Delta'] = df['Amount'].diff().fillna(0)

    ax.clear()
    for child_ax in fig.axes[1:]:
        fig.delaxes(child_ax)

    if hover_connection_id is not None:
        fig.canvas.mpl_disconnect(hover_connection_id)
        hover_connection_id = None

    show_raw = current_view_mode in ['raw', 'both']
    show_delta = current_view_mode in ['delta', 'both']

    line_raw = None
    line_delta = None

    if show_raw:
        line_raw, = ax.plot(df['Timestamp'], df['Raw'], marker='o', markersize=8, color='#2196F3',
                            linewidth=3, label='Nilai Input (Raw)', picker=5)

    if show_delta:
        if not show_raw:  # Hanya plot di axis utama jika tidak ada raw (mode delta only)
            line_delta, = ax.plot(df['Timestamp'], df['Delta'], marker='s', markersize=7, color='#F44336',
                                  linewidth=2, linestyle='--', label='Selisih (Delta)', picker=5)
        # Jika mode both, delta hanya diplot di ax2 (nanti di bawah)

    if show_raw and show_delta:
        ax2 = ax.twinx()
        line_delta2, = ax2.plot(df['Timestamp'], df['Delta'], marker='s', markersize=7, color='#F44336',
                                linewidth=2, linestyle='--', label='Selisih (Delta)', picker=5)
        ax2.set_ylabel('Selisih dari Sebelumnya', color='#F44336', fontsize=12)
        ax2.tick_params(axis='y', labelcolor='#F44336')

        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left',
                  facecolor='#333333', edgecolor='white', labelcolor='white')
    else:
        ax.legend(loc='upper left', facecolor='#333333', edgecolor='white', labelcolor='white')

    ax.set_title(f'Grafik Uang - Mode: {current_view_mode.capitalize()}', fontsize=14, color='white')
    ax.set_xlabel('Waktu', color='white')
    ax.set_ylabel('Nilai Input', color='#2196F3', fontsize=12)
    ax.tick_params(colors='white')
    ax.set_facecolor('#333333')
    fig.patch.set_facecolor('#2E2E2E')
    ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
    plt.xticks(rotation=45)
    
    # Berikan margin yang cukup agar label, legend, dan tooltip tidak terpotong
    plt.subplots_adjust(left=0.11, right=0.88, top=0.92, bottom=0.18)
    
    # JANGAN pakai tight_layout() karena akan override subplots_adjust
    # plt.tight_layout()  # <-- Pastikan ini di-comment atau dihapus

    annot = ax.annotate("", xy=(0,0), xytext=(15,15), textcoords="offset points",
                        bbox=dict(boxstyle="round,pad=0.5", fc="#1e1e1e", ec="white", alpha=0.9),
                        arrowprops=dict(arrowstyle="->", color='white', lw=1.5),
                        color='white', fontsize=11, ha='left', va='bottom')
    annot.set_visible(False)

    def on_hover(event):
        if event.inaxes not in [ax, ax2] if 'ax2' in locals() else event.inaxes != ax:
            annot.set_visible(False)
            canvas.draw_idle()
            return

        visible = False
        lines_to_check = []
        if line_raw:
            lines_to_check.append(line_raw)
        if line_delta:
            lines_to_check.append(line_delta)
        if show_raw and show_delta and 'line_delta2' in locals():
            lines_to_check.append(line_delta2)

        for line in lines_to_check:
            if line.contains(event)[0]:
                ind = line.contains(event)[1]["ind"][0]
                x = df['Timestamp'].iloc[ind]
                y_raw = df['Raw'].iloc[ind]
                y_delta = df['Delta'].iloc[ind]
                # Sesuaikan y berdasarkan axis line
                y_pos = y_raw if line == line_raw else y_delta
                annot.xy = (x, y_pos)
                text = f"Waktu: {x.strftime('%d %b %Y %H:%M:%S')}\nInput: {y_raw:,.0f}\nSelisih: {y_delta:,.0f}"
                annot.set_text(text)
                visible = True
                break

        annot.set_visible(visible)
        canvas.draw_idle()

    hover_connection_id = fig.canvas.mpl_connect("motion_notify_event", on_hover)
    canvas.draw()

# Export data ke file ODS (LibreOffice/OpenOffice spreadsheet)
def export_to_ods():
    df = load_data()
    if df.empty:
        messagebox.showwarning("Peringatan", "Tidak ada data untuk diekspor!")
        return

    # Dialog simpan file
    from tkinter import filedialog
    file_path = filedialog.asksaveasfilename(
        defaultextension=".ods",
        filetypes=[("ODS Spreadsheet", "*.ods"), ("All Files", "*.*")],
        title="Simpan sebagai ODS"
    )
    if not file_path:
        return  # User cancel

    # Buat dokumen ODS
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Money Tracker Data")
    doc.spreadsheet.addElement(table)

    # Header
    tr = TableRow()
    table.addElement(tr)
    for col_name in ['Timestamp', 'Amount']:
        cell = TableCell()
        tr.addElement(cell)
        p = text.P()
        p.addText(col_name)
        cell.addElement(p)

    # Isi data
    for _, row in df.iterrows():
        tr = TableRow()
        table.addElement(tr)

        # Timestamp
        cell = TableCell()
        tr.addElement(cell)
        p = text.P()
        p.addText(str(row['Timestamp']))
        cell.addElement(p)

        # Amount (format angka dengan koma)
        cell = TableCell(valuetype="float", value=row['Amount'])
        tr.addElement(cell)
        p = text.P()
        p.addText(f"{row['Amount']:,.0f}".replace(",", "."))
        cell.addElement(p)

    # Simpan file
    try:
        doc.save(file_path)
        messagebox.showinfo("Sukses", f"Data berhasil diekspor ke:\n{file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Gagal menyimpan file ODS:\n{e}")

# Pengaturan shortcut dengan simpan config
def open_settings():
    global current_hotkey
    settings_win = tk.Toplevel()
    settings_win.title("Pengaturan Shortcut")
    settings_win.geometry("450x250")
    settings_win.configure(bg='#2E2E2E')
    settings_win.attributes('-topmost', True)

    tk.Label(settings_win, text="Tekan kombinasi tombol langsung di bawah ini\natau ketik manual:", 
             bg='#2E2E2E', fg='white', font=('Arial', 12)).pack(pady=20)

    entry = tk.Entry(settings_win, font=('Arial', 14), width=35, justify='center')
    entry.insert(0, current_hotkey)
    entry.pack(pady=10)
    entry.focus_set()

    def on_key(event):
        try:
            hotkey_name = keyboard.get_hotkey_name()
            if hotkey_name and hotkey_name != current_hotkey:
                entry.delete(0, tk.END)
                entry.insert(0, hotkey_name)
        except:
            pass

    settings_win.bind('<KeyPress>', on_key)

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
                save_config()  # Simpan config setelah ubah
                messagebox.showinfo("Sukses", f"Shortcut diubah menjadi: {new_key.upper()}")
                settings_win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Shortcut tidak valid!\n{e}")
        else:
            messagebox.showwarning("Peringatan", "Shortcut tidak boleh kosong!")

    tk.Button(settings_win, text="Terapkan", command=apply_hotkey, bg='#4CAF50', fg='white', font=('Arial', 12)).pack(pady=20)

# Fungsi quit aplikasi
def on_closing():
    global auto_timer, warning_timer, hover_connection_id
    if messagebox.askokcancel("Keluar", "Apakah Anda yakin ingin menutup aplikasi?"):
        if auto_timer:
            auto_timer.cancel()
        if warning_timer:
            warning_timer.cancel()
        
        try:
            keyboard.remove_hotkey(current_hotkey)
        except:
            pass
        
        if hover_connection_id:
            fig.canvas.mpl_disconnect(hover_connection_id)
        
        root_window.destroy()
        sys.exit(0)

# Main window
def main_window():
    global canvas, fig, ax, chart_type_combo, view_mode_combo, auto_mode_combo, interval_entry
    global warning_entry, root_window

    load_config()  # Load config di awal

    root_window = tk.Tk()
    root_window.title(f"Money Tracker v{APP_VERSION}")
    root_window.geometry("950x750")
    root_window.configure(bg='#2E2E2E')
    root_window.protocol("WM_DELETE_WINDOW", on_closing)

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor('#2E2E2E')
    ax.set_facecolor('#333333')

    canvas = FigureCanvasTkAgg(fig, master=root_window)
    canvas.get_tk_widget().pack(pady=10, fill=tk.BOTH, expand=True)

    toolbar = NavigationToolbar2Tk(canvas, root_window)
    toolbar.update()
    toolbar.pack(pady=5)

    # Kontrol grafik
    control_frame = tk.Frame(root_window, bg='#2E2E2E')
    control_frame.pack(pady=30)

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

    def on_chart_change(event=None):
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

    # Auto/Manual popup
    auto_frame = tk.Frame(root_window, bg='#2E2E2E')
    auto_frame.pack(pady=10)

    tk.Label(auto_frame, text="Mode Popup:", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
    auto_options = ['Manual', 'Auto']
    auto_mode_combo = ttk.Combobox(auto_frame, values=auto_options, font=('Arial', 10), width=10, state='readonly')
    auto_mode_combo.current(0)
    auto_mode_combo.pack(side=tk.LEFT, padx=5)

    tk.Label(auto_frame, text="Interval (detik):", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
    interval_entry = tk.Entry(auto_frame, font=('Arial', 10), width=8)
    interval_entry.insert(0, str(auto_interval))
    interval_entry.pack(side=tk.LEFT, padx=5)

    tk.Label(auto_frame, text="Peringatan sebelum (detik):", bg='#2E2E2E', fg='white', font=('Arial', 10)).pack(side=tk.LEFT, padx=10)
    warning_entry = tk.Entry(auto_frame, font=('Arial', 10), width=5)
    warning_entry.insert(0, str(auto_warning_seconds))
    warning_entry.pack(side=tk.LEFT, padx=5)

    def on_mode_change(event):
        global auto_mode, auto_interval, auto_warning_seconds, auto_timer
        if auto_mode_combo.get() == 'Auto':
            try:
                auto_interval = int(interval_entry.get())
                auto_warning_seconds = int(warning_entry.get())
                if auto_interval <= 0 or auto_warning_seconds < 0:
                    raise ValueError
                auto_mode = True
                if auto_timer:
                    auto_timer.cancel()
                auto_popup()
                save_config()  # Simpan setelah ubah
            except:
                messagebox.showerror("Error", "Interval harus >0, peringatan ≥0!")
                auto_mode_combo.current(0)
        else:
            auto_mode = False
            if auto_timer:
                auto_timer.cancel()
                auto_timer = None

    auto_mode_combo.bind('<<ComboboxSelected>>', on_mode_change)

    # Tombol
    btn_frame = tk.Frame(root_window, bg='#2E2E2E')
    btn_frame.pack(pady=15)

    tk.Button(btn_frame, text="Refresh Grafik", command=update_chart, bg='#4CAF50', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="Pengaturan Shortcut", command=open_settings, bg='#2196F3', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="Export ke ODS", command=export_to_ods, bg='#FF9800', fg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=10)
    
    update_chart()
    root_window.mainloop()

# Hotkey listener
def hotkey_listener():
    keyboard.add_hotkey(current_hotkey, show_input_popup)
    keyboard.wait()

if __name__ == '__main__':
    threading.Thread(target=hotkey_listener, daemon=True).start()
    main_window()