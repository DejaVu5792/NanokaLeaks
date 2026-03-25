import webbrowser
import threading
import customtkinter as ctk
from PIL import Image
import io
import requests
import sys
import os
from datetime import datetime

if __name__ == "__main__":
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)

from nanoka_viewer.api import (
    get_newest_characters,
    get_character_url,
    get_rarity,
    get_element,
    get_name,
    get_character_image,
    get_element_image,
    get_specialty_image,
    is_released_char,
    clear_cache,
    GAMES,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

IMAGE_CACHE = {}
CHAR_IMAGE_CACHE = {}


def load_image(url, size=(100, 100)):
    if not url or url in IMAGE_CACHE:
        return IMAGE_CACHE.get(url)

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            img_data = response.content
            img = Image.open(io.BytesIO(img_data))
            img = img.resize(size, Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            IMAGE_CACHE[url] = ctk_img
            return ctk_img
    except Exception:
        pass
    return None


class NanokaViewer(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Nanoka Viewer")
        self.geometry("950x700")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tabs = {}
        for game, info in GAMES.items():
            self.tabs[game] = self.tabview.add(info["name"])

        self.game_frames = {}
        self.game_data = {}
        self.loading_labels = {}

        for game in GAMES.keys():
            frame = ctk.CTkFrame(self.tabs[game])
            frame.pack(fill="both", expand=True, padx=10, pady=10)
            self.game_frames[game] = frame

            loading = ctk.CTkLabel(frame, text="Loading...", font=ctk.CTkFont(size=14))
            loading.pack(pady=20)
            self.loading_labels[game] = loading

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.refresh_btn = ctk.CTkButton(
            button_frame,
            text="Refresh",
            command=self.load_data,
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.clear_cache_btn = ctk.CTkButton(
            button_frame,
            text="Clear Cache",
            command=self._on_clear_cache,
            fg_color="#444",
        )
        self.clear_cache_btn.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(button_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)

        self.load_data()

    def load_data(self):
        self.refresh_btn.configure(state="disabled")
        self.status_label.configure(text="Loading...")

        for game in GAMES.keys():
            if self.loading_labels[game]:
                self.loading_labels[game].configure(text="Loading...")
                self.loading_labels[game].pack(pady=20)

        thread = threading.Thread(target=self._load_data_thread)
        thread.start()

    def _load_data_thread(self):
        for game in GAMES.keys():
            try:
                chars = get_newest_characters(game, count=6)
                self.game_data[game] = chars
            except Exception as e:
                self.game_data[game] = []
                print(f"Error loading {game}: {e}")

        self.after(0, self._update_ui)

    def _update_ui(self):
        for game, chars in self.game_data.items():
            for widget in self.game_frames[game].winfo_children():
                widget.destroy()

            if not chars:
                label = ctk.CTkLabel(
                    self.game_frames[game],
                    text="Failed to load characters",
                )
                label.pack(pady=20)
                continue

            count_released = sum(1 for _, c in chars if is_released_char(game, c))

            header = ctk.CTkFrame(self.game_frames[game], fg_color="transparent")
            header.pack(fill="x", pady=(0, 10))

            ctk.CTkLabel(
                header,
                text=f"Showing {len(chars)} characters ({count_released} released)",
                font=ctk.CTkFont(size=12),
            ).pack(side="left")

            cards_frame = ctk.CTkFrame(self.game_frames[game], fg_color="transparent")
            cards_frame.pack(fill="both", expand=True, pady=10)

            cols_per_row = 3
            for i, (char_id, char_data) in enumerate(chars):
                card = self.create_card(game, char_id, char_data)
                card.pack(in_=cards_frame, side="left", padx=10, pady=10)

        self.refresh_btn.configure(state="normal")
        self.status_label.configure(
            text=f"Loaded at {datetime.now().strftime('%H:%M:%S')}"
        )

    def create_card(self, game, char_id, char_data):
        card = ctk.CTkFrame(self.game_frames[game], width=280, height=340)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)
        released = is_released_char(game, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        char_img = load_image(char_img_url, (120, 120))
        element_img = load_image(element_img_url, (24, 24))
        specialty_img = load_image(specialty_img_url, (24, 24))

        if char_img:
            img_label = ctk.CTkLabel(card, image=char_img, text="")
            img_label.pack(pady=(10, 5))
        else:
            img_label = ctk.CTkLabel(card, text="[No Image]", height=120)
            img_label.pack(pady=(10, 5))

        if not released:
            unreleased_badge = ctk.CTkLabel(
                card,
                text="UNRELEASED",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color="#FF6B6B",
            )
            unreleased_badge.pack(pady=(5, 0))

        name_label = ctk.CTkLabel(
            card,
            text=name,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        name_label.pack(pady=(5, 5))

        rarity_colors = {
            "S": "#FF6B6B",
            "5": "#FFD700",
            "4": "#9370DB",
            "A": "#FF6B6B",
        }
        color = rarity_colors.get(str(rarity), "#FFFFFF")

        rarity_label = ctk.CTkLabel(
            card,
            text=f"{rarity}★",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color,
        )
        rarity_label.pack()

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(pady=5)

        if element_img:
            element_label = ctk.CTkLabel(info_frame, image=element_img, text="")
            element_label.image = element_img
        else:
            element_label = ctk.CTkLabel(
                info_frame,
                text=element,
                font=ctk.CTkFont(size=12),
            )
        element_label.pack(side="left", padx=10)

        if specialty_img:
            specialty_label = ctk.CTkLabel(info_frame, image=specialty_img, text="")
            specialty_label.image = specialty_img
            specialty_label.pack(side="left", padx=10)

        open_btn = ctk.CTkButton(
            card,
            text="View Page",
            command=lambda: webbrowser.open(url),
            width=120,
        )
        open_btn.pack(pady=10)

        return card

    def _on_clear_cache(self):
        clear_cache()
        IMAGE_CACHE.clear()
        self.status_label.configure(text="Cache cleared")
        self.load_data()


def main():
    app = NanokaViewer()
    app.mainloop()


if __name__ == "__main__":
    main()
