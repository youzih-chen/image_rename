# -*- coding: utf-8 -*-
"""
Image Filename Renamer 2.0
Batch image renaming tool with multi-format support (JPG, PNG, TIF, RAW, WebP, HEIC, etc.),
live filename preview, safe collision handling, direct rename with undo, and .bat export.

Powered by Python 3.10+ & Pillow
Original by YouZih Chen (March 2025), refactored & optimized.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import io
import json
import os
import queue
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Iterable

from PIL import Image, ImageDraw, ImageOps, ImageTk

# ── Optional format plugins ────────────────────────────────────────────────────
try:
    import rawpy  # type: ignore
    HAS_RAWPY = True
except ImportError:
    HAS_RAWPY = False

try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
    HAS_HEIF = True
except ImportError:
    HAS_HEIF = False

try:
    import sv_ttk  # type: ignore
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

# ── Supported image extensions ────────────────────────────────────────────────
STANDARD_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tif", ".tiff", ".ico"
}
RAW_EXTENSIONS = {
    ".dng", ".cr2", ".cr3", ".nef", ".arw", ".orf", ".rw2", ".raf", ".pef", ".srw"
}
HEIF_EXTENSIONS = {".heic", ".heif", ".avif"}
SUPPORTED_EXTENSIONS = STANDARD_EXTENSIONS | RAW_EXTENSIONS | HEIF_EXTENSIONS

RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS
INVALID_FILENAME_CHARS_RE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
THUMB_CACHE_PAGES = 3

# ══════════════════════════════════════════════════════════════════════════════
# Colour palettes
# Every palette must have these keys:
#   bg_hard, bg, bg1, bg2, bg3, fg, fg1, fg2, fg3,
#   bright_blue, bright_yellow, bright_orange,
#   thumb_named, thumb_current, canvas_bg
# ══════════════════════════════════════════════════════════════════════════════

# ── Windows 11 (used for tk widget colours when sv-ttk is active) ─────────────
WIN11_DARK: dict[str, str] = {
    "bg_hard":       "#1c1c1c",
    "bg":            "#202020",
    "bg1":           "#2d2d2d",
    "bg2":           "#3d3d3d",
    "bg3":           "#4d4d4d",
    "fg":            "#ffffff",
    "fg1":           "#e0e0e0",
    "fg2":           "#c0c0c0",
    "fg3":           "#888888",
    "bright_yellow": "#ffd700",
    "bright_orange": "#ff8c00",
    "bright_blue":   "#60cdff",
    "thumb_named":   "#4caf50",
    "thumb_current": "#60cdff",
    "canvas_bg":     "#1c1c1c",
}

WIN11_LIGHT: dict[str, str] = {
    "bg_hard":       "#e0e0e0",
    "bg":            "#f3f3f3",
    "bg1":           "#ffffff",
    "bg2":           "#e5e5e5",
    "bg3":           "#d0d0d0",
    "fg":            "#1a1a1a",
    "fg1":           "#2a2a2a",
    "fg2":           "#444444",
    "fg3":           "#666666",
    "bright_yellow": "#875200",
    "bright_orange": "#c14d00",
    "bright_blue":   "#0067c0",
    "thumb_named":   "#0f7b0f",
    "thumb_current": "#0067c0",
    "canvas_bg":     "#e0e0e0",
}

# ── Gruvbox ───────────────────────────────────────────────────────────────────
GRUVBOX_DARK: dict[str, str] = {
    "bg_hard":       "#1d2021",
    "bg":            "#282828",
    "bg1":           "#3c3836",
    "bg2":           "#504945",
    "bg3":           "#665c54",
    "fg":            "#ebdbb2",
    "fg1":           "#d5c4a1",
    "fg2":           "#bdae93",
    "fg3":           "#a89984",
    "bright_yellow": "#fabd2f",
    "bright_orange": "#fe8019",
    "bright_blue":   "#83a598",
    "thumb_named":   "#b8bb26",
    "thumb_current": "#fabd2f",
    "canvas_bg":     "#1d2021",
    # extra keys used by apply_gruvbox_theme
    "bg4":           "#7c6f64",
    "yellow":        "#d79921",
    "orange":        "#d65d0e",
    "red":           "#cc241d",
    "green":         "#98971a",
    "blue":          "#458588",
    "purple":        "#b16286",
    "aqua":          "#689d6a",
    "bright_red":    "#fb4934",
    "bright_green":  "#b8bb26",
    "bright_purple": "#d3869b",
    "bright_aqua":   "#8ec07c",
}

GRUVBOX_LIGHT: dict[str, str] = {
    "bg_hard":       "#f9f5d7",
    "bg":            "#fbf1c7",
    "bg1":           "#ebdbb2",
    "bg2":           "#d5c4a1",
    "bg3":           "#bdae93",
    "fg":            "#3c3836",
    "fg1":           "#504945",
    "fg2":           "#665c54",
    "fg3":           "#7c6f64",
    "bright_yellow": "#d79921",
    "bright_orange": "#d65d0e",
    "bright_blue":   "#458588",
    "thumb_named":   "#79740e",
    "thumb_current": "#b57614",
    "canvas_bg":     "#f0ead6",
    "bg4":           "#a89984",
    "yellow":        "#b57614",
    "orange":        "#af3a03",
    "red":           "#9d0006",
    "green":         "#79740e",
    "blue":          "#076678",
    "purple":        "#8f3f71",
    "aqua":          "#427b58",
    "bright_red":    "#cc241d",
    "bright_green":  "#98971a",
    "bright_purple": "#b16286",
    "bright_aqua":   "#689d6a",
}

# ── Dracula ───────────────────────────────────────────────────────────────────
DRACULA: dict[str, str] = {
    "bg_hard":       "#21222c",
    "bg":            "#282a36",
    "bg1":           "#343746",
    "bg2":           "#44475a",
    "bg3":           "#6272a4",
    "fg":            "#f8f8f2",
    "fg1":           "#e2e2dc",
    "fg2":           "#ccccc7",
    "fg3":           "#6272a4",
    "bright_yellow": "#f1fa8c",
    "bright_orange": "#ffb86c",
    "bright_blue":   "#8be9fd",
    "thumb_named":   "#50fa7b",
    "thumb_current": "#ffb86c",
    "canvas_bg":     "#21222c",
    "bg4":           "#6272a4",
    "yellow":        "#f1fa8c",
    "orange":        "#ffb86c",
    "red":           "#ff5555",
    "green":         "#50fa7b",
    "blue":          "#6272a4",
    "purple":        "#bd93f9",
    "aqua":          "#8be9fd",
    "bright_red":    "#ff5555",
    "bright_green":  "#50fa7b",
    "bright_purple": "#ff79c6",
    "bright_aqua":   "#8be9fd",
}

# ── Nord ──────────────────────────────────────────────────────────────────────
NORD: dict[str, str] = {
    "bg_hard":       "#242933",
    "bg":            "#2e3440",
    "bg1":           "#3b4252",
    "bg2":           "#434c5e",
    "bg3":           "#4c566a",
    "fg":            "#eceff4",
    "fg1":           "#e5e9f0",
    "fg2":           "#d8dee9",
    "fg3":           "#616e88",
    "bright_yellow": "#ebcb8b",
    "bright_orange": "#d08770",
    "bright_blue":   "#88c0d0",
    "thumb_named":   "#a3be8c",
    "thumb_current": "#88c0d0",
    "canvas_bg":     "#242933",
    "bg4":           "#616e88",
    "yellow":        "#ebcb8b",
    "orange":        "#d08770",
    "red":           "#bf616a",
    "green":         "#a3be8c",
    "blue":          "#5e81ac",
    "purple":        "#b48ead",
    "aqua":          "#88c0d0",
    "bright_red":    "#bf616a",
    "bright_green":  "#a3be8c",
    "bright_purple": "#b48ead",
    "bright_aqua":   "#8fbcbb",
}

# ── Catppuccin Mocha (dark) ───────────────────────────────────────────────────
CATPPUCCIN_MOCHA: dict[str, str] = {
    "bg_hard":       "#181825",
    "bg":            "#1e1e2e",
    "bg1":           "#313244",
    "bg2":           "#45475a",
    "bg3":           "#585b70",
    "fg":            "#cdd6f4",
    "fg1":           "#bac2de",
    "fg2":           "#a6adc8",
    "fg3":           "#7f849c",
    "bright_yellow": "#f9e2af",
    "bright_orange": "#fab387",
    "bright_blue":   "#89b4fa",
    "thumb_named":   "#a6e3a1",
    "thumb_current": "#cba6f7",
    "canvas_bg":     "#181825",
    "bg4":           "#7f849c",
    "yellow":        "#f9e2af",
    "orange":        "#fab387",
    "red":           "#f38ba8",
    "green":         "#a6e3a1",
    "blue":          "#89b4fa",
    "purple":        "#cba6f7",
    "aqua":          "#89dceb",
    "bright_red":    "#f38ba8",
    "bright_green":  "#a6e3a1",
    "bright_purple": "#cba6f7",
    "bright_aqua":   "#89dceb",
}

# ── Catppuccin Latte (light) ──────────────────────────────────────────────────
CATPPUCCIN_LATTE: dict[str, str] = {
    "bg_hard":       "#dce0e8",
    "bg":            "#eff1f5",
    "bg1":           "#e6e9ef",
    "bg2":           "#ccd0da",
    "bg3":           "#bcc0cc",
    "fg":            "#4c4f69",
    "fg1":           "#5c5f77",
    "fg2":           "#6c6f85",
    "fg3":           "#9ca0b0",
    "bright_yellow": "#df8e1d",
    "bright_orange": "#fe640b",
    "bright_blue":   "#1e66f5",
    "thumb_named":   "#40a02b",
    "thumb_current": "#1e66f5",
    "canvas_bg":     "#dce0e8",
    "bg4":           "#9ca0b0",
    "yellow":        "#df8e1d",
    "orange":        "#fe640b",
    "red":           "#d20f39",
    "green":         "#40a02b",
    "blue":          "#1e66f5",
    "purple":        "#8839ef",
    "aqua":          "#179299",
    "bright_red":    "#d20f39",
    "bright_green":  "#40a02b",
    "bright_purple": "#8839ef",
    "bright_aqua":   "#179299",
}

# ── Theme registry ────────────────────────────────────────────────────────────
# Themes that use sv-ttk (Windows 11 native style)
SVTTK_THEMES: dict[str, str] = {
    "Win11 Light": "light",
    "Win11 Dark":  "dark",
}

# Themes that use our custom ttk.Style (Gruvbox / palette-based)
CUSTOM_THEMES: dict[str, dict[str, str]] = {
    "Gruvbox Dark":      GRUVBOX_DARK,
    "Gruvbox Light":     GRUVBOX_LIGHT,
    "Dracula":           DRACULA,
    "Nord":              NORD,
    "Catppuccin Mocha":  CATPPUCCIN_MOCHA,
    "Catppuccin Latte":  CATPPUCCIN_LATTE,
}

# Win11 colour dicts used for tk widgets when sv-ttk is active
SVTTK_PALETTES: dict[str, dict[str, str]] = {
    "Win11 Dark":  WIN11_DARK,
    "Win11 Light": WIN11_LIGHT,
}

# Which themes should use a dark title bar
DARK_THEMES: set[str] = {
    "Win11 Dark", "Gruvbox Dark", "Dracula", "Nord", "Catppuccin Mocha"
}

# Ctrl+T toggle pairs
THEME_TOGGLE_PAIRS: dict[str, str] = {
    "Win11 Dark":        "Win11 Light",
    "Win11 Light":       "Win11 Dark",
    "Gruvbox Dark":      "Gruvbox Light",
    "Gruvbox Light":     "Gruvbox Dark",
    "Catppuccin Mocha":  "Catppuccin Latte",
    "Catppuccin Latte":  "Catppuccin Mocha",
    "Dracula":           "Dracula",
    "Nord":              "Nord",
}

DEFAULT_THEME = "Win11 Light" if HAS_SV_TTK else "Gruvbox Light"


# ══════════════════════════════════════════════════════════════════════════════
# Custom (clam-based) theme application
# ══════════════════════════════════════════════════════════════════════════════

def apply_custom_theme(root: tk.Tk, style: ttk.Style, p: dict[str, str]) -> None:
    """Apply a Gruvbox/palette colour scheme to ttk widgets via clam base theme."""
    root.configure(bg=p["bg"])
    style.theme_use("clam")

    style.configure(".",
        background=p["bg"], foreground=p["fg"],
        bordercolor=p["bg3"], darkcolor=p["bg1"], lightcolor=p["bg2"],
        troughcolor=p["bg1"], focuscolor=p["bright_yellow"],
        selectbackground=p["bg2"], selectforeground=p["fg"],
        insertcolor=p["fg"], fieldbackground=p["bg1"],
        font=("Segoe UI", 10), relief="flat",
    )
    style.configure("TFrame",        background=p["bg"])
    style.configure("TPanedwindow",  background=p["bg3"])
    style.configure("TLabel",        background=p["bg"], foreground=p["fg"])
    style.configure("Status.TLabel", background=p["bg_hard"], foreground=p["fg3"],
                                     font=("Segoe UI", 9), padding=(8, 3))
    style.configure("Editing.TLabel",    background=p["bg"], foreground=p["bright_blue"],
                                         font=("Segoe UI", 10, "bold"))
    style.configure("LivePreview.TLabel", background=p["bg"], foreground=p["bright_yellow"],
                                          font=("Segoe UI", 10))
    style.configure("TButton",
        background=p["bg1"], foreground=p["fg"],
        bordercolor=p["bg3"], lightcolor=p["bg2"], darkcolor=p["bg1"], padding=(8, 5),
    )
    style.map("TButton",
        background=[("active", p["bg2"]), ("pressed", p["bg3"]), ("disabled", p["bg"])],
        foreground=[("disabled", p["bg4"])],
    )
    style.configure("Accent.TButton",
        background=p["bright_orange"], foreground=p["bg"],
        font=("Segoe UI", 10, "bold"), padding=(8, 5),
    )
    style.map("Accent.TButton",
        background=[("active", p["orange"]), ("pressed", p["bg3"])],
        foreground=[("active", p["bg"])],
    )
    style.configure("TEntry",
        fieldbackground=p["bg1"], foreground=p["fg"],
        insertcolor=p["fg"], bordercolor=p["bg3"],
        lightcolor=p["bg2"], darkcolor=p["bg"], padding=4,
    )
    style.map("TEntry",
        fieldbackground=[("focus", p["bg2"])],
        bordercolor=[("focus", p["bright_yellow"])],
    )
    style.configure("Horizontal.TProgressbar",
        background=p["bright_yellow"], troughcolor=p["bg1"],
        bordercolor=p["bg2"], lightcolor=p["bright_yellow"], darkcolor=p["yellow"],
    )
    style.configure("TScrollbar",
        background=p["bg1"], troughcolor=p["bg"], bordercolor=p["bg2"],
        arrowcolor=p["fg2"], arrowsize=12,
    )
    style.map("TScrollbar", background=[("active", p["bg2"])])
    style.configure("TSeparator", background=p["bg3"])


# ══════════════════════════════════════════════════════════════════════════════
# Utility functions
# ══════════════════════════════════════════════════════════════════════════════

def setup_utf8_stdio() -> None:
    """Force UTF-8 encoding for stdout/stderr when running as a standalone script."""
    if sys.stdout is not None and hasattr(sys.stdout, "detach"):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
        except Exception:
            pass
    elif sys.stdout is None:
        sys.stdout = io.TextIOWrapper(open(os.devnull, "wb"), encoding="utf-8")
    if sys.stderr is not None and hasattr(sys.stderr, "detach"):
        try:
            sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding="utf-8")
        except Exception:
            pass
    elif sys.stderr is None:
        sys.stderr = io.TextIOWrapper(open(os.devnull, "wb"), encoding="utf-8")


def resource_path(relative_path: str) -> str:
    """Resolve resource path for both development and PyInstaller bundles."""
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, relative_path)


def sanitize_filename_part(text: str, replacement: str = "_") -> str:
    cleaned = INVALID_FILENAME_CHARS_RE.sub(replacement, text.strip())
    return cleaned.rstrip(". ")


def sanitize_base_name(base_name: str, fallback: str = "renamed") -> str:
    cleaned = INVALID_FILENAME_CHARS_RE.sub("_", base_name).strip().rstrip(". ")
    if not cleaned:
        cleaned = fallback
    if cleaned.upper() in WINDOWS_RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


def _normalize_pil_for_display(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16S", "I", "F"):
        extrema = img.getextrema()
        if isinstance(extrema, tuple) and len(extrema) == 2:
            lo, hi = extrema
            if hi > lo:
                scale = 255.0 / (hi - lo)
                img = img.point(lambda v, _lo=lo, _s=scale: int((v - _lo) * _s))
            else:
                img = img.point(lambda _v: 0)
        img = img.convert("L")
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    return img


def _extract_embedded_jpeg(raw_path: Path, max_scan_bytes: int = 16 * 1024 * 1024) -> Image.Image | None:
    with open(raw_path, "rb") as f:
        data = f.read(max_scan_bytes)
    best_img: Image.Image | None = None
    best_pixels = 0
    pos = 0
    while True:
        start = data.find(b"\xff\xd8\xff", pos)
        if start == -1:
            break
        try:
            with Image.open(io.BytesIO(data[start:])) as candidate:
                candidate.load()
                pixels = candidate.width * candidate.height
                if pixels > best_pixels:
                    best_pixels = pixels
                    best_img = candidate.copy()
        except Exception:
            pass
        pos = start + 3
        if best_pixels >= 800 * 600:
            break
    return best_img


def _make_placeholder_image(label_text: str, size: tuple[int, int] = (240, 240)) -> Image.Image:
    img = Image.new("RGB", size, color=(45, 48, 56))
    draw = ImageDraw.Draw(img)
    draw.rectangle([4, 4, size[0] - 5, size[1] - 5], outline=(100, 110, 130), width=2)
    draw.text((16, size[1] // 2 - 10), label_text[:24], fill=(220, 225, 235))
    return img


def load_pil_image(img_path: Path, target_size: tuple[int, int] | None = None) -> Image.Image:
    ext = img_path.suffix.lower()

    if ext in RAW_EXTENSIONS and HAS_RAWPY:
        try:
            with rawpy.imread(str(img_path)) as raw:
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        with Image.open(io.BytesIO(thumb.data)) as img:
                            img.load()
                            return _normalize_pil_for_display(img)
                    if thumb.format == rawpy.ThumbFormat.BITMAP:
                        return _normalize_pil_for_display(Image.fromarray(thumb.data))
                except Exception:
                    pass
                rgb = raw.postprocess(use_camera_wb=True, half_size=target_size is not None)
                return _normalize_pil_for_display(Image.fromarray(rgb))
        except Exception:
            pass

    try:
        with Image.open(img_path) as img:
            if target_size is not None and ext in (".jpg", ".jpeg"):
                img.draft("RGB", target_size)
            try:
                img.seek(0)
            except (EOFError, AttributeError):
                pass
            img.load()
            copied = img.copy()
        return _normalize_pil_for_display(copied)
    except Exception:
        pass

    if ext in RAW_EXTENSIONS:
        embedded = _extract_embedded_jpeg(img_path)
        if embedded is not None:
            return _normalize_pil_for_display(embedded)

    return _make_placeholder_image(f"[{ext.lstrip('.').upper() or 'IMG'}]\n{img_path.name}")


def build_new_stem(
    values: Iterable[str],
    separator: str,
    original_stem: str,
    prefixes: Iterable[str] | None = None,
    suffixes: Iterable[str] | None = None,
) -> str:
    vals_list = list(values)
    pre_list = list(prefixes) if prefixes is not None else [""] * len(vals_list)
    suf_list = list(suffixes) if suffixes is not None else [""] * len(vals_list)
    non_empty: list[str] = []
    for idx, val in enumerate(vals_list):
        if not val.strip():
            continue
        pre = pre_list[idx] if idx < len(pre_list) else ""
        suf = suf_list[idx] if idx < len(suf_list) else ""
        combined = sanitize_filename_part(f"{pre}{val.strip()}{suf}")
        if combined:
            non_empty.append(combined)
    if not non_empty:
        return original_stem
    return sanitize_base_name(separator.join(non_empty), fallback=original_stem)


def plan_renames(
    all_images: list[str],
    rename_map: dict[str, list[str]],
    separator: str,
    prefixes: list[str] | None = None,
    suffixes: list[str] | None = None,
) -> list[tuple[str, str]]:
    edited_set = set(rename_map.keys())
    occupied = {name.lower() for name in all_images if name not in edited_set}
    planned: list[tuple[str, str]] = []

    for old_name in all_images:
        if old_name not in rename_map:
            continue
        values = rename_map[old_name]
        if not any(v.strip() for v in values):
            continue
        path_obj = Path(old_name)
        stem, ext = path_obj.stem, path_obj.suffix
        base = build_new_stem(values, separator, stem, prefixes=prefixes, suffixes=suffixes)
        candidate = f"{base}{ext}"
        counter = 1
        while candidate.lower() in occupied:
            candidate = f"{base}({counter}){ext}"
            counter += 1
        occupied.add(candidate.lower())
        if candidate != old_name:
            planned.append((old_name, candidate))

    return planned


def execute_renames(folder: Path, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if not pairs:
        return []
    temp_moves: list[tuple[Path, Path, str, str]] = []
    executed: list[tuple[str, str]] = []
    try:
        for old_name, new_name in pairs:
            src = folder / old_name
            if not src.exists():
                raise FileNotFoundError(f"Source file not found: {src}")
            tmp = folder / f".tmp_ren_{uuid.uuid4().hex}_{old_name}"
            src.rename(tmp)
            temp_moves.append((tmp, folder / new_name, old_name, new_name))
        for tmp, dst, old_name, new_name in temp_moves:
            if dst.exists():
                raise FileExistsError(f"Target already exists: {dst}")
            tmp.rename(dst)
            executed.append((old_name, new_name))
        return executed
    except Exception:
        for tmp, _dst, old_name, _new_name in temp_moves:
            if tmp.exists():
                orig = folder / old_name
                if not orig.exists():
                    tmp.rename(orig)
        raise


def migrate_loaded_map(raw_map: dict, field_titles: list[str]) -> dict[str, list[str]]:
    normalized: dict[str, list[str]] = {}
    for img_name, entry in raw_map.items():
        if isinstance(entry, dict):
            values = [str(entry.get(title, "")) for title in field_titles]
        elif isinstance(entry, list):
            values = [str(v) for v in entry[: len(field_titles)]]
            if len(values) < len(field_titles):
                values.extend([""] * (len(field_titles) - len(values)))
        else:
            continue
        if any(v.strip() for v in values):
            normalized[img_name] = values
    return normalized


# ══════════════════════════════════════════════════════════════════════════════
# Main Application
# ══════════════════════════════════════════════════════════════════════════════

class ImageRenamerApp:
    """Main Tkinter GUI application for batch image renaming."""

    THUMB_SIZE_OPTIONS: dict[str, tuple[int, int]] = {
        "Small (64px)":  (64, 64),
        "Medium (80px)": (80, 80),
        "Large (96px)":  (96, 96),
    }
    DEFAULT_THUMB_KEY = "Medium (80px)"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Image Filename Renamer 2.0")
        self.root.geometry("1240x820")

        # ── Theme state ───────────────────────────────────────────────
        self.current_theme_name: str = DEFAULT_THEME
        self.current_palette: dict[str, str] = (
            SVTTK_PALETTES[DEFAULT_THEME] if DEFAULT_THEME in SVTTK_THEMES
            else CUSTOM_THEMES[DEFAULT_THEME]
        )
        self.style = ttk.Style()
        self._all_menus: list[tk.Menu] = []
        self._theme_name_var = tk.StringVar(value=DEFAULT_THEME)

        # ── Thumbnail size state ──────────────────────────────────────
        self._thumb_size_var = tk.StringVar(value=self.DEFAULT_THUMB_KEY)
        self.THUMB_SIZE: tuple[int, int] = self.THUMB_SIZE_OPTIONS[self.DEFAULT_THUMB_KEY]

        # ── Application state ─────────────────────────────────────────
        self.folder_path: Path | None = None
        self.field_titles: list[str] = []
        self.field_prefixes: list[str] = []
        self.field_suffixes: list[str] = []
        self.separator: str = ""
        self.images: list[str] = []
        self.current_index: int = 0
        self.field_entries: list[ttk.Entry] = []
        self.prefix_entries: list[ttk.Entry] = []
        self.suffix_entries: list[ttk.Entry] = []
        self.rename_map: dict[str, list[str]] = {}
        self.original_name_map: dict[str, str] = {}
        self.last_rename_history: list[tuple[str, str]] = []

        # ── Preview & cache state ─────────────────────────────────────
        self.thumbnail_cache: dict[str, ImageTk.PhotoImage] = {}
        self.all_preview_labels: list[tk.Label] = []
        self.preview_start: int = 0
        self._last_layout_cols: int = 0
        self._last_layout_limit: int = 0
        self._resize_after_id: str | None = None
        self._thumb_cancel_event = threading.Event()
        self._save_after_id: str | None = None

        # ── Main canvas image state ───────────────────────────────────
        self.main_image_size: int = 500
        self.current_pil_image: Image.Image | None = None
        self.current_tk_image: ImageTk.PhotoImage | None = None
        self.canvas_image_id: int | None = None
        self.image_offset_x: int = 0
        self.image_offset_y: int = 0
        self.last_x: int = 0
        self.last_y: int = 0

        self._load_icon()
        self._build_ui()
        self._build_menu()
        self._bind_shortcuts()
        self._apply_theme()
        # DWM title bar colour needs the HWND, which is ready after the event loop starts
        self.root.after(50, self._set_titlebar_color)

    # ──────────────────────────────────────────────────────────────────────────
    # Theme
    # ──────────────────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        """Dispatch to sv-ttk or custom-palette theming then update all tk widgets."""
        name = self.current_theme_name
        if name in SVTTK_THEMES:
            self._apply_svttk_theme(name)
        else:
            palette = CUSTOM_THEMES[name]
            self.current_palette = palette
            apply_custom_theme(self.root, self.style, palette)

        self._apply_canvas_colors()
        self._apply_menu_colors()
        self.load_all_previews(force=True)
        self._update_status_bar()

    def _apply_svttk_theme(self, name: str) -> None:
        """Apply Windows 11 style via sv-ttk + our label colour overrides."""
        self.current_palette = SVTTK_PALETTES[name]
        p = self.current_palette

        if HAS_SV_TTK:
            sv_ttk.set_theme(SVTTK_THEMES[name])
        else:
            # Graceful fallback when sv-ttk is not installed
            fallback = "Gruvbox Dark" if "Dark" in name else "Gruvbox Light"
            self.current_theme_name = fallback
            self._theme_name_var.set(fallback)
            self.current_palette = CUSTOM_THEMES[fallback]
            apply_custom_theme(self.root, self.style, self.current_palette)
            return

        self.root.configure(bg=p["bg"])
        # Apply only the label/status styles on top of sv-ttk
        self.style.configure("Status.TLabel",
            foreground=p["fg3"], font=("Segoe UI", 9), padding=(8, 3),
        )
        self.style.configure("Editing.TLabel",
            foreground=p["bright_blue"], font=("Segoe UI", 10, "bold"),
        )
        self.style.configure("LivePreview.TLabel",
            foreground=p["bright_blue"], font=("Segoe UI", 10),
        )

    def _apply_canvas_colors(self) -> None:
        p = self.current_palette
        self.main_image_canvas.configure(bg=p["canvas_bg"])
        self.preview_canvas.configure(bg=p["bg"])

    def _apply_menu_colors(self) -> None:
        p = self.current_palette
        for menu in self._all_menus:
            try:
                menu.configure(
                    bg=p["bg1"], fg=p["fg"],
                    activebackground=p["bg2"], activeforeground=p["bright_yellow"],
                    borderwidth=0,
                )
            except tk.TclError:
                pass

    def _set_titlebar_color(self) -> None:
        """
        Set the Win32 title bar to dark or light mode via DWM API.
        Works on Windows 10 (1809+) and Windows 11.
        Silently ignored on other platforms.
        """
        try:
            is_dark = self.current_theme_name in DARK_THEMES
            value = ctypes.c_int(1 if is_dark else 0)
            hwnd = self.root.winfo_id()
            # DWMWA_USE_IMMERSIVE_DARK_MODE: attribute 20 on Win11, 19 on Win10
            for attr in (20, 19):
                try:
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def toggle_theme(self) -> None:
        partner = THEME_TOGGLE_PAIRS.get(self.current_theme_name, self.current_theme_name)
        self.set_theme(partner)

    def set_theme(self, name: str) -> None:
        self.current_theme_name = name
        self._theme_name_var.set(name)
        self._apply_theme()
        self.root.after(50, self._set_titlebar_color)

    def set_thumb_size(self, size_key: str) -> None:
        self._thumb_size_var.set(size_key)
        self.THUMB_SIZE = self.THUMB_SIZE_OPTIONS[size_key]
        self._last_layout_cols = 0
        self._last_layout_limit = 0
        if self.folder_path and self.images:
            self.thumbnail_cache.clear()
            self._start_thumbnail_generation()
        else:
            self.load_all_previews(force=True)

    def _reset_to_defaults(self) -> None:
        self.set_theme(DEFAULT_THEME)
        self.set_thumb_size(self.DEFAULT_THUMB_KEY)

    # ──────────────────────────────────────────────────────────────────────────
    # UI Building
    # ──────────────────────────────────────────────────────────────────────────

    def _load_icon(self) -> None:
        icon_path = Path(resource_path("img_ren.ico"))
        if icon_path.exists():
            try:
                with Image.open(icon_path) as icon:
                    icon.load()
                    self._icon_photo = ImageTk.PhotoImage(icon.copy())
                self.root.iconphoto(True, self._icon_photo)
            except Exception as e:
                print(f"Failed to load icon: {e}")

    def _build_ui(self) -> None:
        pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # ── Left panel ───────────────────────────────────────────────
        left_frame = ttk.Frame(pane)
        pane.add(left_frame, weight=1)

        top_bar = ttk.Frame(left_frame)
        top_bar.pack(pady=8, fill=tk.X, padx=10)
        ttk.Button(top_bar, text="📂  Load Folder", command=self.load_folder).pack(side=tk.LEFT)
        self.status_label = ttk.Label(top_bar, text="No folder loaded", foreground="gray")
        self.status_label.pack(side=tk.LEFT, padx=10)

        fields_setup_frame = ttk.Frame(left_frame)
        fields_setup_frame.pack(pady=5, padx=10, fill=tk.X)
        ttk.Label(fields_setup_frame, text="Field Titles (comma-separated):").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.fields_entry = ttk.Entry(fields_setup_frame, width=28)
        self.fields_entry.grid(row=0, column=1, padx=5, pady=2)
        ttk.Label(fields_setup_frame, text="Separator:").grid(
            row=1, column=0, sticky="w", padx=5, pady=2
        )
        self.separator_entry = ttk.Entry(fields_setup_frame, width=28)
        self.separator_entry.grid(row=1, column=1, padx=5, pady=2)
        self.separator_entry.bind("<KeyRelease>", lambda _e: self.update_live_preview())
        ttk.Button(fields_setup_frame, text="✔  Set Fields", command=self.set_fields).grid(
            row=2, columnspan=2, pady=5
        )

        self.fields_frame = ttk.Frame(left_frame)
        self.fields_frame.pack(pady=5, padx=10, fill=tk.X)

        self.live_preview_label = ttk.Label(
            left_frame, text="New Name: —",
            style="LivePreview.TLabel", wraplength=380,
        )
        self.live_preview_label.pack(pady=4, padx=10, anchor="w")

        nav_frame = ttk.Frame(left_frame)
        nav_frame.pack(pady=6, padx=10, fill=tk.X)
        # Create Next before Prev so Tab from the input fields reaches Next first
        self.next_button = ttk.Button(nav_frame, text="Next  ▶", command=self.next_image)
        self.next_button.grid(row=0, column=0, padx=4)
        self.prev_button = ttk.Button(nav_frame, text="◀  Prev", command=self.prev_image)
        self.prev_button.grid(row=0, column=1, padx=4)
        self.image_count_label = ttk.Label(nav_frame, text="Image 0 of 0")
        self.image_count_label.grid(row=0, column=2, padx=8)

        action_frame = ttk.Frame(left_frame)
        action_frame.pack(pady=4, padx=10, fill=tk.X)
        ttk.Button(
            action_frame, text="⚡  Rename Now",
            command=self.apply_renames_now, style="Accent.TButton",
        ).grid(row=0, column=0, padx=4, pady=2)
        self.undo_button = ttk.Button(
            action_frame, text="↺  Undo Rename",
            command=self.undo_last_renames, state=tk.DISABLED,
        )
        self.undo_button.grid(row=0, column=1, padx=4, pady=2)
        ttk.Button(action_frame, text="🖹  Export .bat", command=self.generate_bat).grid(
            row=0, column=2, padx=4, pady=2
        )
        ttk.Button(action_frame, text="↓  Fill Down",    command=self.fill_down).grid(
            row=1, column=0, padx=4, pady=2
        )
        ttk.Button(action_frame, text="✕  Clear Fields", command=self.clear_current_fields).grid(
            row=1, column=1, padx=4, pady=2
        )
        self.restore_button = ttk.Button(
            action_frame, text="⟲  Restore Original",
            command=self.restore_original_names, state=tk.DISABLED,
        )
        self.restore_button.grid(row=1, column=2, padx=4, pady=2)

        self.all_preview_frame = ttk.Frame(left_frame)
        self.all_preview_frame.pack(pady=8, padx=8, fill=tk.BOTH, expand=True)

        self.preview_canvas = tk.Canvas(self.all_preview_frame, highlightthickness=0)
        self.preview_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.scrollable_frame = ttk.Frame(self.preview_canvas)
        self.preview_canvas_window = self.preview_canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        button_frame = ttk.Frame(self.all_preview_frame)
        button_frame.pack(side=tk.BOTTOM, pady=5)
        ttk.Button(button_frame, text="‹", command=self.prev_page, width=3).grid(row=0, column=0, padx=5)
        self.page_label = ttk.Label(button_frame, text="Page 0/0")
        self.page_label.grid(row=0, column=1, padx=6)
        ttk.Button(button_frame, text="›", command=self.next_page, width=3).grid(row=0, column=2, padx=5)

        self.all_preview_frame.bind("<Configure>", self._on_preview_resize)

        # ── Right panel ──────────────────────────────────────────────
        right_frame = ttk.Frame(pane)
        pane.add(right_frame, weight=2)

        editing_frame = ttk.Frame(right_frame)
        editing_frame.pack(pady=6, padx=10, fill=tk.X)
        self.editing_label = ttk.Label(
            editing_frame, text="Editing: No image", style="Editing.TLabel"
        )
        self.editing_label.pack(side=tk.LEFT)
        ttk.Button(editing_frame, text="↺  Reset View", command=self.reset_view).pack(side=tk.RIGHT)

        self.main_image_canvas = tk.Canvas(right_frame, highlightthickness=0)
        self.main_image_canvas.pack(pady=6, padx=8, fill=tk.BOTH, expand=True)
        self.main_image_canvas.bind("<MouseWheel>",      self.zoom_image)
        self.main_image_canvas.bind("<Button-1>",        self.start_drag)
        self.main_image_canvas.bind("<B1-Motion>",       self.move_image)
        self.main_image_canvas.bind("<Double-Button-1>", lambda _e: self.reset_view())
        self.main_image_canvas.bind("<Configure>",       lambda _e: self._render_current_image())

        # ── Status bar ───────────────────────────────────────────────
        self.status_bar = ttk.Label(
            self.root, text="Ready", style="Status.TLabel", anchor="w"
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_menu(self) -> None:
        """Build the top menubar (all labels in English)."""
        p = self.current_palette

        def mk_menu(parent: tk.Widget, tearoff: int = 0) -> tk.Menu:
            m = tk.Menu(parent, tearoff=tearoff,
                        bg=p["bg1"], fg=p["fg"],
                        activebackground=p["bg2"], activeforeground=p["bright_yellow"],
                        borderwidth=0)
            self._all_menus.append(m)
            return m

        menubar = mk_menu(self.root)
        self.root.config(menu=menubar)

        # ── Preferences ──────────────────────────────────────────────
        pref_menu = mk_menu(menubar)
        menubar.add_cascade(label="⚙  Preferences", menu=pref_menu)

        # Theme submenu
        theme_menu = mk_menu(pref_menu)
        pref_menu.add_cascade(label="🎨  Theme", menu=theme_menu)

        def add_group_header(menu: tk.Menu, text: str) -> None:
            menu.add_command(label=f"── {text} ──", state="disabled", font=("Segoe UI", 9))

        def add_theme_radio(menu: tk.Menu, name: str, label: str | None = None) -> None:
            menu.add_radiobutton(
                label=label or name,
                variable=self._theme_name_var,
                value=name,
                command=lambda n=name: self.set_theme(n),
            )

        add_group_header(theme_menu, "Windows 11")
        add_theme_radio(theme_menu, "Win11 Light", "Light")
        add_theme_radio(theme_menu, "Win11 Dark",  "Dark")

        theme_menu.add_separator()
        add_group_header(theme_menu, "Gruvbox")
        add_theme_radio(theme_menu, "Gruvbox Dark")
        add_theme_radio(theme_menu, "Gruvbox Light")

        theme_menu.add_separator()
        add_group_header(theme_menu, "Color Schemes")
        add_theme_radio(theme_menu, "Dracula")
        add_theme_radio(theme_menu, "Nord")
        add_theme_radio(theme_menu, "Catppuccin Mocha")
        add_theme_radio(theme_menu, "Catppuccin Latte")

        theme_menu.add_separator()
        theme_menu.add_command(
            label="Toggle Dark / Light",
            command=self.toggle_theme, accelerator="Ctrl+T",
        )

        # Thumbnail size submenu
        thumb_menu = mk_menu(pref_menu)
        pref_menu.add_cascade(label="🖼  Thumbnail Size", menu=thumb_menu)
        for key in self.THUMB_SIZE_OPTIONS:
            thumb_menu.add_radiobutton(
                label=key,
                variable=self._thumb_size_var,
                value=key,
                command=lambda k=key: self.set_thumb_size(k),
            )

        pref_menu.add_separator()
        pref_menu.add_command(label="↺  Reset to Defaults", command=self._reset_to_defaults)

        # ── Actions ───────────────────────────────────────────────────
        action_menu = mk_menu(menubar)
        menubar.add_cascade(label="📋  Actions", menu=action_menu)
        action_menu.add_command(label="Next  ▶",             command=self.next_image,             accelerator="Ctrl+→ / PgDn")
        action_menu.add_command(label="◀  Prev",             command=self.prev_image,             accelerator="Ctrl+← / PgUp")
        action_menu.add_separator()
        action_menu.add_command(label="⚡  Rename Now",      command=self.apply_renames_now,    accelerator="Ctrl+Enter")
        action_menu.add_command(label="↺  Undo Rename",      command=self.undo_last_renames,    accelerator="Ctrl+Z")
        action_menu.add_command(label="⟲  Restore Original", command=self.restore_original_names)
        action_menu.add_command(label="↓  Fill Down",     command=self.fill_down,          accelerator="Ctrl+D")
        action_menu.add_command(label="✕  Clear Fields",  command=self.clear_current_fields, accelerator="Delete")
        action_menu.add_separator()
        action_menu.add_command(label="🖹  Export .bat",  command=self.generate_bat)
        action_menu.add_separator()
        action_menu.add_command(label="💾  Save Config",  command=lambda: self.save_config(show_toast=True), accelerator="Ctrl+S")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Prior>",          lambda _e: self.prev_image())
        self.root.bind("<Next>",           lambda _e: self.next_image())
        self.root.bind("<Control-Left>",   lambda _e: self.prev_image())
        self.root.bind("<Control-Right>",  lambda _e: self.next_image())
        self.root.bind("<Control-s>",      lambda _e: self.save_config(show_toast=True))
        self.root.bind("<Control-t>",      lambda _e: self.toggle_theme())
        self.root.bind("<Control-d>",      lambda _e: self.fill_down())
        self.root.bind("<Control-z>",      lambda _e: self.undo_last_renames())
        self.root.bind("<Control-Return>", lambda _e: self.apply_renames_now())
        self.root.bind("<Delete>",         lambda _e: self._on_delete_key())

    def _on_delete_key(self) -> None:
        focused = self.root.focus_get()
        if isinstance(focused, (ttk.Entry, tk.Entry)):
            return
        self.clear_current_fields()

    # ──────────────────────────────────────────────────────────────────────────
    # Folder & Thumbnail Loading (Thread-safe)
    # ──────────────────────────────────────────────────────────────────────────

    def load_folder(self) -> None:
        selected = filedialog.askdirectory()
        if not selected:
            return

        folder = Path(selected)
        found = sorted(
            p.name
            for p in folder.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        )

        self._thumb_cancel_event.set()
        self._thumb_cancel_event = threading.Event()

        self.folder_path = folder
        self.images = found
        self.rename_map.clear()
        self.original_name_map.clear()
        self.last_rename_history.clear()
        self.undo_button.config(state=tk.DISABLED)
        self.restore_button.config(state=tk.DISABLED)
        self.current_index = 0
        self.preview_start = 0
        self.thumbnail_cache.clear()
        self.current_pil_image = None
        self.current_tk_image = None
        self.canvas_image_id = None
        self.main_image_canvas.delete("all")

        self.field_titles = []
        self.field_prefixes = []
        self.field_suffixes = []
        self.separator = ""
        self.fields_entry.delete(0, tk.END)
        self.separator_entry.delete(0, tk.END)
        self._rebuild_field_entries()

        if not self.images:
            messagebox.showerror("Error", "No supported image files found in the folder.")
            self.image_count_label.config(text="Image 0 of 0")
            self.editing_label.config(text="Editing: No image")
            self.status_label.config(text="0 images")
            self.load_all_previews(force=True)
            self._update_status_bar()
            return

        self.status_label.config(text=f"{len(self.images)} images")
        self._load_config()
        self._start_thumbnail_generation()

    def _load_config(self) -> None:
        if not self.folder_path:
            return
        config_path = self.folder_path / "rename_config.json"
        if not config_path.exists():
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.field_titles = [str(t).strip() for t in config.get("field_titles", []) if str(t).strip()]
            raw_pre = config.get("field_prefixes", [])
            raw_suf = config.get("field_suffixes", [])
            self.field_prefixes = [
                str(raw_pre[i]) if isinstance(raw_pre, list) and i < len(raw_pre) else ""
                for i in range(len(self.field_titles))
            ]
            self.field_suffixes = [
                str(raw_suf[i]) if isinstance(raw_suf, list) and i < len(raw_suf) else ""
                for i in range(len(self.field_titles))
            ]
            self.separator = str(config.get("separator", ""))
            raw_map = config.get("rename_map", {})
            self.rename_map = migrate_loaded_map(raw_map, self.field_titles)
            raw_orig = config.get("original_names", {})
            if isinstance(raw_orig, dict):
                image_set = set(self.images)
                self.original_name_map = {
                    str(curr): str(orig)
                    for curr, orig in raw_orig.items()
                    if str(curr) in image_set and str(curr) != str(orig)
                }
            self._update_restore_button_state()
            if self.field_titles:
                self.fields_entry.insert(0, ",".join(self.field_titles))
            if self.separator:
                self.separator_entry.insert(0, self.separator)
            self._rebuild_field_entries()
        except Exception as e:
            messagebox.showwarning("Config Warning", f"Failed to read rename_config.json:\n{e}")

    def _start_thumbnail_generation(self) -> None:
        assert self.folder_path is not None
        total = len(self.images)
        p = self.current_palette

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Loading Images")
        progress_window.geometry("320x110")
        progress_window.transient(self.root)
        progress_window.grab_set()
        progress_window.configure(bg=p["bg"])

        ttk.Label(progress_window, text=f"Loading {total} thumbnails...").pack(pady=10)
        progress_bar = ttk.Progressbar(
            progress_window, orient="horizontal", length=260, mode="determinate", maximum=total
        )
        progress_bar.pack(pady=8)

        progress_queue: queue.Queue[tuple[int, str, Image.Image]] = queue.Queue()
        cancel_event = self._thumb_cancel_event
        folder = self.folder_path
        image_list = list(self.images)
        thumb_size = self.THUMB_SIZE

        def worker() -> None:
            for idx, img_name in enumerate(image_list, start=1):
                if cancel_event.is_set():
                    return
                pil_thumb = load_pil_image(folder / img_name, target_size=thumb_size)
                pil_thumb.thumbnail(thumb_size, RESAMPLE_LANCZOS)
                progress_queue.put((idx, img_name, pil_thumb))

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(
            50, self._poll_thumbnail_queue,
            progress_bar, progress_queue, total, progress_window, cancel_event,
        )

    def _poll_thumbnail_queue(
        self,
        progress_bar: ttk.Progressbar,
        progress_queue: queue.Queue[tuple[int, str, Image.Image]],
        total: int,
        progress_window: tk.Toplevel,
        cancel_event: threading.Event,
    ) -> None:
        if cancel_event.is_set():
            if progress_window.winfo_exists():
                progress_window.destroy()
            return
        processed = 0
        while not progress_queue.empty() and processed < 25:
            idx, img_name, pil_thumb = progress_queue.get_nowait()
            self.thumbnail_cache[img_name] = ImageTk.PhotoImage(pil_thumb)
            progress_bar["value"] = idx
            processed += 1
        if progress_bar["value"] >= total:
            if progress_window.winfo_exists():
                progress_window.destroy()
            self.show_image(self.current_index, save_current=False)
            self.load_all_previews(force=True)
            self._update_status_bar()
        else:
            self.root.after(
                50, self._poll_thumbnail_queue,
                progress_bar, progress_queue, total, progress_window, cancel_event,
            )

    # ──────────────────────────────────────────────────────────────────────────
    # Thumbnail cache virtualization
    # ──────────────────────────────────────────────────────────────────────────

    def _evict_thumbnail_cache(self) -> None:
        _, limit = self._calculate_preview_grid()
        if limit == 0:
            return
        keep_start = max(0, self.preview_start - limit * THUMB_CACHE_PAGES)
        keep_end   = min(len(self.images), self.preview_start + limit * (THUMB_CACHE_PAGES + 1))
        keep_names = set(self.images[keep_start:keep_end])
        for k in [k for k in list(self.thumbnail_cache) if k not in keep_names]:
            del self.thumbnail_cache[k]

    def _load_missing_thumbs_async(self) -> None:
        if not self.folder_path:
            return
        _, limit = self._calculate_preview_grid()
        end = min(self.preview_start + limit, len(self.images))
        missing = [
            self.images[i] for i in range(self.preview_start, end)
            if self.images[i] not in self.thumbnail_cache
        ]
        if not missing:
            return
        cancel_event = self._thumb_cancel_event
        folder = self.folder_path
        thumb_size = self.THUMB_SIZE
        q: queue.Queue = queue.Queue()

        def worker() -> None:
            for img_name in missing:
                if cancel_event.is_set():
                    break
                pil = load_pil_image(folder / img_name, target_size=thumb_size)
                pil.thumbnail(thumb_size, RESAMPLE_LANCZOS)
                q.put((img_name, pil))
            q.put(None)

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(50, self._poll_lazy_thumb_queue, q, cancel_event)

    def _poll_lazy_thumb_queue(self, q: queue.Queue, cancel_event: threading.Event) -> None:
        if cancel_event.is_set():
            return
        done = False
        updated = False
        while not q.empty():
            item = q.get_nowait()
            if item is None:
                done = True
                break
            img_name, pil = item
            self.thumbnail_cache[img_name] = ImageTk.PhotoImage(pil)
            updated = True
        if updated:
            self.load_all_previews(force=True)
        if not done:
            self.root.after(50, self._poll_lazy_thumb_queue, q, cancel_event)

    # ──────────────────────────────────────────────────────────────────────────
    # Fields & Config
    # ──────────────────────────────────────────────────────────────────────────

    def set_fields(self) -> None:
        titles_input = self.fields_entry.get()
        new_titles = [t.strip() for t in titles_input.split(",") if t.strip()]
        if not new_titles:
            messagebox.showerror("Error", "Please enter at least one field title.")
            return
        self.save_fields()
        old_titles = self.field_titles
        self.separator = self.separator_entry.get()
        self.field_titles = new_titles
        if old_titles and old_titles != new_titles:
            remapped: dict[str, list[str]] = {}
            for img, vals in self.rename_map.items():
                by_title = dict(zip(old_titles, vals))
                new_vals = [by_title.get(t, "") for t in new_titles]
                if any(v.strip() for v in new_vals):
                    remapped[img] = new_vals
            self.rename_map = remapped
            old_pre_by_title = dict(zip(old_titles, self.field_prefixes))
            old_suf_by_title = dict(zip(old_titles, self.field_suffixes))
            self.field_prefixes = [old_pre_by_title.get(t, "") for t in new_titles]
            self.field_suffixes = [old_suf_by_title.get(t, "") for t in new_titles]
        else:
            self.field_prefixes = [
                self.field_prefixes[i] if i < len(self.field_prefixes) else ""
                for i in range(len(new_titles))
            ]
            self.field_suffixes = [
                self.field_suffixes[i] if i < len(self.field_suffixes) else ""
                for i in range(len(new_titles))
            ]
        self._rebuild_field_entries()
        self.save_config()

    def _on_affix_change(self, idx: int) -> None:
        if idx < len(self.prefix_entries):
            self.field_prefixes[idx] = self.prefix_entries[idx].get()
        if idx < len(self.suffix_entries):
            self.field_suffixes[idx] = self.suffix_entries[idx].get()
        self.update_live_preview()
        self._schedule_save()

    def _rebuild_field_entries(self) -> None:
        for widget in self.fields_frame.winfo_children():
            widget.destroy()
        self.field_entries = []
        self.prefix_entries = []
        self.suffix_entries = []
        if self.field_titles:
            ttk.Label(self.fields_frame, text="Prefix", font=("Segoe UI", 8)).grid(
                row=0, column=1, padx=3, pady=(0, 2)
            )
            ttk.Label(self.fields_frame, text="Value", font=("Segoe UI", 8)).grid(
                row=0, column=2, padx=3, pady=(0, 2)
            )
            ttk.Label(self.fields_frame, text="Suffix", font=("Segoe UI", 8)).grid(
                row=0, column=3, padx=3, pady=(0, 2)
            )
        while len(self.field_prefixes) < len(self.field_titles):
            self.field_prefixes.append("")
        while len(self.field_suffixes) < len(self.field_titles):
            self.field_suffixes.append("")
        for row_idx, title in enumerate(self.field_titles):
            grid_row = row_idx + 1
            ttk.Label(self.fields_frame, text=f"{title}:").grid(
                row=grid_row, column=0, sticky="w", padx=6, pady=3
            )
            pre_entry = ttk.Entry(self.fields_frame, width=8, takefocus=False)
            pre_entry.grid(row=grid_row, column=1, padx=3, pady=3)
            pre_entry.insert(0, self.field_prefixes[row_idx])
            pre_entry.bind("<KeyRelease>", lambda _e, idx=row_idx: self._on_affix_change(idx))
            self.prefix_entries.append(pre_entry)

            entry = ttk.Entry(self.fields_frame, width=18)
            entry.grid(row=grid_row, column=2, padx=3, pady=3)
            entry.bind("<KeyRelease>", lambda _e: self.update_live_preview())
            entry.bind("<Return>", lambda _e, idx=row_idx: self._on_field_enter(idx))
            entry.bind("<Control-Left>", lambda _e: (self.prev_image(), "break")[1])
            entry.bind("<Control-Right>", lambda _e: (self.next_image(), "break")[1])
            self.field_entries.append(entry)

            suf_entry = ttk.Entry(self.fields_frame, width=8, takefocus=False)
            suf_entry.grid(row=grid_row, column=3, padx=3, pady=3)
            suf_entry.insert(0, self.field_suffixes[row_idx])
            suf_entry.bind("<KeyRelease>", lambda _e, idx=row_idx: self._on_affix_change(idx))
            self.suffix_entries.append(suf_entry)
        if self.field_entries:
            self.field_entries[0].focus_set()
        self.load_fields()

    def _on_field_enter(self, entry_index: int) -> None:
        if entry_index + 1 < len(self.field_entries):
            self.field_entries[entry_index + 1].focus_set()
            self.field_entries[entry_index + 1].select_range(0, tk.END)
        else:
            self.next_image()

    def load_fields(self) -> None:
        if not self.field_entries:
            self.update_live_preview()
            return
        for entry in self.field_entries:
            entry.delete(0, tk.END)
        if self.images and 0 <= self.current_index < len(self.images):
            img_name = self.images[self.current_index]
            values = self.rename_map.get(img_name, [])
            for entry, value in zip(self.field_entries, values):
                entry.insert(0, value)
        self.update_live_preview()

    def save_fields(self) -> None:
        if not self.images or not self.field_entries:
            return
        if not (0 <= self.current_index < len(self.images)):
            return
        img_name = self.images[self.current_index]
        values = [entry.get() for entry in self.field_entries]
        old_values = self.rename_map.get(img_name)
        if not any(v.strip() for v in values):
            if old_values is not None:
                del self.rename_map[img_name]
                self._schedule_save()
            return
        if old_values != values:
            self.rename_map[img_name] = values
            self._schedule_save()

    def update_live_preview(self) -> None:
        if not self.images or not (0 <= self.current_index < len(self.images)):
            self.live_preview_label.config(text="New Name: —")
            return
        img_name = self.images[self.current_index]
        sep = self.separator_entry.get()
        values = [entry.get() for entry in self.field_entries]
        stem = Path(img_name).stem
        ext = Path(img_name).suffix
        new_stem = build_new_stem(
            values, sep, stem, prefixes=self.field_prefixes, suffixes=self.field_suffixes
        )
        self.live_preview_label.config(text=f"New Name: {new_stem}{ext}")
        self._update_status_bar()

    def _schedule_save(self) -> None:
        """Debounced save: waits 500 ms after last change before writing to disk."""
        if self._save_after_id is not None:
            self.root.after_cancel(self._save_after_id)
        self._save_after_id = self.root.after(500, self.save_config)

    def save_config(self, show_toast: bool = False) -> None:
        self._save_after_id = None
        if not self.folder_path:
            return
        serialized_map = {
            img: dict(zip(self.field_titles, vals))
            for img, vals in self.rename_map.items()
            if any(v.strip() for v in vals)
        }
        config = {
            "version": 2,
            "rename_map": serialized_map,
            "field_titles": self.field_titles,
            "field_prefixes": self.field_prefixes,
            "field_suffixes": self.field_suffixes,
            "separator": self.separator_entry.get(),
            "original_names": self.original_name_map,
        }
        config_path = self.folder_path / "rename_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        if show_toast:
            self.status_label.config(text="✔ Config saved")
            self.root.after(2000, lambda: self.status_label.config(text=f"{len(self.images)} images"))

    # ──────────────────────────────────────────────────────────────────────────
    # Main Image Display, Pan & Zoom
    # ──────────────────────────────────────────────────────────────────────────

    def show_image(self, index: int, save_current: bool = True) -> None:
        if not self.images or not self.folder_path:
            return
        if not (0 <= index < len(self.images)):
            return
        if save_current and index != self.current_index:
            self.save_fields()
        self.current_index = index
        img_name = self.images[self.current_index]
        self.current_pil_image = load_pil_image(self.folder_path / img_name)
        self.image_offset_x = 0
        self.image_offset_y = 0
        cw = max(200, self.main_image_canvas.winfo_width())
        ch = max(200, self.main_image_canvas.winfo_height())
        self.main_image_size = max(200, min(cw - 20, ch - 20, 700))
        self._render_current_image()
        self.editing_label.config(text=f"Editing: {img_name}")
        self.image_count_label.config(text=f"Image {self.current_index + 1} of {len(self.images)}")
        self.update_preview_highlight()
        self.load_fields()

    def _render_current_image(self) -> None:
        if self.current_pil_image is None:
            return
        img_copy = self.current_pil_image.copy()
        img_copy.thumbnail((self.main_image_size, self.main_image_size), RESAMPLE_LANCZOS)
        self.current_tk_image = ImageTk.PhotoImage(img_copy)
        cw = max(1, self.main_image_canvas.winfo_width())
        ch = max(1, self.main_image_canvas.winfo_height())
        cx = cw // 2 + self.image_offset_x
        cy = ch // 2 + self.image_offset_y
        if self.canvas_image_id is None:
            self.main_image_canvas.delete("all")
            self.canvas_image_id = self.main_image_canvas.create_image(
                cx, cy, image=self.current_tk_image, anchor="center"
            )
        else:
            self.main_image_canvas.itemconfig(self.canvas_image_id, image=self.current_tk_image)
            self.main_image_canvas.coords(self.canvas_image_id, cx, cy)

    def reset_view(self) -> None:
        self.image_offset_x = 0
        self.image_offset_y = 0
        cw = max(200, self.main_image_canvas.winfo_width())
        ch = max(200, self.main_image_canvas.winfo_height())
        self.main_image_size = max(200, min(cw - 20, ch - 20, 700))
        self._render_current_image()

    def zoom_image(self, event: tk.Event) -> None:
        if self.current_pil_image is None:
            return
        step = 60 if event.delta > 0 else -60
        self.main_image_size = max(100, min(2000, self.main_image_size + step))
        self._render_current_image()

    def start_drag(self, event: tk.Event) -> None:
        self.last_x = event.x
        self.last_y = event.y

    def move_image(self, event: tk.Event) -> None:
        if self.canvas_image_id is None:
            return
        dx = event.x - self.last_x
        dy = event.y - self.last_y
        self.image_offset_x += dx
        self.image_offset_y += dy
        self.last_x = event.x
        self.last_y = event.y
        self.main_image_canvas.move(self.canvas_image_id, dx, dy)

    # ──────────────────────────────────────────────────────────────────────────
    # Navigation & Thumbnail Grid
    # ──────────────────────────────────────────────────────────────────────────

    def prev_image(self) -> None:
        if self.current_index > 0:
            self.save_fields()
            self.show_image(self.current_index - 1, save_current=False)
            self.sync_preview_page()
            self.root.after(60, self._focus_first_entry)

    def next_image(self) -> None:
        if self.current_index < len(self.images) - 1:
            carried_values = [entry.get() for entry in self.field_entries]
            self.save_fields()
            self.show_image(self.current_index + 1, save_current=False)
            next_img = self.images[self.current_index]
            if next_img not in self.rename_map and any(v.strip() for v in carried_values):
                for entry, value in zip(self.field_entries, carried_values):
                    entry.delete(0, tk.END)
                    entry.insert(0, value)
                self.update_live_preview()
            self.sync_preview_page()
            self.root.after(60, self._focus_first_entry)

    def _focus_first_entry(self) -> None:
        if self.field_entries:
            self.field_entries[0].focus_set()
            self.field_entries[0].select_range(0, tk.END)

    def _calculate_preview_grid(self) -> tuple[int, int]:
        tw, th = self.THUMB_SIZE
        canvas_width  = max(tw + 16, self.preview_canvas.winfo_width())
        canvas_height = max(th + 30, self.preview_canvas.winfo_height())
        cols = max(1, canvas_width  // (tw + 16))
        rows = max(1, canvas_height // (th + 30))
        return cols, cols * rows

    def _on_preview_resize(self, _event: tk.Event) -> None:
        if self._resize_after_id is not None:
            self.root.after_cancel(self._resize_after_id)
        self._resize_after_id = self.root.after(150, self.load_all_previews)

    def sync_preview_page(self) -> None:
        _, limit = self._calculate_preview_grid()
        new_start = (self.current_index // limit) * limit
        if new_start != self.preview_start:
            self.preview_start = new_start
            self.load_all_previews(force=True)

    def prev_page(self) -> None:
        _, limit = self._calculate_preview_grid()
        if self.preview_start > 0:
            self.preview_start = max(0, self.preview_start - limit)
            self._evict_thumbnail_cache()
            self.load_all_previews(force=True)
            self._load_missing_thumbs_async()

    def next_page(self) -> None:
        _, limit = self._calculate_preview_grid()
        if self.preview_start + limit < len(self.images):
            self.preview_start += limit
            self._evict_thumbnail_cache()
            self.load_all_previews(force=True)
            self._load_missing_thumbs_async()

    def load_all_previews(self, force: bool = False) -> None:
        self._resize_after_id = None
        cols, limit = self._calculate_preview_grid()
        p = self.current_palette

        if not force and cols == self._last_layout_cols and limit == self._last_layout_limit:
            return
        self._last_layout_cols = cols
        self._last_layout_limit = limit

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.all_preview_labels = []

        if not self.images:
            self.page_label.config(text="Page 0/0")
            return

        total_pages  = max(1, (len(self.images) + limit - 1) // limit)
        current_page = (self.preview_start // limit) + 1
        self.page_label.config(text=f"Page {current_page}/{total_pages}")

        end_index = min(self.preview_start + limit, len(self.images))
        tw, _th = self.THUMB_SIZE
        for i in range(self.preview_start, end_index):
            img_name = self.images[i]
            img_tk   = self.thumbnail_cache.get(img_name)
            short_name = (img_name[:11] + "…") if len(img_name) > 12 else img_name
            label = tk.Label(
                self.scrollable_frame,
                image=img_tk, text=short_name,
                compound="bottom", wraplength=tw + 4, width=tw + 8,
                font=("Segoe UI", 8),
                bg=p["bg"], fg=p["fg"],
                cursor="hand2", highlightthickness=2, highlightbackground=p["bg"], bd=0,
            )
            label.image = img_tk
            row = (i - self.preview_start) // cols
            col = (i - self.preview_start) % cols
            label.grid(row=row, column=col, padx=3, pady=3)
            label.bind("<Button-1>", lambda _e, idx=i: self.show_image(idx, save_current=True))
            label.bind("<Button-3>", lambda e, idx=i: self._show_thumb_context_menu(e, idx))
            self.all_preview_labels.append(label)

        self.update_preview_highlight()
        self.scrollable_frame.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def update_preview_highlight(self) -> None:
        """🟡 current  🟢 named  · dim = unset"""
        p = self.current_palette
        for i, preview_label in enumerate(self.all_preview_labels):
            abs_idx  = i + self.preview_start
            img_name = self.images[abs_idx] if abs_idx < len(self.images) else None
            is_current = abs_idx == self.current_index
            is_named   = img_name in self.rename_map if img_name else False

            if is_current:
                preview_label.config(
                    bg=p["bg2"], fg=p["fg"],
                    highlightbackground=p["thumb_current"], highlightthickness=3,
                )
            elif is_named:
                preview_label.config(
                    bg=p["bg1"], fg=p["fg"],
                    highlightbackground=p["thumb_named"], highlightthickness=2,
                )
            else:
                preview_label.config(
                    bg=p["bg"], fg=p["fg3"],
                    highlightbackground=p["bg"], highlightthickness=1,
                )

    def _update_status_bar(self) -> None:
        named = len(self.rename_map)
        total = len(self.images)
        if total == 0:
            self.status_bar.config(text="Ready")
        else:
            folder_str = str(self.folder_path) if self.folder_path else "—"
            self.status_bar.config(text=f"Named: {named} / {total}  ·  {folder_str}")

    # ──────────────────────────────────────────────────────────────────────────
    # Right-click context menu on thumbnails
    # ──────────────────────────────────────────────────────────────────────────

    def _show_thumb_context_menu(self, event: tk.Event, img_index: int) -> None:
        p = self.current_palette
        img_name = self.images[img_index] if img_index < len(self.images) else None

        menu = tk.Menu(self.root, tearoff=0,
                       bg=p["bg1"], fg=p["fg"],
                       activebackground=p["bg2"], activeforeground=p["bright_yellow"],
                       borderwidth=1)
        menu.add_command(
            label="⮞  Select This Image",
            command=lambda: self.show_image(img_index, save_current=True),
        )
        menu.add_separator()
        menu.add_command(
            label="↓  Fill Down from Here",
            command=lambda: self.fill_down(from_index=img_index),
        )
        menu.add_command(
            label="✕  Clear Naming",
            command=lambda: self._clear_image_fields(img_name),
        )
        menu.add_separator()
        if self.folder_path and img_name:
            menu.add_command(
                label="📂  Show in Explorer",
                command=lambda n=img_name: subprocess.run(
                    ["explorer", "/select,", str(self.folder_path / n)], check=False,
                ),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ──────────────────────────────────────────────────────────────────────────
    # Actions
    # ──────────────────────────────────────────────────────────────────────────

    def fill_down(self, from_index: int | None = None) -> None:
        """Copy field values from from_index (default: current) to all subsequent unnamed images."""
        if not self.images or not self.field_entries:
            return
        src_index = from_index if from_index is not None else self.current_index
        if not (0 <= src_index < len(self.images)):
            return
        self.save_fields()
        src_name = self.images[src_index]
        values = self.rename_map.get(src_name)
        if not values or not any(v.strip() for v in values):
            messagebox.showinfo("Fill Down", "Source image has no naming values set.\nPlease fill in the fields first.")
            return
        count = sum(1 for img in self.images[src_index + 1:] if img not in self.rename_map)
        for img in self.images[src_index + 1:]:
            if img not in self.rename_map:
                self.rename_map[img] = list(values)
        self._schedule_save()
        self.update_preview_highlight()
        self._update_status_bar()
        self.status_bar.config(text=f"✔ Fill Down: applied to {count} unnamed image(s)")
        self.root.after(3000, self._update_status_bar)

    def clear_current_fields(self) -> None:
        img_name = (
            self.images[self.current_index]
            if self.images and 0 <= self.current_index < len(self.images)
            else None
        )
        self._clear_image_fields(img_name)

    def _clear_image_fields(self, img_name: str | None) -> None:
        if not img_name:
            return
        if img_name in self.rename_map:
            del self.rename_map[img_name]
            self._schedule_save()
        for entry in self.field_entries:
            entry.delete(0, tk.END)
        self.update_live_preview()
        self.update_preview_highlight()
        self._update_status_bar()

    def _get_planned_renames(self) -> list[tuple[str, str]]:
        self.save_fields()
        self.separator = self.separator_entry.get()
        if not self.rename_map:
            messagebox.showerror("Error", "Please set field values for at least one image first.")
            return []
        pairs = plan_renames(
            self.images,
            self.rename_map,
            self.separator,
            prefixes=self.field_prefixes,
            suffixes=self.field_suffixes,
        )
        if not pairs:
            messagebox.showinfo("Info", "No filenames need to be changed.")
        return pairs

    def apply_renames_now(self) -> None:
        if not self.folder_path:
            return
        pairs = self._get_planned_renames()
        if not pairs:
            return
        preview_lines = "\n".join(f"  {old}  →  {new}" for old, new in pairs[:8])
        if len(pairs) > 8:
            preview_lines += f"\n  … and {len(pairs) - 8} more"
        if not messagebox.askyesno(
            "Confirm Rename",
            f"Rename {len(pairs)} file(s) in:\n{self.folder_path}\n\n{preview_lines}",
        ):
            return
        try:
            executed = execute_renames(self.folder_path, pairs)
        except Exception as e:
            messagebox.showerror("Rename Failed", f"Error during rename:\n{e}")
            return
        self._apply_rename_mapping_to_state(executed)
        self.last_rename_history = [(new, old) for old, new in executed]
        self.undo_button.config(state=tk.NORMAL if self.last_rename_history else tk.DISABLED)
        self.save_config()
        self.show_image(self.current_index, save_current=False)
        self.load_all_previews(force=True)
        self._update_status_bar()
        messagebox.showinfo("Success", f"Successfully renamed {len(executed)} file(s).")

    def undo_last_renames(self) -> None:
        if not self.folder_path or not self.last_rename_history:
            return
        if not messagebox.askyesno(
            "Undo Rename",
            f"Revert the last {len(self.last_rename_history)} renamed file(s)?",
        ):
            return
        try:
            reverted = execute_renames(self.folder_path, self.last_rename_history)
        except Exception as e:
            messagebox.showerror("Undo Failed", f"Error during undo:\n{e}")
            return
        self._apply_rename_mapping_to_state(reverted)
        self.last_rename_history.clear()
        self.undo_button.config(state=tk.DISABLED)
        self.save_config()
        self.show_image(self.current_index, save_current=False)
        self.load_all_previews(force=True)
        self._update_status_bar()
        messagebox.showinfo("Undone", f"Reverted {len(reverted)} file(s).")

    def _update_restore_button_state(self) -> None:
        has_restorable = any(
            img in self.original_name_map and self.original_name_map[img] != img
            for img in self.images
        )
        self.restore_button.config(state=tk.NORMAL if has_restorable else tk.DISABLED)

    def restore_original_names(self) -> None:
        if not self.folder_path:
            return
        pairs = [
            (img, self.original_name_map[img])
            for img in self.images
            if img in self.original_name_map and self.original_name_map[img] != img
        ]
        if not pairs:
            messagebox.showinfo("Info", "No original filenames recorded to restore.")
            return
        preview_lines = "\n".join(f"  {curr}  →  {orig}" for curr, orig in pairs[:8])
        if len(pairs) > 8:
            preview_lines += f"\n  … and {len(pairs) - 8} more"
        if not messagebox.askyesno(
            "Restore Original Filenames",
            f"Restore {len(pairs)} file(s) to their original names in:\n{self.folder_path}\n\n{preview_lines}",
        ):
            return
        try:
            executed = execute_renames(self.folder_path, pairs)
        except Exception as e:
            messagebox.showerror("Restore Failed", f"Error during restore:\n{e}")
            return
        self._apply_rename_mapping_to_state(executed)
        self.last_rename_history = [(new, old) for old, new in executed]
        self.undo_button.config(state=tk.NORMAL if self.last_rename_history else tk.DISABLED)
        self.save_config()
        self.show_image(self.current_index, save_current=False)
        self.load_all_previews(force=True)
        self._update_status_bar()
        messagebox.showinfo("Success", f"Successfully restored {len(executed)} file(s).")

    def _apply_rename_mapping_to_state(self, pairs: list[tuple[str, str]]) -> None:
        rename_dict = dict(pairs)
        self.images = [rename_dict.get(name, name) for name in self.images]
        self.rename_map = {rename_dict.get(img, img): vals for img, vals in self.rename_map.items()}
        self.thumbnail_cache = {rename_dict.get(img, img): thumb for img, thumb in self.thumbnail_cache.items()}
        new_orig_map: dict[str, str] = {}
        for old_name, new_name in pairs:
            orig_name = self.original_name_map.pop(old_name, old_name)
            if new_name != orig_name:
                new_orig_map[new_name] = orig_name
        for img, orig_name in self.original_name_map.items():
            if img != orig_name:
                new_orig_map[img] = orig_name
        self.original_name_map = new_orig_map
        self._update_restore_button_state()

    def generate_bat(self) -> None:
        if not self.folder_path:
            return
        pairs = self._get_planned_renames()
        if not pairs:
            return
        bat_lines = ["@chcp 65001 >nul", f'cd /d "{self.folder_path}"']
        for old_name, new_name in pairs:
            safe_old = old_name.replace("%", "%%")
            safe_new = new_name.replace("%", "%%")
            bat_lines.append(f'ren "{safe_old}" "{safe_new}"')
        bat_lines.append("pause")
        bat_path = self.folder_path / "rename.bat"
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(bat_lines))
        messagebox.showinfo("Success", f"Rename commands saved to {bat_path}")


if __name__ == "__main__":
    setup_utf8_stdio()
    root = tk.Tk()
    app = ImageRenamerApp(root)
    root.mainloop()
