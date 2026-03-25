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
        self.configure(fg_color="#1a1a1a")

        # Header
        header = ctk.CTkFrame(self, fg_color="#1a1a1a")
        header.pack(fill="x", padx=10, pady=(10, 0))

        ctk.CTkLabel(
            header,
            text="Nanoka Viewer",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(side="left", pady=10)

        self.refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            command=self.load_data,
            width=80,
        )
        self.refresh_btn.pack(side="right", pady=10, padx=(0, 10))

        self.status_label = ctk.CTkLabel(header, text="Ready")
        self.status_label.pack(side="right", pady=10)

        # Main scrollable frame (vertical)
        self.main_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="#1a1a1a",
            scrollbar_button_color="#333333",
        )
        self.main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.game_data = {}

        for game, info in GAMES.items():
            self.game_data[game] = {"chars": [], "loading": True}
            self._create_game_section(game, info["name"])

        self.load_data()

    def _create_game_section(self, game, title):
        section = ctk.CTkFrame(self.main_frame, fg_color="#1a1a1a")
        section.pack(fill="x", pady=(0, 8))

        header = ctk.CTkFrame(section, fg_color="#252525")
        header.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=10, pady=8)

        loading_label = ctk.CTkLabel(
            header,
            text="Loading...",
            font=ctk.CTkFont(size=12),
        )
        loading_label.pack(side="right", padx=10)
        self.game_data[game]["loading_label"] = loading_label

        # Cards container
        cards_container = ctk.CTkFrame(section, fg_color="#1a1a1a")
        cards_container.pack(fill="x", expand=True, padx=5, pady=(0, 4))

        # Use native CTkScrollableFrame instead of Canvas for seamless horizontal scrolling
        card_frame = ctk.CTkScrollableFrame(
            cards_container,
            orientation="horizontal",
            fg_color="#1a1a1a",
            height=260,
            scrollbar_button_color="#333333"
        )
        card_frame.pack(fill="x", expand=True)

        self.game_data[game]["canvas"] = None
        self.game_data[game]["card_frame"] = card_frame
        self.game_data[game]["section"] = section

    def load_data(self):
        self.refresh_btn.configure(state="disabled")
        self.status_label.configure(text="Loading...")

        for game in GAMES.keys():
            self.game_data[game]["loading"] = True
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
            card_frame = info["card_frame"]

            for widget in card_frame.winfo_children():
                widget.destroy()

            if not chars:
                ctk.CTkLabel(
                    card_frame,
                    text="Failed to load characters",
                    fg_color="#1a1a1a",
                ).pack()
                continue

            count_released = sum(1 for _, c in chars if is_released_char(game, c))

            info["loading_label"].configure(
                text=f"{len(chars)} chars ({count_released} released)"
            )

            for char_id, char_data in chars:
                card = self._create_card(card_frame, game, char_id, char_data)
                card.pack(side="left", padx=4, pady=4)

        self.refresh_btn.configure(state="normal")
        self.status_label.configure(
            text=f"Loaded at {datetime.now().strftime('%H:%M:%S')}"
        )

    def _create_card(self, parent, game, char_id, char_data):
        card = ctk.CTkFrame(parent, fg_color="#252525", width=180, height=240)

        # FIX 1: Force exact card dimensions for the scrollable canvas.
        # By packing a dummy frame of the exact size, the canvas natively
        # reserves this 180x240 space and prevents the background from collapsing.
        dummy = ctk.CTkFrame(card, width=180, height=240, fg_color="#252525")
        dummy.pack()
        card.pack_propagate(False)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)
        released = is_released_char(game, char_data)

        char_img_url = get_character_image(game, char_data, char_id)
        element_img_url = get_element_image(game, char_data)
        specialty_img_url = get_specialty_image(game, char_data)

        char_img = load_image(char_img_url, (80, 80))
        element_img = load_image(element_img_url, (18, 18))
        specialty_img = load_image(specialty_img_url, (18, 18))

        # FIX 2: Replaced fg_color="transparent" with "#252525"
        # Transparent frames inside scrollable canvases cause severe smearing.
        img_container = ctk.CTkFrame(card, fg_color="#252525")
        img_container.place(x=50, y=8)

        if char_img:
            ctk.CTkLabel(
                img_container, image=char_img, text="", fg_color="#252525"
            ).pack()
        else:
            ctk.CTkLabel(
                img_container, text="[No Img]", width=80, height=80, fg_color="#252525"
            ).pack()

        # Element and specialty below image
        icons_frame = ctk.CTkFrame(img_container, fg_color="#252525")
        icons_frame.pack(pady=(2, 0))

        if element_img:
            lbl = ctk.CTkLabel(
                icons_frame, image=element_img, text="", fg_color="#252525"
            )
            lbl.image = element_img
        else:
            lbl = ctk.CTkLabel(
                icons_frame,
                text=element[:3] if element else "N/A",
                font=ctk.CTkFont(size=9),
                fg_color="#252525",
            )
        lbl.pack(side="left", padx=2)

        if specialty_img:
            lbl = ctk.CTkLabel(
                icons_frame, image=specialty_img, text="", fg_color="#252525"
            )
            lbl.image = specialty_img
            lbl.pack(side="left", padx=2)

        # Rarity badge (top right)
        rarity_colors = {"S": "#FF6B6B", "5": "#FFD700", "4": "#9370DB", "A": "#FF6B6B"}
        color = rarity_colors.get(str(rarity), "#FFFFFF")
        ctk.CTkLabel(
            card,
            text=f"{rarity}★",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=color,
            fg_color="#252525",
        ).place(x=165, y=5, anchor="ne")

        # Unreleased badge (top left)
        if not released:
            ctk.CTkLabel(
                card,
                text="NEW",
                font=ctk.CTkFont(size=8, weight="bold"),
                text_color="#FF6B6B",
                fg_color="#252525",
            ).place(x=5, y=5)

        # Name (centered below image)
        ctk.CTkLabel(
            card,
            text=name[:12] + ("..." if len(name) > 12 else ""),
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#252525",
        ).place(x=90, y=130, anchor="n")

        # View Page button
        ctk.CTkButton(
            card,
            text="View",
            command=lambda u=url: webbrowser.open(u),
            width=60,
            height=20,
            font=ctk.CTkFont(size=10),
        ).place(x=90, y=155, anchor="n")

        return card

def main():
    app = NanokaViewer()
    app.mainloop()


if __name__ == "__main__":
    main()
