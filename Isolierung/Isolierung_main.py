# Isolierung_main.py
import sys
import os
import tkinter as tk
from tkinter import ttk
import sv_ttk

# Tabs
from tabs.tab1_berechnung_ui import BerechnungTab
from tabs.tab2_projekte_ui import ProjekteTab
from tabs.tab3_bericht_ui import BerichtTab
from tabs.tab4_isolierungen_ui import IsolierungenTab


class IsolierungApp:
    """Hauptklasse der Anwendung"""
    def __init__(self):
        # Fenster
        self.root = tk.Tk()
        self.root.title("Heatrix IsoSim v1.0")
        self.root.geometry("1200x800")
        self.root.minsize(1000, 700)

        # Dynamischer Icon-Pfad (für .exe und Entwicklung)
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS  # Pfad zur temporären EXE-Datei
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))  # Pfad zum Skript

        # Versuche, das .ico-Icon zu laden
        icon_ico_path = os.path.join(base_path, "logo-min.ico")
        if os.path.exists(icon_ico_path):
            try:
                self.root.iconbitmap(icon_ico_path)
            except Exception as e:
                print(f"Fehler beim Laden des .ico-Icons: {e}")

        # Fallback: Versuche, das .png-Icon zu laden
        icon_png_path = os.path.join(base_path, "logo_min.png")
        if os.path.exists(icon_png_path):
            try:
                icon = tk.PhotoImage(file=icon_png_path)
                self.root.iconphoto(True, icon)  # True = für alle Fenster
            except Exception as e:
                print(f"Fehler beim Laden des .png-Icons: {e}")
        else:
            print(f"⚠ Icon nicht gefunden unter {icon_ico_path} oder {icon_png_path}")

        # Styling / Theme
        try:
            sv_ttk.set_theme("dark")
        except Exception:
            print("Hinweis: sv_ttk konnte nicht geladen werden. Standard-Theme wird verwendet.")

        # Kopfbereich
        header = ttk.Frame(self.root, padding=(10, 8))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Heatrix Isolierungsberechnung",
            font=("Segoe UI", 16, "bold")
        ).pack(side="left", padx=5)
        ttk.Label(
            header,
            text="Version 1.0",
            font=("Segoe UI", 9)
        ).pack(side="right")

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # Tab-Instanzen erzeugen (jetzt als Attribute)
        try:
            self.berechnung_tab = BerechnungTab(self.notebook)
            self.projekte_tab = ProjekteTab(self.notebook, berechnung_tab=self.berechnung_tab)
            self.bericht_tab = BerichtTab(self.notebook)
            self.isolierungen_tab = IsolierungenTab(self.notebook)
        except Exception as e:
            import traceback
            print("Fehler beim Erstellen der Tabs:")
            traceback.print_exc()

        # Automatische Aktualisierung bei Tab-Wechsel
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # Fußzeile
        footer = ttk.Frame(self.root, padding=(10, 5))
        footer.pack(fill="x", side="bottom")
        ttk.Label(footer, text="© 2025 Heatrix GmbH", font=("Segoe UI", 9)).pack(side="left")
        ttk.Button(footer, text="🌓 Theme wechseln", command=self.toggle_theme).pack(side="right")

    # ---------------------------------------------------------------
    # Tab-Wechsel → automatische Aktualisierung
    # ---------------------------------------------------------------
    def on_tab_changed(self, event):
        """Aktualisiert automatisch Tab 2 und 3, wenn sie geöffnet werden."""
        selected_tab = event.widget.nametowidget(event.widget.select())

        try:
            # Tab 2 (Projekte)
            if hasattr(self, "projekte_tab") and selected_tab == self.projekte_tab.scrollable.master:
                self.projekte_tab.refresh_projects()
                print("[Auto-Update] Tab 2 (Projekte) aktualisiert.")

            # Tab 3 (Bericht)
            elif hasattr(self, "bericht_tab") and selected_tab == self.bericht_tab.scrollable.master:
                self.bericht_tab.refresh_project_list()
                print("[Auto-Update] Tab 3 (Bericht) aktualisiert.")

        except Exception as e:
            import traceback
            print("[Auto-Update] Fehler beim Aktualisieren eines Tabs:")
            traceback.print_exc()

    # ---------------------------------------------------------------
    # Theme-Umschaltung
    # ---------------------------------------------------------------
    def toggle_theme(self):
        if sv_ttk.get_theme() == "light":
            sv_ttk.use_dark_theme()
        else:
            sv_ttk.use_light_theme()

        # Aktualisiere Farben in allen Tabs (falls vorhanden)
        if hasattr(self, "berechnung_tab"):
            self.berechnung_tab.update_theme_colors()
        if hasattr(self, "projekte_tab"):
            if hasattr(self.projekte_tab, "update_theme_colors"):
                self.projekte_tab.update_theme_colors()
        if hasattr(self, "bericht_tab"):
            if hasattr(self.bericht_tab, "update_theme_colors"):
                self.bericht_tab.update_theme_colors()

    # ---------------------------------------------------------------
    # Programmstart
    # ---------------------------------------------------------------
    def run(self):
        self.root.mainloop()


def main():
    try:
        app = IsolierungApp()
        app.run()
    except Exception as e:
        import traceback
        print("FEHLER beim Programmstart:")
        traceback.print_exc()
        input("\nDrücke Enter zum Schließen...")


if __name__ == "__main__":
    main()