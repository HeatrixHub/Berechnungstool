import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from .tab4_isolierungen_logic import (
    get_all_insulations,
    load_insulation,
    save_insulation,
    delete_insulation,
    interpolate_k
)
from tabs.scrollable import ScrollableFrame  # Importiere die ScrollableFrame-Klasse

class IsolierungenTab:
    def __init__(self, notebook):
        # Erstelle einen Container für das Notebook
        container = ttk.Frame(notebook)
        notebook.add(container, text="Isolierungen")
        # Verwende einen ScrollableFrame im Container
        self.scrollable = ScrollableFrame(container)
        self.scrollable.pack(fill="both", expand=True)
        # Baue die UI im inneren Frame des ScrollableFrame auf
        self.frame = self.scrollable.inner
        self.build_ui()

    # ---------------------------------------------------------------
    # GUI-Aufbau
    # ---------------------------------------------------------------
    def build_ui(self):
        self.frame.rowconfigure(4, weight=1)
        self.frame.columnconfigure(0, weight=1)
        # --- Tabelle
        columns = ("name", "classification_temp", "density")
        self.tree = ttk.Treeview(
            self.frame, columns=columns, show="headings", height=10, selectmode="browse"
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("classification_temp", text="Klass.-Temp [°C]")
        self.tree.heading("density", text="Dichte [kg/m³]")
        for c in columns:
            self.tree.column(c, anchor="center", width=150)
        self.tree.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=10, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        ttk.Button(self.frame, text="Neu", command=self.new_entry).grid(row=1, column=0, sticky="ew", padx=10)
        ttk.Button(self.frame, text="Bearbeiten", command=self.edit_entry).grid(row=1, column=1, sticky="ew")
        ttk.Button(self.frame, text="Löschen", command=self.delete_entry).grid(row=1, column=2, sticky="ew", padx=10)
        # --- Eingabeformular
        form = ttk.LabelFrame(self.frame, text="Isolierung bearbeiten/erstellen")
        form.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        ttk.Label(form, text="Name:").grid(row=0, column=0, sticky="w")
        self.entry_name = ttk.Entry(form)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(form, text="Klass.-Temp [°C]:").grid(row=1, column=0, sticky="w")
        self.entry_class_temp = ttk.Entry(form)
        self.entry_class_temp.grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Label(form, text="Dichte [kg/m³]:").grid(row=2, column=0, sticky="w")
        self.entry_density = ttk.Entry(form)
        self.entry_density.grid(row=2, column=1, sticky="ew", padx=5)
        ttk.Label(form, text="Temperaturen [°C]:").grid(row=3, column=0, sticky="w")
        self.entry_temps = ttk.Entry(form)
        self.entry_temps.grid(row=3, column=1, sticky="ew", padx=5)
        ttk.Label(form, text="Wärmeleitfähigkeiten [W/mK]:").grid(row=4, column=0, sticky="w")
        self.entry_ks = ttk.Entry(form)
        self.entry_ks.grid(row=4, column=1, sticky="ew", padx=5)
        ttk.Button(form, text="💾 Speichern", command=self.save_entry).grid(row=5, column=1, columnspan=2, pady=5)
        # --- Plotbereich
        self.plot_frame = ttk.LabelFrame(self.frame, text="Interpolierte Wärmeleitfähigkeit")
        self.plot_frame.grid(row=3, column=0, columnspan=3, sticky="nsew", padx=10, pady=10)
        self.frame.rowconfigure(3, weight=1)
        self.refresh_table()

    # ---------------------------------------------------------------
    # Datenhandling
    # ---------------------------------------------------------------
    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        for ins in get_all_insulations():
            self.tree.insert("", "end", values=(ins["name"], ins["classification_temp"], ins["density"]))

    def new_entry(self):
        self.clear_fields()

    def edit_entry(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte eine Isolierung auswählen.")
            return
        name = self.tree.item(selection[0])["values"][0]
        data = load_insulation(name)
        if not data:
            return
        self.entry_name.delete(0, tk.END)
        self.entry_name.insert(0, data["name"])
        self.entry_class_temp.delete(0, tk.END)
        self.entry_class_temp.insert(0, str(data["classification_temp"]))
        self.entry_density.delete(0, tk.END)
        self.entry_density.insert(0, str(data["density"]))
        self.entry_temps.delete(0, tk.END)
        self.entry_temps.insert(0, ", ".join(map(str, data["temps"])))
        self.entry_ks.delete(0, tk.END)
        self.entry_ks.insert(0, ", ".join(map(str, data["ks"])))
        self.update_plot(data["temps"], data["ks"], data["classification_temp"])

    def save_entry(self):
        try:
            name = self.entry_name.get().strip()
            if not name:
                messagebox.showwarning("Fehler", "Name darf nicht leer sein.")
                return
            class_temp = float(self.entry_class_temp.get())
            density = float(self.entry_density.get())
            temps = [float(x.strip()) for x in self.entry_temps.get().split(",") if x.strip()]
            ks = [float(x.strip()) for x in self.entry_ks.get().split(",") if x.strip()]
            if len(temps) != len(ks):
                messagebox.showerror("Fehler", "Temperatur- und k-Werte müssen gleich viele Einträge haben.")
                return
            save_insulation(name, class_temp, density, temps, ks)
            messagebox.showinfo("Gespeichert", f"Isolierung '{name}' wurde gespeichert.")
            self.refresh_table()
        except Exception as e:
            messagebox.showerror("Fehler", str(e))

    def delete_entry(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Hinweis", "Bitte eine Isolierung auswählen.")
            return
        name = self.tree.item(selection[0])["values"][0]
        if messagebox.askyesno("Löschen", f"Soll '{name}' wirklich gelöscht werden?"):
            delete_insulation(name)
            self.refresh_table()
            self.clear_fields()

    def on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        name = self.tree.item(selection[0])["values"][0]
        data = load_insulation(name)
        if data:
            self.update_plot(data["temps"], data["ks"], data["classification_temp"])

    def clear_fields(self):
        for entry in [self.entry_name, self.entry_class_temp, self.entry_density, self.entry_temps, self.entry_ks]:
            entry.delete(0, tk.END)

    # ---------------------------------------------------------------
    # Plot
    # ---------------------------------------------------------------
    def update_plot(self, temps, ks, class_temp):
        """Zeichnet den interpolierten k(T)-Plot."""
        try:
            x = np.linspace(20, class_temp, 100)
            y = interpolate_k(temps, ks, x)
            plt.close("all")
            fig, ax = plt.subplots(figsize=(6, 4), dpi=100)
            ax.plot(x, y, linewidth=2, label="Interpoliert")
            ax.scatter(temps, ks, color="red", zorder=5, label="Messpunkte")
            ax.set_xlabel("Temperatur [°C]")
            ax.set_ylabel("Wärmeleitfähigkeit [W/mK]")
            ax.set_title("Wärmeleitfähigkeit über Temperatur")
            ax.legend()
            ax.grid(True, linestyle="--", alpha=0.6)
            for widget in self.plot_frame.winfo_children():
                widget.destroy()
            canvas = FigureCanvasTkAgg(fig, master=self.plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="both", expand=True)
        except Exception as e:
            messagebox.showerror("Fehler beim Plotten", str(e))