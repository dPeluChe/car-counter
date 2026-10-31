import tkinter as tk
from tkinter import messagebox, ttk

from carcounter.access_routes import zone_role_errors


def edit_access_roles(app):
    if not app.zones:
        messagebox.showinfo("Accesos", "Dibuja primero las zonas de entrada y salida.")
        return
    app._stop_zone_preview()
    dialog = tk.Toplevel(app)
    dialog.title("Entradas y salidas por acceso")
    dialog.geometry("620x440")
    dialog.transient(app)
    tk.Label(dialog, text="Usa polígonos distintos para entrada y salida.\n"
                         "El mismo acceso en ambos permite contar retornos.").pack(pady=10)
    controls = tk.Frame(dialog)
    controls.pack(side="bottom", fill="x", pady=10)
    canvas = tk.Canvas(dialog, highlightthickness=0)
    scrollbar = tk.Scrollbar(dialog, command=canvas.yview)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(fill="both", expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    body = tk.Frame(canvas)
    window = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
    values = {}
    labels = {"entry": "Entrada", "exit": "Salida"}
    for name in app.zones:
        saved = getattr(app, "zone_roles", {}).get(name, {})
        row = tk.Frame(body)
        row.pack(fill="x", padx=10, pady=4)
        tk.Label(row, text=name, width=20, anchor="w").pack(side="left")
        role = tk.StringVar(value=labels.get(saved.get("role"), ""))
        access = tk.StringVar(value=saved.get("access", name))
        ttk.Combobox(row, textvariable=role, values=list(labels.values()),
                     state="readonly", width=10).pack(side="left", padx=6)
        ttk.Entry(row, textvariable=access).pack(side="left", fill="x", expand=True)
        values[name] = (role, access)

    def save():
        reverse = {value: key for key, value in labels.items()}
        roles = {name: dict(role=reverse.get(role.get()), access=access.get().strip())
                 for name, (role, access) in values.items()}
        errors = zone_role_errors(app.zones, roles)
        if errors:
            messagebox.showwarning("Accesos incompletos", "\n".join(errors), parent=dialog)
            return
        app.zone_roles = roles
        app.status_var.set("Accesos definidos: solo entrada confirmada y salida confirmada completan una ruta.")
        dialog.destroy()

    def clear():
        app.zone_roles = {}
        app.status_var.set("Modo de zonas libre: cualquier zona distinta puede ser destino.")
        dialog.destroy()

    tk.Button(controls, text="Cancelar", command=dialog.destroy).pack(side="left", padx=10)
    tk.Button(controls, text="Usar zonas sin roles", command=clear).pack(side="left")
    tk.Button(controls, text="Aplicar accesos", command=save).pack(side="right", padx=10)
    dialog.grab_set()
