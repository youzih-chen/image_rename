"""
This is a simple image renaming tool that allows users to rename a batch of images based on user-defined fields.
Powered by Python 3.11.0
Created by YouZih Chen, with AI assistance from Grok 3
Date: March 2025
Version: 1.0
"""

# -*- coding: utf-8 -*-
import os
import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
from collections import defaultdict
import sys
import io
import threading
import queue

# 強制設置 UTF-8 編碼
if sys.stdout is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
else:
    sys.stdout = io.TextIOWrapper(open(os.devnull, 'wb'), encoding='utf-8')
if sys.stderr is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')
else:
    sys.stderr = io.TextIOWrapper(open(os.devnull, 'wb'), encoding='utf-8')

# 全域變數
folder_path = ""
field_titles = []
separator = ""
images = []
current_index = 0
field_entries = []
rename_map = {}
main_image_size = 400
all_preview_labels = []
thumbnail_cache = {}
image_offset_x = 0
image_offset_y = 0
last_x = 0
last_y = 0
preview_start = 0

# 創建主窗口
root = tk.Tk()
root.title("Image Filename Renamer 1.0")
root.geometry("1200x800")

def generate_thumbnails(progress_queue):
    global thumbnail_cache
    thumbnail_cache.clear()
    for i, img_name in enumerate(images):
        img_path = os.path.join(folder_path, img_name)
        img = Image.open(img_path)
        img.thumbnail((80, 80))
        thumbnail_cache[img_name] = ImageTk.PhotoImage(img)
        progress_queue.put(i + 1)

def update_progress(progress_bar, progress_queue, total_images, progress_window):
    try:
        while not progress_queue.empty():
            progress = progress_queue.get_nowait()
            progress_bar["value"] = progress
        if progress_bar["value"] >= total_images:
            progress_window.destroy()
            show_image(current_index)
            load_all_previews()
        else:
            root.after(100, update_progress, progress_bar, progress_queue, total_images, progress_window)
    except queue.Empty:
        root.after(100, update_progress, progress_bar, progress_queue, total_images, progress_window)

def load_folder():
    global folder_path, images, rename_map, field_titles, separator, current_index, preview_start
    folder_path = filedialog.askdirectory()
    if folder_path:
        images = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        if not images:
            messagebox.showerror("Error", "No image files found in the folder")
            image_count_label.config(text="Image 0 of 0")
        else:
            current_index = 0
            preview_start = 0
            
            progress_window = tk.Toplevel(root)
            progress_window.title("Loading Images")
            progress_window.geometry("300x100")
            progress_window.transient(root)
            progress_window.grab_set()
            ttk.Label(progress_window, text="Loading thumbnails...").pack(pady=10)
            progress_bar = ttk.Progressbar(progress_window, orient="horizontal", length=250, mode="determinate")
            progress_bar.pack(pady=10)
            progress_bar["maximum"] = len(images)
            
            progress_queue = queue.Queue()
            thread = threading.Thread(target=generate_thumbnails, args=(progress_queue,))
            thread.daemon = True
            thread.start()
            
            root.after(100, update_progress, progress_bar, progress_queue, len(images), progress_window)
            
            config_path = os.path.join(folder_path, "rename_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    rename_map = config.get("rename_map", {})
                    field_titles[:] = config.get("field_titles", [])
                    separator = config.get("separator", "")
                    if field_titles:
                        create_field_entries()
                        separator_entry.insert(0, separator)
                        fields_entry.insert(0, ",".join(field_titles))

def set_fields():
    global field_titles, separator
    titles_input = fields_entry.get()
    separator = separator_entry.get()
    field_titles = [title.strip() for title in titles_input.split(',') if title.strip()]
    if not field_titles:
        messagebox.showerror("Error", "Please enter at least one field title")
        return
    create_field_entries()
    save_config()

def create_field_entries():
    global field_entries
    for widget in fields_frame.winfo_children():
        widget.destroy()
    field_entries = []
    for title in field_titles:
        label = ttk.Label(fields_frame, text=f"{title}:")
        label.grid(row=len(field_entries), column=0, padx=10, pady=5)
        entry = ttk.Entry(fields_frame, width=30)
        entry.grid(row=len(field_entries), column=1, padx=10, pady=5)
        field_entries.append(entry)
    if field_entries:
        field_entries[0].focus_set()
    load_fields()

def show_image(index):
    global current_index, main_image_size, image_offset_x, image_offset_y
    current_index = index
    if 0 <= current_index < len(images):
        img_path = os.path.join(folder_path, images[current_index])
        img = Image.open(img_path)
        img.thumbnail((main_image_size, main_image_size))
        img_tk = ImageTk.PhotoImage(img)
        main_image_canvas.delete("all")
        main_image_canvas.create_image(image_offset_x + main_image_size // 2, 
                                       image_offset_y + main_image_size // 2, 
                                       image=img_tk)
        main_image_canvas.image = img_tk
        
        editing_label.config(text=f"Editing: {images[current_index]}")
        image_count_label.config(text=f"Image {current_index + 1} of {len(images)}")
        
        update_preview_highlight()
        load_fields()

def update_preview_highlight():
    for i, preview_label in enumerate(all_preview_labels):
        if i + preview_start == current_index:
            preview_label.config(borderwidth=2, relief="solid", highlightbackground="red", highlightcolor="red")
        else:
            preview_label.config(borderwidth=0, relief="flat")

def load_fields():
    if field_entries and images[current_index] in rename_map:
        values = rename_map[images[current_index]]
        for entry, value in zip(field_entries, values):
            entry.delete(0, tk.END)
            entry.insert(0, value)

def prev_image():
    global current_index
    if current_index > 0:
        save_fields()
        current_index -= 1
        show_image(current_index)
        sync_preview_page()
        root.after(200, set_focus_to_first_entry)

def next_image():
    global current_index
    if current_index < len(images) - 1:
        save_fields()
        current_index += 1
        show_image(current_index)
        sync_preview_page()
        root.after(200, set_focus_to_first_entry)

def set_focus_to_first_entry():
    if field_entries:
        field_entries[0].focus_force()
        field_entries[0].select_range(0, tk.END)

def sync_preview_page():
    global preview_start
    preview_limit = calculate_preview_limit()
    new_page_start = (current_index // preview_limit) * preview_limit
    if new_page_start != preview_start:
        preview_start = new_page_start
        load_all_previews()

def save_fields():
    values = [entry.get() for entry in field_entries]
    if all(values):
        rename_map[images[current_index]] = values
        save_config()

def save_config():
    if folder_path:
        config = {"rename_map": rename_map, "field_titles": field_titles, "separator": separator}
        config_path = os.path.join(folder_path, "rename_config.json")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False)

def generate_bat():
    save_fields()
    
    if not rename_map:
        messagebox.showerror("Error", "Please set field values first")
        return
    bat_content = [f'cd /d "{folder_path}"']
    new_names = defaultdict(int)
    for img, values in rename_map.items():
        _, ext = os.path.splitext(img)
        base_name = separator.join(values)
        # 檢查重複並生成最終檔名
        count = new_names[base_name]
        if count == 0:
            new_name = base_name + ext
        else:
            new_name = f"{base_name}({count}){ext}"
        new_names[base_name] += 1  # 更新計數
        bat_content.append(f'ren "{img}" "{new_name}"')
    bat_content.append("pause")
    bat_path = os.path.join(folder_path, "rename.bat")
    with open(bat_path, 'w', encoding='ansi') as f:
        f.write('\n'.join(bat_content))
    messagebox.showinfo("Success", f"Rename commands saved to {bat_path}")

def zoom_image(event):
    global main_image_size, image_offset_x, image_offset_y
    if event.delta > 0:
        main_image_size = min(800, main_image_size + 50)
    else:
        main_image_size = max(100, main_image_size - 50)
    image_offset_x = 0
    image_offset_y = 0
    show_image(current_index)

def start_drag(event):
    global last_x, last_y
    last_x = event.x
    last_y = event.y

def move_image(event):
    global image_offset_x, image_offset_y, last_x, last_y
    dx = event.x - last_x
    dy = event.y - last_y
    image_offset_x += dx
    image_offset_y += dy
    last_x = event.x
    last_y = event.y
    show_image(current_index)

def prev_page():
    global preview_start
    preview_limit = calculate_preview_limit()
    if preview_start > 0:
        preview_start -= preview_limit
        load_all_previews()

def next_page():
    global preview_start
    preview_limit = calculate_preview_limit()
    if preview_start + preview_limit < len(images):
        preview_start += preview_limit
        load_all_previews()

def calculate_preview_limit():
    preview_canvas.update_idletasks()
    canvas_width = preview_canvas.winfo_width() or 300
    canvas_height = preview_canvas.winfo_height() or 300
    img_size = 80
    padding = 10
    text_height = 50
    cols = max(1, (canvas_width - padding) // (img_size + padding))
    rows = max(1, (canvas_height - padding - text_height) // (img_size + padding))
    return cols * rows

def load_all_previews(event=None):
    global all_preview_labels, preview_canvas, preview_start
    for widget in preview_canvas_frame.winfo_children():
        widget.destroy()
    
    preview_canvas = tk.Canvas(preview_canvas_frame)
    scrollable_frame = ttk.Frame(preview_canvas)
    preview_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    preview_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    
    preview_limit = calculate_preview_limit()
    all_preview_labels = []
    end_index = min(preview_start + preview_limit, len(images))
    cols = max(1, (preview_canvas.winfo_width() - 10) // 90)
    for i in range(preview_start, end_index):
        img_name = images[i]
        img_tk = thumbnail_cache[img_name]
        label = tk.Label(scrollable_frame, image=img_tk, text=img_name, compound='bottom', wraplength=80)
        label.image = img_tk
        row = (i - preview_start) // cols
        col = (i - preview_start) % cols
        label.grid(row=row, column=col, padx=5, pady=5)
        label.bind("<Button-1>", lambda e, idx=i: show_image(idx))
        all_preview_labels.append(label)
    
    update_preview_highlight()
    scrollable_frame.update_idletasks()
    canvas_height = scrollable_frame.winfo_height()
    preview_canvas.configure(scrollregion=(0, 0, preview_canvas.winfo_width(), canvas_height))

# GUI 佈局
pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
pane.pack(fill=tk.BOTH, expand=True)

left_frame = ttk.Frame(pane, relief="groove", borderwidth=2)
pane.add(left_frame, weight=1)

load_button = ttk.Button(left_frame, text="Load Folder", command=load_folder)
load_button.pack(pady=10)

fields_setup_frame = ttk.Frame(left_frame)
fields_setup_frame.pack(pady=10)
ttk.Label(fields_setup_frame, text="Field Titles (comma-separated):").grid(row=0, column=0, padx=10)
fields_entry = ttk.Entry(fields_setup_frame, width=30)
fields_entry.grid(row=0, column=1, padx=10)
ttk.Label(fields_setup_frame, text="Separator:").grid(row=1, column=0, padx=10)
separator_entry = ttk.Entry(fields_setup_frame, width=30)
separator_entry.grid(row=1, column=1, padx=10)
set_fields_button = ttk.Button(fields_setup_frame, text="Set", command=set_fields)
set_fields_button.grid(row=2, columnspan=2, pady=5)

fields_frame = ttk.Frame(left_frame)
fields_frame.pack(pady=10)

nav_frame = ttk.Frame(left_frame)
nav_frame.pack(pady=10)
next_button = ttk.Button(nav_frame, text="Next", command=next_image)
next_button.grid(row=0, column=0, padx=10)
prev_button = ttk.Button(nav_frame, text="Previous", command=prev_image)
prev_button.grid(row=0, column=1, padx=10)
save_button = ttk.Button(nav_frame, text="Save", command=generate_bat)
save_button.grid(row=0, column=2, padx=10)
image_count_label = ttk.Label(nav_frame, text="Image 0 of 0")
image_count_label.grid(row=0, column=3, padx=10)

all_preview_frame = ttk.Frame(left_frame, relief="sunken", borderwidth=2)
all_preview_frame.pack(pady=10, fill=tk.BOTH, expand=True)

preview_canvas_frame = ttk.Frame(all_preview_frame)
preview_canvas_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
button_frame = ttk.Frame(all_preview_frame)
button_frame.pack(side=tk.BOTTOM, pady=5)
prev_page_button = ttk.Button(button_frame, text="<", command=prev_page, width=2)
prev_page_button.grid(row=0, column=0, padx=5)
next_page_button = ttk.Button(button_frame, text=">", command=next_page, width=2)
next_page_button.grid(row=0, column=1, padx=5)

all_preview_frame.bind("<Configure>", load_all_previews)

right_frame = ttk.Frame(pane, relief="groove", borderwidth=2)
pane.add(right_frame, weight=2)

editing_frame = ttk.Frame(right_frame)
editing_frame.pack(pady=5, fill=tk.X)
editing_label = ttk.Label(editing_frame, text="Editing: No image", foreground="blue")
editing_label.pack()

main_image_frame = ttk.Frame(right_frame)
main_image_frame.pack(pady=10, expand=True)
main_image_canvas = tk.Canvas(main_image_frame, width=800, height=600)
main_image_canvas.pack()
main_image_canvas.bind("<MouseWheel>", zoom_image)
main_image_canvas.bind("<Button-1>", start_drag)
main_image_canvas.bind("<B1-Motion>", move_image)

root.mainloop()