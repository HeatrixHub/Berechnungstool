# tabs/tab2_projekte_ui.py
import tkinter as tk
from tkinter import ttk, messagebox
import sv_ttk
from .scrollable import ScrollableFrame
from .tab2_projekte_logic import list_projects, get_project_details, remove_project


class ProjekteTab:
    def __init__(self, notebook, berechnung_tab=None):
        """
        berechnung_tab: reference to the BerechnungTab instance so we can load projects into Tab1
        """
        self.berechnung_tab = berechnung_tab

        container = ttk.Frame(notebook)
        notebook.add(container, text="Projekte")

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)

        self.frame = self.scrollable.inner
        self.project_overview: list[dict] = []
        self.build_ui()

    # ---------------------------------------------------------------
    # UI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.rowconfigure(1, weight=1)
        self.frame.columnconfigure(0, weight=1)

        ttk.Label(
            self.frame, text="Gespeicherte Projekte", font=("Segoe UI", 12, "bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        # --- Treeview für Projekte ---
        columns = ("name", "layers", "T_left", "T_inf", "h", "updated_at")
        self.tree = ttk.Treeview(
            self.frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=12,
        )
        self.tree.heading("name", text="Projektname")
        self.tree.heading("layers", text="Schichten")
        self.tree.heading("T_left", text="T_links [°C]")
        self.tree.heading("T_inf", text="T_∞ [°C]")
        self.tree.heading("h", text="h [W/m²K]")
        self.tree.heading("updated_at", text="Zuletzt aktualisiert")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("layers", width=80, anchor="center")
        self.tree.column("T_left", width=80, anchor="center")
        self.tree.column("T_inf", width=80, anchor="center")
        self.tree.column("h", width=80, anchor="center")
        self.tree.column("updated_at", width=160, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_project_select)

        scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=1, column=1, sticky="ns")

        # --- Buttons ---
        btn_frame = ttk.Frame(self.frame)
        btn_frame.grid(row=2, column=0, pady=8, sticky="ew", padx=10)
        ttk.Button(
            btn_frame,
            text="🔄 Aktualisieren",
            command=self.refresh_projects,
            style="Neutral.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame,
            text="📄 Laden in Tab 1",
            command=self.load_selected_into_tab1,
            style="Warning.TButton",
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(
            btn_frame,
            text="🗑️ Löschen",
            command=self.delete_selected_project,
            style="Danger.TButton",
        ).pack(side=tk.LEFT, padx=5)

        # --- Projektdetails ---
        ttk.Label(self.frame, text="Projektdetails", font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, sticky="w", padx=10, pady=(10, 0)
        )

        self.details_text = tk.Text(
            self.frame,
            height=10,
            wrap="word",
            relief="flat",
            borderwidth=0,
        )
        self.details_text.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

        self.refresh_projects()
        self.update_theme_colors()  # einmal initial aufrufen

    # ---------------------------------------------------------------
    # Theme-Anpassung (Farben)
    # ---------------------------------------------------------------
    def update_theme_colors(self):
        """Passt Textfarben im Detailfeld an das aktuelle sv_ttk-Theme an."""
        theme = sv_ttk.get_theme()
        if theme == "dark":
            bg_color = "#2D2D2D"
            fg_color = "white"
        else:
            bg_color = "#f9f9f9"
            fg_color = "black"

        self.details_text.config(bg=bg_color, fg=fg_color)

    # ---------------------------------------------------------------
    # Projektdaten anzeigen
    # ---------------------------------------------------------------
    def refresh_projects(self):
        self.tree.delete(*self.tree.get_children())
        self.project_overview = list_projects()
        for project in self.project_overview:
            self.tree.insert(
                "",
                "end",
                values=(
                    project.get("name"),
                    project.get("layer_count", 0),
                    project.get("T_left"),
                    project.get("T_inf"),
                    project.get("h"),
                    project.get("updated_at"),
                ),
            )
        self.update_theme_colors()

    def on_project_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0])
        name = item["values"][0]
        project = get_project_details(name)
        if project:
            self.display_project_details(project)

    def display_project_details(self, project):
        self.details_text.delete("1.0", tk.END)
        self.update_theme_colors()  # falls Theme gewechselt wurde
        try:
            lines = [
                f"Projektname: {project.name}",
                f"Anzahl Schichten: {len(project.thicknesses)}",
                f"Dicken [mm]: {', '.join(map(str, project.thicknesses))}",
                f"Materialien: {', '.join(project.isolierungen) if hasattr(project, 'isolierungen') else '-'}",
                f"T_links [°C]: {project.T_left}",
                f"T_∞ [°C]: {project.T_inf}",
                f"h [W/m²K]: {project.h}",
                f"Erstellt am: {project.created_at or '-'}",
                f"Zuletzt aktualisiert: {project.updated_at or '-'}",
            ]
            if project.result:
                lines.append("\n--- Ergebnis ---")
                lines.append(f"Wärmestromdichte q: {project.result.get('q', 0):.3f} W/m²")
                lines.append(f"Gesamtwiderstand: {project.result.get('R_total', 0):.5f} m²K/W")
                temps = project.result.get("interface_temperatures", [])
                lines.append("Grenzflächentemperaturen: " + ", ".join([f"{t:.2f}" for t in temps]))
            self.details_text.insert(tk.END, "\n".join(lines))
        except Exception as e:
            self.details_text.insert(tk.END, f"Fehler beim Anzeigen: {e}")

    # ---------------------------------------------------------------
    # Projekt laden / löschen
    # ---------------------------------------------------------------
    def load_selected_into_tab1(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte ein Projekt auswählen.")
            return
        item = self.tree.item(selection[0])
        name = item["values"][0]
        project = get_project_details(name)
        if not project:
            messagebox.showerror("Fehler", "Projekt konnte nicht geladen werden.")
            return

        if self.berechnung_tab:
            self.berechnung_tab.load_project_into_ui(project)
        else:
            messagebox.showwarning("Nicht verbunden", "Berechnung-Tab nicht verfügbar (interner Fehler).")

    def delete_selected_project(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte ein Projekt auswählen.")
            return
        item = self.tree.item(selection[0])
        name = item["values"][0]
        if messagebox.askyesno("Löschen bestätigen", f"Soll das Projekt '{name}' wirklich gelöscht werden?"):
            if remove_project(name):
                messagebox.showinfo("Erfolg", f"Projekt '{name}' wurde gelöscht.")
                self.refresh_projects()
                self.details_text.delete("1.0", tk.END)
                if self.berechnung_tab:
                    try:
                        current_name = self.berechnung_tab.entry_project_name.get().strip()
                        if current_name == name:
                            self.berechnung_tab.entry_project_name.delete(0, tk.END)
                    except Exception:
                        pass
            else:
                messagebox.showerror("Fehler", "Projekt konnte nicht gelöscht werden.")