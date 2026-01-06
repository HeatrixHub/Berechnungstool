# gui_utils.py
import tkinter as tk

def zeige_fehlermeldung(entry):
    """Markiert das Eingabefeld rot und zeigt 'Bitte eintragen!' an"""
    entry.config(foreground="red")
    entry.delete(0, 'end')
    entry.insert(0, "Bitte eintragen!")

    def loesche_bei_fokus(event):
        if entry.get() == "Bitte eintragen!":
            entry.delete(0, 'end')
            entry.config(foreground="black")

    entry.bind("<FocusIn>", loesche_bei_fokus)


def check_eingabe(entry):
    """Liefert Eingabetext oder None bei leerem Feld"""
    wert = entry.get().strip()
    if not wert or wert == "Bitte eintragen!":
        zeige_fehlermeldung(entry)
        return None
    return wert


def check_float(entry):
    """Liefert Float-Wert oder None + Fehleranzeige"""
    wert = check_eingabe(entry)
    if wert is None:
        return None
    try:
        return float(wert)
    except ValueError:
        zeige_fehlermeldung(entry)
        return None


def set_entry_value(entry, value, readonly=False):
    """Schreibt einen Wert in ein Entry-Feld und setzt zurück auf Standardfarbe"""
    entry.config(state="normal", foreground="black")
    entry.delete(0, 'end')
    entry.insert(0, f"{value:.5e}" if abs(value) < 0.001 else f"{value:.5f}")
    if readonly:
        entry.config(state="readonly")



class ToolTip:
    def __init__(self, widget, text, delay=3000):
        self.widget = widget
        self.text = text
        self.delay = delay  # Millisekunden
        self.tip_window = None
        self.after_id = None

        widget.bind("<Enter>", self.schedule_tip)
        widget.bind("<Leave>", self.cancel_tip)

    def schedule_tip(self, event=None):
        self.after_id = self.widget.after(self.delay, self.show_tip)

    def cancel_tip(self, event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hide_tip()

    def show_tip(self):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", 9, "normal"),
            justify='left',
            wraplength=250
        )
        label.pack(ipadx=1)

    def hide_tip(self):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
