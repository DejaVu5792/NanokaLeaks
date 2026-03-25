import webbrowser
import threading
import customtkinter as ctk
from PIL import Image
import io
import requests
import sys
import os

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
    GAMES,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class NanokaViewer(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Nanoka Viewer")
        self.geometry("900x650")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tabs = {}
        for game, info in GAMES.items():
            self.tabs[game] = self.tabview.add(info["name"])

        self.game_frames = {}
        self.game_data = {}

        for game in GAMES.keys():
            frame = ctk.CTkScrollableFrame(self.tabs[game])
            frame.pack(fill="both", expand=True, padx=10, pady=10)
            self.game_frames[game] = frame

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.refresh_btn = ctk.CTkButton(
            button_frame,
            text="Refresh",
            command=self.load_data,
        )
        self.refresh_btn.pack(side="left", padx=5)

        self.status_label = ctk.CTkLabel(button_frame, text="Ready")
        self.status_label.pack(side="left", padx=5)

        self.load_data()

    def load_data(self):
        self.refresh_btn.configure(state="disabled")
        self.status_label.configure(text="Loading...")

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
                    text="No characters found",
                )
                label.pack(pady=20)
                continue

            row = 0
            col = 0
            max_cols = 3

            for char_id, char_data in chars:
                card = self.create_card(game, char_id, char_data)
                card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

            self.game_frames[game].columnconfigure(list(range(max_cols)), weight=1)

        self.refresh_btn.configure(state="normal")
        self.status_label.configure(text="Loaded")

    def create_card(self, game, char_id, char_data):
        card = ctk.CTkFrame(self.game_frames[game], width=250, height=300)
        card.grid_propagate(False)

        name = get_name(game, char_data)
        rarity = get_rarity(game, char_data)
        element = get_element(game, char_data)
        url = get_character_url(game, char_id, char_data)

        rarity_colors = {
            "S": "#FF6B6B",
            "5": "#FFD700",
            "4": "#9370DB",
            "A": "#FF6B6B",
        }
        color = rarity_colors.get(str(rarity), "#FFFFFF")

        name_label = ctk.CTkLabel(
            card,
            text=name,
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        name_label.pack(pady=(10, 5))

        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(pady=5)

        rarity_label = ctk.CTkLabel(
            info_frame,
            text=f"{rarity}★",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=color,
        )
        rarity_label.pack(side="left", padx=10)

        element_label = ctk.CTkLabel(
            info_frame,
            text=element,
            font=ctk.CTkFont(size=12),
        )
        element_label.pack(side="left", padx=10)

        open_btn = ctk.CTkButton(
            card,
            text="View Page",
            command=lambda: webbrowser.open(url),
        )
        open_btn.pack(pady=10)

        return card


def main():
    app = NanokaViewer()
    app.mainloop()


if __name__ == "__main__":
    main()
