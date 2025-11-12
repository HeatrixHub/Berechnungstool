import sys
import os
import tkinter as tk
from tkinter import ttk
import sv_ttk  # <<— Modernes Windows-Theme
import tab1_GUI as tab1
import tab2_GUI as tab2
import tab3_GUI as tab3
# import tab4


def main():
    root = tk.Tk()
    root.title("Berechnungstool Heatrix GmbH")

    # Dynamischer Icon-Pfad
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    icon_filename = "logo-min.ico"
    icon_path = os.path.join(base_path, icon_filename)

    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print(f"⚠ Icon '{icon_filename}' nicht gefunden unter {icon_path}")

    icon_png = os.path.join(base_path, "logo-min.png")
    if os.path.exists(icon_png):
        icon = tk.PhotoImage(file=icon_png)
        root.iconphoto(True, icon)

    # Fenstergröße
    initial_width = 1150
    initial_height = 610
    root.geometry(f"{initial_width}x{initial_height}")
    root.minsize(initial_width, initial_height)

    # === Stil ===
    style = ttk.Style()

    # Fonts anpassen (sv_ttk übernimmt Farb- und Theme-Design)
    style.configure("Standard.TEntry", foreground="black")
    style.configure("Fehler.TEntry", foreground="red")
    style.configure("TLabel", font=("Arial", 12))
    style.configure("TButton", font=("Arial", 12))
    style.configure("TEntry", font=("Arial", 12))
    style.configure("TCheckbutton", font=("Arial", 12))
    style.configure("TCombobox", font=("Arial", 12))
    style.configure("TNotebook.Tab", font=("Arial", 12))

    root.option_add("*TCombobox*Font", "Arial 12")
    root.option_add("*TEntry*Font", "Arial 12")
    root.option_add("*TCheckbutton*Font", "Arial 12")

    style.map("TEntry", font=[("readonly", ("Arial", 12))])
    style.map("TCombobox", font=[("readonly", ("Arial", 12))])

    # === sv_ttk aktivieren ===
    sv_ttk.use_dark_theme()  # Standardmäßig Dunkelmodus (alternativ use_light_theme())

    # === Hauptbereich ===
    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)

    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill="both", expand=True, padx=20, pady=(10, 20))

    frame_zustand = tab1.create_tab1(notebook)
    notebook.add(frame_zustand, text="Zustandsgrößen")

    frame_geschwindigkeit = tab2.create_tab2(notebook)
    notebook.add(frame_geschwindigkeit, text="v Inlet")

    def get_thermal_power_from_tab1():
        try:
            eintraege = tab1.get_entries()  # Zugriff auf entries via Getter
            return float(eintraege["Wärmeleistung (kW):"].get())
        except (ValueError, KeyError):
            return None

    frame_heizer = tab3.create_tab3(notebook, get_thermal_power_from_tab1)
    notebook.add(frame_heizer, text="Heizer Leistung")

    # frame_druckverlust = tab4.create_tab4(notebook)
    # notebook.add(frame_druckverlust, text="Druckverlust Rohrbogen")

    # === Fußleiste ===
    footer = tk.Frame(root, height=25)
    footer.pack(fill="x", side="bottom")

    version_label = tk.Label(footer, text="v2.0", anchor="w", font=("Arial", 10))
    version_label.pack(side="left", padx=10)

    author_label = tk.Label(footer, text="© 2025 Heatrix GmbH", anchor="e", font=("Arial", 10))
    author_label.pack(side="right", padx=10)

    # === Theme-Wechsel ===
    def toggle_theme():
        current = sv_ttk.get_theme()
        if current == "dark":
            sv_ttk.use_light_theme()
            theme_button.config(text="🌙 Dunkelmodus")
        else:
            sv_ttk.use_dark_theme()
            theme_button.config(text="☀ Hellmodus")

    theme_button = ttk.Button(
        footer, text="☀ Hellmodus", command=toggle_theme
    )
    theme_button.pack(side="right", padx=10)

    root.mainloop()


if __name__ == "__main__":
    main()