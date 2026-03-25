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
        self.geometry("950x750")

        self.main_frame = ctk.CTkScrollableFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.header_frame = ctk.CTkFrame(self.main_frame)
        self.header_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            self.header_frame,
            text="Nanoka Viewer",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left", padx=10)

        button_frame = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        button_frame.pack(side="right", padx=10)

        self.refresh_btn = ctk.CTkButton(
            button_frame,
            text="Refresh",
            command=self.load_data,
            width=80,
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.clear_cache_btn = ctk.CTkButton(
            button_frame,
            text="Clear Cache",
            command=self._on_clear_cache,
            fg_color="#444",
            width=80,
        )
        self.clear_cache_btn.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(button_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)

        self.game_sections = {}
        self.game_data = {}

        for game, info in GAMES.items():
            section = self._create_game_section(game, info["name"])
            self.game_sections[game] = section

        self.load_data()

    def _create_game_section(self, game, title):
        section = ctk.CTkFrame(self.main_frame)
        section.pack(fill="x", pady=(0, 15))

        header = ctk.CTkFrame(section)
        header.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        self.game_data[game] = {"chars": [], "loading": True}

        loading = ctk.CTkLabel(
            header,
            text="Loading...",
            font=ctk.CTkFont(size=12),
        )
        loading.pack(side="right", padx=10)
        self.game_data[game]["loading_label"] = loading

        chars_frame = ctk.CTkFrame(section, fg_color="transparent")
        chars_frame.pack(fill="x", padx=10, pady=(0, 10))
        self.game_data[game]["frame"] = chars_frame

        return section

    def load_data(self):
        self.refresh_btn.configure(state="disabled")
        self.status_label.configure(text="Loading...")

        for game in GAMES.keys():
            self.game_data[game]["loading"] = True
            if "loading_label" in self.game_data[game]:
                self.game_data[game]["loading_label"].configure(text="Loading...")

        thread = threading.Thread(target=self._load_data_thread)
        thread.start()

    def _load_data_thread(self):
        for game in GAMES.keys():
            try:
                chars = get_newest_characters(game, count=6)
                self.game_data[game]["chars"] = chars
            except Exception as e:
                self.game_data[game]["chars"] = []
                print(f"Error loading {game}: {e}")

        self.after(0, self._update_ui)

    def _update_ui(self):
        for game, info in self.game_data.items():
            chars = info["chars"]
            frame = info["frame"]

            for widget in frame.winfo_children():
                widget.destroy()

            if not chars:
                ctk.CTkLabel(
                    frame,
                    text="Failed to load characters",
                ).pack()
                continue

            count_released = sum(1 for _, c in chars if is_released_char(game, c))

            info["loading_label"].configure(
                text=f"{len(chars)} chars ({count_released} released)"
            )

            for char_id, char_data in chars:
                card = self._create_card(frame, game, char_id, char_data)
                card.pack(side="left", padx=8, pady=8)

        self.refresh_btn.configure(state="normal")
        self.status_label.configure(
            text=f"Loaded at {datetime.now().strftime('%H:%M:%S')}"
        )

    def _create_card(self, parent, game, char_id, char_data):
        card = ctk.CTkFrame(parent, width=260, height=300)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)
        released = is_released_char(game, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        char_img = load_image(char_img_url, (100, 100))
        element_img = load_image(element_img_url, (20, 20))
        specialty_img = load_image(specialty_img_url, (20, 20))

        if char_img:
            ctk.CTkLabel(card, image=char_img, text="").pack(pady=(10, 5))
        else:
            ctk.CTkLabel(card, text="[No Image]", height=100).pack(pady=(10, 5))

        if not released:
            ctk.CTkLabel(
                card,
                text="UNRELEASED",
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#FF6B6B",
            ).pack(pady=(5, 0))

        ctk.CTkLabel(
            card,
            text=name,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(pady=(5, 0))

        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        color = rarity_colors.get(str(rarity), "#FFFFFF")

        ctk.CTkLabel(
            card,
            text=f"{rarity}★",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=color,
        ).pack()

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(pady=5)

        if element_img:
            lbl = ctk.CTkLabel(info_frame, image=element_img, text="")
            lbl.image = element_img
        else:
            lbl = ctk.CTkLabel(info_frame, text=element, font=ctk.CTkFont(size=11))
        lbl.pack(side="left", padx=8)

        if specialty_img:
            lbl = ctk.CTkLabel(info_frame, image=specialty_img, text="")
            lbl.image = specialty_img
            lbl.pack(side="left", padx=8)

        ctk.CTkButton(
            card,
            text="View Page",
            command=lambda u=url: webbrowser.open(u),
            width=100,
            height=28,
        ).pack(pady=5)

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
