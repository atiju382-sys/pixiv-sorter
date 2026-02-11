import customtkinter as ctk
import threading
import sys
import os
import time
from pixiv_sorter import run_sorter

# Set appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class PixivSorterGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Pixiv Sorter - Desktop GUI")
        self.geometry("1000x650")

        # Configure grid layout (1x2)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create sidebar frame with widgets
        self.sidebar_frame = ctk.CTkFrame(self, width=300, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(9, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="Pixiv Sorter", font=ctk.CTkFont(size=24, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        # Search Term
        self.search_label = ctk.CTkLabel(self.sidebar_frame, text="Search Term:", anchor="w")
        self.search_label.grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.search_entry = ctk.CTkEntry(self.sidebar_frame, placeholder_text="e.g. アズールレーン")
        self.search_entry.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Threshold
        self.threshold_label = ctk.CTkLabel(self.sidebar_frame, text="Likes Threshold:", anchor="w")
        self.threshold_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")
        self.threshold_entry = ctk.CTkEntry(self.sidebar_frame)
        self.threshold_entry.insert(0, "1000")
        self.threshold_entry.grid(row=4, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Pages & Start Page
        self.pages_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.pages_frame.grid(row=5, column=0, padx=20, pady=10, sticky="ew")
        self.pages_frame.grid_columnconfigure((0, 1), weight=1)

        self.pages_label = ctk.CTkLabel(self.pages_frame, text="Pages:", anchor="w")
        self.pages_label.grid(row=0, column=0, padx=(0, 5), sticky="w")
        self.pages_entry = ctk.CTkEntry(self.pages_frame)
        self.pages_entry.insert(0, "5")
        self.pages_entry.grid(row=1, column=0, padx=(0, 5), sticky="ew")

        self.start_page_label = ctk.CTkLabel(self.pages_frame, text="Start Page:", anchor="w")
        self.start_page_label.grid(row=0, column=1, padx=(5, 0), sticky="w")
        self.start_page_entry = ctk.CTkEntry(self.pages_frame)
        self.start_page_entry.insert(0, "1")
        self.start_page_entry.grid(row=1, column=1, padx=(5, 0), sticky="ew")

        # Switches
        self.r18_switch = ctk.CTkSwitch(self.sidebar_frame, text="Include R-18")
        self.r18_switch.grid(row=6, column=0, padx=20, pady=10, sticky="w")

        self.no_limit_switch = ctk.CTkSwitch(self.sidebar_frame, text="No Page Limit")
        self.no_limit_switch.grid(row=7, column=0, padx=20, pady=10, sticky="w")

        self.auto_download_switch = ctk.CTkSwitch(self.sidebar_frame, text="Auto-Download Images", progress_color="green")
        self.auto_download_switch.grid(row=8, column=0, padx=20, pady=10, sticky="w")

        # Delay
        self.delay_label = ctk.CTkLabel(self.sidebar_frame, text="Delay (seconds): 2.5", anchor="w")
        self.delay_label.grid(row=9, column=0, padx=20, pady=(10, 0), sticky="w")
        self.delay_slider = ctk.CTkSlider(self.sidebar_frame, from_=0.5, to=10, number_of_steps=19, command=self.update_delay_label)
        self.delay_slider.set(2.5)
        self.delay_slider.grid(row=10, column=0, padx=20, pady=(0, 10), sticky="ew")

        # Action Buttons
        self.run_button = ctk.CTkButton(self.sidebar_frame, text="Run Search", font=ctk.CTkFont(weight="bold"), command=self.start_search)
        self.run_button.grid(row=11, column=0, padx=20, pady=10)

        self.clear_button = ctk.CTkButton(self.sidebar_frame, text="Clear Logs", fg_color="transparent", border_width=1, command=self.clear_logs)
        self.clear_button.grid(row=12, column=0, padx=20, pady=(0, 20))

        # Main logging area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.console_label = ctk.CTkLabel(self.main_frame, text="Output Console", font=ctk.CTkFont(size=16, weight="bold"))
        self.console_label.grid(row=0, column=0, padx=20, pady=(10, 5), sticky="w")

        self.log_textbox = ctk.CTkTextbox(self.main_frame, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_textbox.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        self.is_running = False

    def update_delay_label(self, value):
        self.delay_label.configure(text=f"Delay (seconds): {value:.1f}")

    def clear_logs(self):
        self.log_textbox.delete("1.0", "end")

    def log(self, message):
        # Thread-safe logging
        self.after(0, lambda: self._do_log(message))

    def _do_log(self, message):
        self.log_textbox.insert("end", str(message) + "\n")
        self.log_textbox.see("end")

    def start_search(self):
        if self.is_running:
            return

        search_term = self.search_entry.get().strip()
        if not search_term:
            self.log("[!] Error: Search term is empty.")
            return

        try:
            threshold = int(self.threshold_entry.get())
            pages = int(self.pages_entry.get())
            start_page = int(self.start_page_entry.get())
        except ValueError:
            self.log("[!] Error: Threshold, Pages, and Start Page must be numbers.")
            return

        delay = self.delay_slider.get()
        r18 = self.r18_switch.get() == 1
        no_limit = self.no_limit_switch.get() == 1
        auto_download = self.auto_download_switch.get() == 1

        self.is_running = True
        self.run_button.configure(state="disabled", text="Running...")
        
        # Start in background thread
        thread = threading.Thread(target=self.run_task, args=(search_term, threshold, pages, r18, delay, start_page, no_limit, auto_download))
        thread.daemon = True
        thread.start()

    def run_task(self, search_term, threshold, pages, r18, delay, start_page, no_limit, auto_download):
        try:
            run_sorter(
                search_term=search_term,
                threshold=threshold,
                pages=pages,
                r18=r18,
                delay=delay,
                start_page=start_page,
                no_limit=no_limit,
                auto_download=auto_download,
                logger=self.log
            )
        except Exception as e:
            self.log(f"[!] Critical Error: {e}")
        finally:
            self.is_running = False
            self.after(0, lambda: self.run_button.configure(state="normal", text="Run Search"))

if __name__ == "__main__":
    app = PixivSorterGUI()
    app.mainloop()
