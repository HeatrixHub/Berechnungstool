# tabs/tab3_bericht_ui.py
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.colors import LinearSegmentedColormap
import sv_ttk

from ..core.database import get_all_project_names, load_project
from .tab3_bericht_logic import build_report_content, export_to_pdf, export_to_docx
from .scrollable import ScrollableFrame


class BerichtTab:
    def __init__(self, notebook):
        container = ttk.Frame(notebook)
        notebook.add(container, text="Bericht")

        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)
        self.frame = self.scrollable.inner

        self.build_ui()

        # Theme-Listener
        self.frame.bind("<<ThemeChanged>>", lambda e: self._apply_theme_colors())

    # ---------------------------------------------------------------
    # GUI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.columnconfigure(0, weight=1)
        self.frame.rowconfigure(7, weight=1)

        ttk.Label(self.frame, text="Projekt auswählen:").grid(row=0, column=0, sticky="w", padx=10, pady=(10, 2))
        self.project_combo = ttk.Combobox(self.frame, values=get_all_project_names(), state="readonly")
        self.project_combo.grid(row=0, column=1, sticky="ew", padx=10, pady=(10, 2))
        ttk.Button(self.frame, text="Laden", command=self.load_project).grid(row=0, column=2, padx=5, pady=(10, 2))
        ttk.Button(self.frame, text="🔄 Aktualisieren", command=self.refresh_project_list).grid(row=0, column=3, padx=5, pady=(10, 2))

        # Autor & Kommentar
        ttk.Label(self.frame, text="Autor:").grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.entry_author = ttk.Entry(self.frame, width=30)
        self.entry_author.grid(row=1, column=1, sticky="ew", padx=10, pady=2)

        ttk.Label(self.frame, text="Kommentar:").grid(row=2, column=0, sticky="nw", padx=10, pady=2)
        self.text_comment = tk.Text(self.frame, height=4, wrap="word", relief="flat", borderwidth=0)
        self.text_comment.grid(row=2, column=1, columnspan=3, sticky="ew", padx=10, pady=2)

        # Berichtsvorschau
        ttk.Label(self.frame, text="Berichtsvorschau", font=("Segoe UI", 11, "bold")).grid(
            row=3, column=0, sticky="w", padx=10, pady=(10, 0)
        )

        self.summary_frame = ttk.LabelFrame(self.frame, text="Ergebnisse")
        self.summary_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", padx=10, pady=5)

        # Plot-Vorschau
        self.plot_frame = ttk.LabelFrame(self.frame, text="Temperaturverlauf (Vorschau)")
        self.plot_frame.grid(row=5, column=0, columnspan=4, sticky="nsew", padx=10, pady=5)

        # Buttons
        btn_frame = ttk.Frame(self.frame)
        btn_frame.grid(row=6, column=0, columnspan=4, pady=10)
        ttk.Button(btn_frame, text="🖨️ Bericht aktualisieren", command=self.update_preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📄 Exportieren (PDF/DOCX)", command=self.export_report).pack(side=tk.LEFT, padx=5)

        # Initial Themefarben anwenden
        self._apply_theme_colors()

    # ---------------------------------------------------------------
    # Theme & Styling
    # ---------------------------------------------------------------
    def _apply_theme_colors(self):
        """Setzt Farben für Textfelder und Tabellen gemäß sv_ttk-Theme."""
        theme = sv_ttk.get_theme()
        if theme == "dark":
            bg_color = "#2D2D2D"
            fg_color = "white"
        else:
            bg_color = "#f9f9f9"
            fg_color = "black"

        # Kommentarbox
        self.text_comment.config(bg=bg_color, fg=fg_color, insertbackground=fg_color)

        # Treeview-Stil aktualisieren
        self._apply_treeview_style(theme)

    def _apply_treeview_style(self, theme):
        style = ttk.Style()
        if theme == "dark":
            style.configure("Treeview",
                            background="#2b2b2b",
                            fieldbackground="#2b2b2b",
                            foreground="white",
                            rowheight=22)
            style.configure("Treeview.Heading",
                            background="#3a3a3a",
                            foreground="white",
                            font=("Segoe UI", 9, "bold"))
        else:
            style.configure("Treeview",
                            background="white",
                            fieldbackground="white",
                            foreground="black",
                            rowheight=22)
            style.configure("Treeview.Heading",
                            background="#f0f0f0",
                            foreground="black",
                            font=("Segoe UI", 9, "bold"))

    # ---------------------------------------------------------------
    # Projekt laden & Vorschau
    # ---------------------------------------------------------------
    def refresh_project_list(self):
        names = get_all_project_names()
        self.project_combo["values"] = names
        if names:
            self.project_combo.current(0)

    def load_project(self):
        name = self.project_combo.get()
        if not name:
            messagebox.showinfo("Hinweis", "Bitte ein Projekt auswählen.")
            return
        project = load_project(name)
        if not project:
            messagebox.showerror("Fehler", "Projekt konnte nicht geladen werden.")
            return
        self.current_project = project
        self.update_preview()

    def update_preview(self):
        if not hasattr(self, "current_project") or not self.current_project:
            messagebox.showwarning("Fehler", "Kein Projekt geladen.")
            return

        self._apply_theme_colors()

        author = self.entry_author.get().strip()
        comment = self.text_comment.get("1.0", tk.END).strip()
        project_dict = self.current_project.__dict__

        report_text = build_report_content(project_dict, author, comment)
        for widget in self.summary_frame.winfo_children():
            widget.destroy()

        result = project_dict.get("result", {})
        if not result:
            ttk.Label(self.summary_frame, text="Keine Berechnungsergebnisse verfügbar.").pack()
            return

        # Kopfbereich
        ttk.Label(self.summary_frame, text=f"Wärmestromdichte q = {result.get('q', 0):.3f} W/m²").grid(row=0, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(self.summary_frame, text=f"Gesamtwiderstand R_total = {result.get('R_total', 0):.5f} m²K/W").grid(row=1, column=0, sticky="w", padx=6, pady=2)
        ttk.Label(self.summary_frame, text=f"Iteration: {result.get('iterations', '–')}").grid(row=2, column=0, sticky="w", padx=6, pady=2)

        ttk.Label(self.summary_frame, text="Temperaturen und Materialeigenschaften pro Schicht:").grid(row=3, column=0, sticky="w", padx=6, pady=(8, 2))

        # Tabelle
        cols = ("schicht", "material", "dicke", "T_links", "T_rechts", "T_mittel", "k_mittel")
        headers = ["Schicht", "Material", "Dicke [mm]",
                   "T_links [°C]", "T_rechts [°C]",
                   "T_mittel [°C]", "k_mittel [W/mK]"]
        widths = [70, 160, 90, 110, 110, 110, 130]

        theme = sv_ttk.get_theme()
        self._apply_treeview_style(theme)

        tree = ttk.Treeview(self.summary_frame, columns=cols, show="headings", height=8, style="Treeview")
        tree.grid(row=4, column=0, columnspan=3, sticky="nsew", padx=6, pady=4)
        for c, h, w in zip(cols, headers, widths):
            tree.heading(c, text=h)
            tree.column(c, anchor="center", width=w)

        # Inhalte
        T_if = result.get("interface_temperatures", [])
        T_avg = result.get("T_avg", [])
        k_avg = result.get("k_final", [])
        isolierungen = project_dict.get("isolierungen", [])
        thicknesses = project_dict.get("thicknesses", [])
        n_layers = len(T_if) - 1

        for i in range(n_layers):
            iso_name = isolierungen[i] if i < len(isolierungen) else f"Schicht {i+1}"
            thick = thicknesses[i] if i < len(thicknesses) else 0.0
            T_l = T_if[i]
            T_r = T_if[i + 1]
            T_m = T_avg[i] if i < len(T_avg) else (T_l + T_r) / 2
            k_m = k_avg[i] if i < len(k_avg) else 0.0
            tree.insert("", "end", values=(f"{i+1}", iso_name, f"{thick:.2f}",
                                           f"{T_l:.2f}", f"{T_r:.2f}",
                                           f"{T_m:.2f}", f"{k_m:.4f}"))

        scroll = ttk.Scrollbar(self.summary_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=4, column=3, sticky="ns")

        self._draw_plot(self.current_project.thicknesses, T_if, isolierungen)

    # ---------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------
    def _draw_plot(self, thicknesses, temperatures, isolierungen):
        theme = sv_ttk.get_theme()
        plot_bg_color = '#1e1e1e' if theme == "dark" else '#fefefe'
        fg_color = 'white' if theme == "dark" else 'black'
        colors = ["#e81919", "#fce6e6"]
        cmap = LinearSegmentedColormap.from_list("custom_cmap", colors, N=256)

        plt.close("all")
        fig, ax = plt.subplots(figsize=(8, 5), dpi=100, facecolor=plot_bg_color)
        ax.set_facecolor(plot_bg_color)

        total_x = [0]
        for t in thicknesses:
            total_x.append(total_x[-1] + t)

        ax.plot(total_x, temperatures, linewidth=2, marker="o", color=fg_color)
        x_pos = 0
        for i, t in enumerate(thicknesses):
            color_value = i / (len(thicknesses) - 1) if len(thicknesses) > 1 else 0.5
            color = cmap(color_value)
            ax.axvspan(x_pos, x_pos + t, color=color, alpha=0.4)
            x_pos += t

        ax.set_xlabel("Dicke [mm]", color=fg_color)
        ax.set_ylabel("Temperatur [°C]", color=fg_color)
        ax.set_title("Temperaturverlauf durch die Isolierung", fontsize=10, color=fg_color)
        ax.grid(True, linestyle="--", alpha=0.6, color='gray')
        ax.tick_params(axis='x', colors=fg_color)
        ax.tick_params(axis='y', colors=fg_color)

        for widget in self.plot_frame.winfo_children():
            widget.destroy()
        canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    # ---------------------------------------------------------------
    # Export (unverändert)
    # ---------------------------------------------------------------
    def export_report(self):
        if not hasattr(self, "current_project") or not self.current_project:
            messagebox.showwarning("Hinweis", "Bitte zuerst ein Projekt laden.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF-Datei", "*.pdf"), ("Word-Datei", "*.docx")],
            title="Bericht speichern unter"
        )
        if not file_path:
            return

        author = self.entry_author.get().strip()
        comment = self.text_comment.get("1.0", tk.END).strip()
        project_dict = self.current_project.__dict__
        report_text = build_report_content(project_dict, author, comment)

        # Temporären Plot speichern
        img_path = os.path.join(os.getcwd(), "temp_plot.png")
        try:
            fig, ax = plt.subplots(figsize=(8, 5))
            colors = ["#e81919", "#fce6e6"]
            cmap = LinearSegmentedColormap.from_list("custom_cmap", colors, N=256)
            total_x = [0]
            for t in self.current_project.thicknesses:
                total_x.append(total_x[-1] + t)
            temps = self.current_project.result.get("interface_temperatures", [])
            ax.plot(total_x, temps, linewidth=2, marker="o")
            x_pos = 0
            for i, t in enumerate(self.current_project.thicknesses):
                color_value = i / (len(self.current_project.thicknesses) - 1) if len(self.current_project.thicknesses) > 1 else 0.5
                color = cmap(color_value)
                ax.axvspan(x_pos, x_pos + t, color=color, alpha=0.4)
                x_pos += t
            ax.set_xlabel("Dicke [mm]")
            ax.set_ylabel("Temperatur [°C]")
            ax.grid(True, linestyle="--", alpha=0.6)
            fig.savefig(img_path, dpi=200, bbox_inches="tight")
            plt.close(fig)
        except Exception:
            img_path = None

        try:
            if file_path.lower().endswith(".pdf"):
                export_to_pdf(file_path, report_text, self.current_project.name, project_dict, img_path)
            elif file_path.lower().endswith(".docx"):
                export_to_docx(file_path, report_text, self.current_project.name, project_dict, img_path)
            else:
                raise ValueError("Ungültiges Dateiformat.")
            if os.path.exists(file_path):
                messagebox.showinfo("Erfolg", f"Bericht erfolgreich exportiert:\n{file_path}")
        except Exception as e:
            import traceback
            messagebox.showerror("Fehler beim Export", traceback.format_exc())
        finally:
            if img_path and os.path.exists(img_path):
                os.remove(img_path)