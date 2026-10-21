import cv2
import mediapipe as mp
import numpy as np
import tkinter as tk

from tkinter import messagebox, filedialog
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk

# =========================================================
# AI VIRTUAL PAINTER - PROFESSIONAL DESKTOP EDITION
# =========================================================

BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "hand_landmarker.task"
ARTWORKS_DIR = BASE_DIR / "artworks"
ARTWORKS_DIR.mkdir(exist_ok=True)

CANVAS_W, CANVAS_H = 1280, 720
PREVIEW_W, PREVIEW_H = 900, 506
SMOOTHING = 0.35

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        f"Missing model file: {MODEL_PATH}\n"
        "Keep hand_landmarker.task beside main.py."
    )

# OpenCV BGR colours
COLORS = {
    "Blue": (255, 100, 30),
    "Green": (50, 220, 70),
    "Red": (60, 60, 255),
    "Yellow": (0, 230, 255),
    "White": (255, 255, 255),
    "Purple": (220, 80, 200),
}

# =========================================================
# APPLICATION
# =========================================================

class VirtualPainter:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Virtual Painter | Creative Studio")
        self.root.geometry("1450x900")
        self.root.minsize(1100, 720)
        self.root.configure(bg="#10131c")

        self.canvas = np.zeros(
            (CANVAS_H, CANVAS_W, 3), dtype=np.uint8
        )

        self.color_name = "Blue"
        self.brush_size = tk.IntVar(value=8)
        self.eraser = False
        self.previous_point = None
        self.smooth_point = None
        self.frame_number = 0
        self.running = True
        self.camera = None
        self.detector = None
        self.current_photo = None
        self.gallery_photos = []
        self.status_text = tk.StringVar(
            value="Starting camera..."
        )
        self.mode_text = tk.StringVar(value="DRAW MODE")
        self.hand_text = tk.StringVar(value="Hand: not detected")
        self.selected_artwork = None

        self.build_interface()
        self.start_camera()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(10, self.update_frame)
        self.root.after(1000, self.refresh_gallery)

    # -----------------------------------------------------
    # INTERFACE
    # -----------------------------------------------------

    def build_interface(self):
        # Header
        header = tk.Frame(self.root, bg="#171c29", height=78)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="✦  AI VIRTUAL PAINTER",
            font=("Segoe UI", 22, "bold"),
            bg="#171c29", fg="#f1f5ff"
        ).pack(side="left", padx=24, pady=15)

        tk.Label(
            header, text="CREATIVE STUDIO  •  COMPUTER VISION",
            font=("Segoe UI", 10, "bold"),
            bg="#171c29", fg="#8b9ab8"
        ).pack(side="right", padx=24)

        # Main three-column layout
        body = tk.Frame(self.root, bg="#10131c")
        body.pack(fill="both", expand=True, padx=16, pady=14)

        body.grid_columnconfigure(0, minsize=205)
        body.grid_columnconfigure(1, weight=1)
        body.grid_columnconfigure(2, minsize=230)
        body.grid_rowconfigure(0, weight=1)

        self.sidebar = tk.Frame(
            body, bg="#171c29", width=205
        )
        self.sidebar.grid(
            row=0, column=0, sticky="nsew", padx=(0, 12)
        )
        self.sidebar.grid_propagate(False)

        center = tk.Frame(body, bg="#10131c")
        center.grid(row=0, column=1, sticky="nsew")

        self.gallery_panel = tk.Frame(
            body, bg="#171c29", width=230
        )
        self.gallery_panel.grid(
            row=0, column=2, sticky="nsew", padx=(12, 0)
        )
        self.gallery_panel.grid_propagate(False)

        self.build_sidebar()
        self.build_workspace(center)
        self.build_gallery_panel()

        # Bottom status bar
        footer = tk.Frame(self.root, bg="#171c29", height=36)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Label(
            footer, textvariable=self.status_text,
            bg="#171c29", fg="#9daac2",
            font=("Segoe UI", 9)
        ).pack(side="left", padx=18, pady=7)

        tk.Label(
            footer, textvariable=self.hand_text,
            bg="#171c29", fg="#71dfb1",
            font=("Segoe UI", 9)
        ).pack(side="right", padx=18, pady=7)

    def section_label(self, parent, text):
        tk.Label(
            parent, text=text.upper(),
            font=("Segoe UI", 9, "bold"),
            bg="#171c29", fg="#8b9ab8"
        ).pack(anchor="w", padx=16, pady=(17, 9))

    def make_button(
        self, parent, text, command,
        bg="#252d40", fg="#f1f5ff"
    ):
        return tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, activebackground="#374561",
            activeforeground="#ffffff",
            relief="flat", bd=0, cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=10, pady=9
        )

    def build_sidebar(self):
        self.section_label(self.sidebar, "Drawing tools")

        self.draw_button = self.make_button(
            self.sidebar, "✎  Draw", self.enable_draw,
            bg="#315bd6"
        )
        self.draw_button.pack(fill="x", padx=12, pady=4)

        self.eraser_button = self.make_button(
            self.sidebar, "⌫  Eraser", self.enable_eraser
        )
        self.eraser_button.pack(fill="x", padx=12, pady=4)

        self.make_button(
            self.sidebar, "↺  Clear canvas",
            self.clear_canvas, bg="#603343"
        ).pack(fill="x", padx=12, pady=4)

        self.make_button(
            self.sidebar, "⬇  Save artwork",
            self.save_artwork, bg="#17694f"
        ).pack(fill="x", padx=12, pady=4)

        self.section_label(self.sidebar, "Brush size")

        tk.Label(
            self.sidebar, text="Adjust thickness",
            bg="#171c29", fg="#c2cbe0",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=14)

        self.brush_value_label = tk.Label(
            self.sidebar, text="8 px",
            bg="#171c29", fg="#8fb5ff",
            font=("Segoe UI", 12, "bold")
        )
        self.brush_value_label.pack(anchor="w", padx=14, pady=4)

        tk.Scale(
            self.sidebar, from_=2, to=35,
            orient="horizontal", variable=self.brush_size,
            command=self.update_brush_label,
            bg="#171c29", fg="#f1f5ff",
            troughcolor="#30394c", highlightthickness=0,
            activebackground="#6c92ff", length=170
        ).pack(padx=10, fill="x")

        self.section_label(self.sidebar, "Colour palette")

        palette = tk.Frame(self.sidebar, bg="#171c29")
        palette.pack(fill="x", padx=10)

        self.color_buttons = {}

        # BGR values converted to Tk hexadecimal colours
        for i, (name, bgr) in enumerate(COLORS.items()):
            r, g, b = bgr[2], bgr[1], bgr[0]
            hex_color = f"#{r:02x}{g:02x}{b:02x}"

            btn = tk.Button(
                palette, text=name,
                command=lambda n=name: self.select_color(n),
                bg=hex_color, fg="#111827",
                activebackground=hex_color,
                relief="flat", bd=0, cursor="hand2",
                font=("Segoe UI", 8, "bold"),
                width=8, pady=7
            )
            btn.grid(
                row=i // 2, column=i % 2,
                padx=3, pady=4, sticky="ew"
            )
            self.color_buttons[name] = btn

        palette.grid_columnconfigure(0, weight=1)
        palette.grid_columnconfigure(1, weight=1)
        self.update_color_buttons()

        self.section_label(self.sidebar, "Shortcuts")

        tk.Label(
            self.sidebar,
            text="S  Save artwork\n"
                 "C  Clear canvas\n"
                 "E  Eraser mode\n"
                 "D  Draw mode\n"
                 "Q  Exit application\n\n"
                 "Draw using your index\n"
                 "finger while keeping\n"
                 "your middle finger down.",
            justify="left",
            bg="#171c29", fg="#aab6ce",
            font=("Segoe UI", 9), lineSpacing=5
        ).pack(anchor="w", padx=16)

    def build_workspace(self, parent):
        top = tk.Frame(parent, bg="#10131c")
        top.pack(fill="x", pady=(0, 10))

        tk.Label(
            top, text="Painting workspace",
            bg="#10131c", fg="#f1f5ff",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left")

        tk.Label(
            top, textvariable=self.mode_text,
            bg="#233d36", fg="#84edbf",
            font=("Segoe UI", 9, "bold"),
            padx=10, pady=5
        ).pack(side="right")

        preview_card = tk.Frame(
            parent, bg="#080b12",
            highlightbackground="#30394c",
            highlightthickness=1
        )
        preview_card.pack(fill="both", expand=True)

        self.video_label = tk.Label(
            preview_card, bg="#080b12",
            text="Starting webcam...",
            fg="#aab6ce", font=("Segoe UI", 14)
        )
        self.video_label.pack(
            fill="both", expand=True, padx=4, pady=4
        )

        help_frame = tk.Frame(parent, bg="#10131c")
        help_frame.pack(fill="x", pady=(10, 0))

        tk.Label(
            help_frame,
            text="✋  Index finger up + middle finger down = draw",
            bg="#10131c", fg="#aab6ce",
            font=("Segoe UI", 10)
        ).pack(anchor="w")

        tk.Label(
            help_frame,
            text="Use the controls on the left to change tools.",
            bg="#10131c", fg="#73819c",
            font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(4, 0))

    def build_gallery_panel(self):
        tk.Label(
            self.gallery_panel, text="Artwork gallery",
            bg="#171c29", fg="#f1f5ff",
            font=("Segoe UI", 15, "bold")
        ).pack(anchor="w", padx=14, pady=(18, 4))

        tk.Label(
            self.gallery_panel,
            text="Your saved creations",
            bg="#171c29", fg="#8b9ab8",
            font=("Segoe UI", 9)
        ).pack(anchor="w", padx=14, pady=(0, 12))

        self.make_button(
            self.gallery_panel, "↻  Refresh gallery",
            self.refresh_gallery
        ).pack(fill="x", padx=12, pady=(0, 10))

        self.gallery_count = tk.Label(
            self.gallery_panel, text="0 artworks",
            bg="#171c29", fg="#8b9ab8",
            font=("Segoe UI", 9)
        )
        self.gallery_count.pack(anchor="w", padx=14, pady=4)

        self.gallery_list = tk.Frame(
            self.gallery_panel, bg="#171c29"
        )
        self.gallery_list.pack(
            fill="both", expand=True, padx=10, pady=8
        )

    # -----------------------------------------------------
    # CAMERA AND MEDIAPIPE
    # -----------------------------------------------------

    def start_camera(self):
        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            messagebox.showerror(
                "Camera error",
                "Could not open the webcam.\n"
                "Close other camera applications and try again."
            )
            self.status_text.set("Camera unavailable")
            return

        vision = mp.tasks.vision

        options = vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(MODEL_PATH)
            ),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.detector = vision.HandLandmarker.create_from_options(
            options
        )
        self.vision = vision
        self.status_text.set("Camera connected • Ready to paint")

    # -----------------------------------------------------
    # DRAWING TOOLS
    # -----------------------------------------------------

    def select_color(self, name):
        self.color_name = name
        self.eraser = False
        self.previous_point = None
        self.smooth_point = None
        self.update_color_buttons()
        self.update_mode()

    def update_color_buttons(self):
        for name, btn in self.color_buttons.items():
            if name == self.color_name and not self.eraser:
                btn.config(relief="solid", bd=3)
            else:
                btn.config(relief="flat", bd=0)

    def enable_draw(self):
        self.eraser = False
        self.previous_point = None
        self.update_mode()
        self.update_color_buttons()
        self.status_text.set("Draw mode enabled")

    def enable_eraser(self):
        self.eraser = True
        self.previous_point = None
        self.update_mode()
        self.update_color_buttons()
        self.status_text.set("Eraser mode enabled")

    def update_mode(self):
        if self.eraser:
            self.mode_text.set("ERASER MODE")
        else:
            self.mode_text.set(f"DRAW MODE • {self.color_name}")

    def update_brush_label(self, value):
        self.brush_value_label.config(
            text=f"{int(float(value))} px"
        )

    def clear_canvas(self):
        if messagebox.askyesno(
            "Clear canvas",
            "Clear the current drawing? Saved artwork will remain."
        ):
            self.canvas[:] = 0
            self.previous_point = None
            self.smooth_point = None
            self.status_text.set("Canvas cleared")

    def save_artwork(self):
        suggested_name = (
            f"artwork_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )

        filename = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save your artwork",
            initialdir=str(ARTWORKS_DIR),
            initialfile=suggested_name,
            defaultextension=".png",
            filetypes=[
                ("PNG image", "*.png"),
                ("JPEG image", "*.jpg"),
            ]
        )

        if not filename:
            return

        success = cv2.imwrite(filename, self.canvas)

        if success:
            self.status_text.set("Artwork saved successfully")
            self.refresh_gallery()
            messagebox.showinfo(
                "Saved",
                f"Your artwork has been saved:\n{filename}"
            )
        else:
            messagebox.showerror(
                "Save failed", "Could not save this artwork."
            )

    # -----------------------------------------------------
    # ARTWORK GALLERY
    # -----------------------------------------------------

    def refresh_gallery(self):
        if not hasattr(self, "gallery_list"):
            return

        for widget in self.gallery_list.winfo_children():
            widget.destroy()

        self.gallery_photos.clear()

        files = sorted(
            list(ARTWORKS_DIR.glob("*.png"))
            + list(ARTWORKS_DIR.glob("*.jpg"))
            + list(ARTWORKS_DIR.glob("*.jpeg")),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        self.gallery_count.config(
            text=f"{len(files)} artwork(s)"
        )

        if not files:
            tk.Label(
                self.gallery_list,
                text="No saved artwork yet.\n\n"
                     "Create a drawing and\nclick Save artwork.",
                bg="#171c29", fg="#8b9ab8",
                justify="center",
                font=("Segoe UI", 10)
            ).pack(pady=25)
            return

        for path in files[:30]:
            try:
                with Image.open(path) as img:
                    thumb = img.convert("RGB")
                    thumb.thumbnail((185, 100))
                    photo = ImageTk.PhotoImage(thumb)

                self.gallery_photos.append(photo)

                item = tk.Frame(
                    self.gallery_list,
                    bg="#222a3a",
                    highlightbackground="#354158",
                    highlightthickness=1
                )
                item.pack(fill="x", pady=5)

                image_label = tk.Label(
                    item, image=photo, bg="#080b12",
                    cursor="hand2"
                )
                image_label.pack(padx=5, pady=(5, 3))

                name_label = tk.Label(
                    item, text=path.name,
                    bg="#222a3a", fg="#e5ebf7",
                    font=("Segoe UI", 8),
                    wraplength=190
                )
                name_label.pack(padx=5, pady=(2, 6))

                for widget in (item, image_label, name_label):
                    widget.bind(
                        "<Button-1>",
                        lambda event, p=path: self.open_artwork(p)
                    )

            except Exception as exc:
                print(f"Could not load thumbnail {path}: {exc}")

    def open_artwork(self, path):
        if not messagebox.askyesno(
            "Open artwork",
            f"Load '{path.name}' onto the current canvas?\n"
            "This replaces the current unsaved drawing."
        ):
            return

        loaded = cv2.imread(str(path), cv2.IMREAD_COLOR)

        if loaded is None:
            messagebox.showerror(
                "Open failed", "Could not read this image."
            )
            return

        self.canvas = cv2.resize(
            loaded, (CANVAS_W, CANVAS_H)
        )
        self.previous_point = None
        self.smooth_point = None
        self.selected_artwork = path
        self.status_text.set(f"Opened {path.name}")

    # -----------------------------------------------------
    # LIVE CAMERA, HAND TRACKING AND DRAWING
    # -----------------------------------------------------

    def update_frame(self):
        if not self.running:
            return

        try:
            if self.camera is None or not self.camera.isOpened():
                self.root.after(100, self.update_frame)
                return

            success, frame = self.camera.read()

            if not success:
                self.status_text.set("Waiting for camera...")
                self.root.after(30, self.update_frame)
                return

            frame = cv2.flip(frame, 1)
            frame = cv2.resize(frame, (CANVAS_W, CANVAS_H))

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb
            )

            timestamp_ms = self.frame_number * 33
            self.frame_number += 1

            result = self.detector.detect_for_video(
                mp_image, timestamp_ms
            )

            drawing_now = False
            tip = None

            if result.hand_landmarks:
                hand = result.hand_landmarks[0]

                raw_tip = (
                    int(hand[8].x * CANVAS_W),
                    int(hand[8].y * CANVAS_H)
                )

                index_up = hand[8].y < hand[6].y
                middle_up = hand[12].y < hand[10].y
                drawing_now = index_up and not middle_up

                if self.smooth_point is None:
                    self.smooth_point = raw_tip
                else:
                    self.smooth_point = (
                        int(
                            SMOOTHING * raw_tip[0]
                            + (1 - SMOOTHING) * self.smooth_point[0]
                        ),
                        int(
                            SMOOTHING * raw_tip[1]
                            + (1 - SMOOTHING) * self.smooth_point[1]
                        )
                    )

                tip = self.smooth_point
                # Hand skeleton
                points = [
                    (int(p.x * CANVAS_W), int(p.y * CANVAS_H))
                    for p in hand
                ]

                connections = [
                    (0, 1), (1, 2), (2, 3), (3, 4),
                    (0, 5), (5, 6), (6, 7), (7, 8),
                    (5, 9), (9, 10), (10, 11), (11, 12),
                    (9, 13), (13, 14), (14, 15), (15, 16),
                    (13, 17), (17, 18), (18, 19), (19, 20),
                    (0, 17)
                ]

                for start, end in connections:
                    cv2.line(
                        frame, points[start], points[end],
                        (60, 220, 100), 2, cv2.LINE_AA
                    )

                if drawing_now:
                    if self.previous_point is not None:
                        color = ((0, 0, 0) if self.eraser
                            else COLORS[self.color_name]
                        )
                        thickness = (
                            40 if self.eraser
                            else int(self.brush_size.get())
                        )

                        cv2.line(
                            self.canvas,
                            self.previous_point, tip,
                            color, thickness, cv2.LINE_AA
                        )
                        cv2.circle(
                            self.canvas, tip,
                            max(1, thickness // 2),
                            color, -1, cv2.LINE_AA
                        )
                        self.previous_point = tip
                    self.hand_text.set("Hand: detected • Drawing")
                else:
                    self.previous_point = None
                    self.hand_text.set("Hand: detected • Ready")

                cv2.circle(
                    frame, tip, 10,
                    (0, 0, 255) if drawing_now else (255, 180, 0),
                    -1, cv2.LINE_AA
                )

            else:
                self.previous_point = None
                self.smooth_point = None
                self.hand_text.set("Hand: not detected")
                gray = cv2.cvtColor(
                self.canvas, cv2.COLOR_BGR2GRAY
            )
            _, mask = cv2.threshold(
                gray, 1, 255, cv2.THRESH_BINARY
            )
            inverse_mask = cv2.bitwise_not(mask)

            background = cv2.bitwise_and(
                frame, frame, mask=inverse_mask
            )
            artwork = cv2.bitwise_and(
                self.canvas, self.canvas, mask=mask
            )
            display = cv2.add(background, artwork)

            # Convert for Tkinter
            display = cv2.resize(
                display, (PREVIEW_W, PREVIEW_H)
            )
            display = cv2.cvtColor(
                display, cv2.COLOR_BGR2RGB)
            photo = ImageTk.PhotoImage(
                Image.fromarray(display)
            )

            self.current_photo = photo
            self.video_label.config(image=photo, text="")

        except Exception as exc:
            self.status_text.set(f"Application error: {exc}")
            print("Frame update error:", exc)

        if self.running:
            self.root.after(15, self.update_frame)

    # -----------------------------------------------------
    # KEYBOARD SHORTCUTS AND SHUTDOWN
    #
    def on_key(self, event):
        key = event.char.lower()

        if key == "s":
            self.save_artwork()
        elif key == "c":
            self.clear_canvas()
        elif key == "e":
            self.enable_eraser()
        elif key == "d":
            self.enable_draw()
        elif key == "q":
            self.close()
        elif key in "123456":
            names = list(COLORS.keys())
            self.select_color(names[int(key) - 1])

    def close(self):
        if not self.running:
            return

        self.running = False

        try:
            if self.camera is not None:
                self.camera.release()

            if self.detector is not None:
                self.detector.close()

        except Exception as exc:
            print("Shutdown warning:", exc)

        self.root.destroy()



        
    