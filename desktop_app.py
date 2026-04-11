import tkinter as tk
from tkinter import ttk, messagebox

from app.config_loader import ConfigLoader
from app.settings_manager import SettingsManager
from app.providers.provider_admin import ProviderAdmin
from app.adaptive.quick_access_admin import QuickAccessAdmin


PROVIDER_TYPE_LABELS = {
    "web_search": "Веб-поиск",
    "youtube_search": "YouTube поисковик",
    "music_search": "Поиск музыки"
}

TARGET_TYPE_LABELS = {
    "app": "Приложение",
    "file": "Файл",
    "folder": "Папка",
    "url": "Ссылка"
}


class AssistantDesktopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Настройки локального ассистента")
        self.root.geometry("980x700")

        self.loader = ConfigLoader()
        self.config = self.loader.get()
        self.settings = SettingsManager()
        self.provider_admin = ProviderAdmin()
        self.quick_admin = QuickAccessAdmin()

        self._build_ui()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.general_tab = ttk.Frame(notebook)
        self.voice_tab = ttk.Frame(notebook)
        self.paths_tab = ttk.Frame(notebook)
        self.providers_tab = ttk.Frame(notebook)
        self.quick_tab = ttk.Frame(notebook)

        notebook.add(self.general_tab, text="Общие")
        notebook.add(self.voice_tab, text="Голос")
        notebook.add(self.paths_tab, text="Обязательные папки")
        notebook.add(self.providers_tab, text="Провайдеры")
        notebook.add(self.quick_tab, text="Быстрые цели")

        self._build_general_tab()
        self._build_voice_tab()
        self._build_paths_tab()
        self._build_providers_tab()
        self._build_quick_tab()

    def _build_general_tab(self):
        frm = self.general_tab

        ttk.Label(frm, text="Провайдер музыки по умолчанию:").pack(anchor="w", padx=12, pady=(12, 4))
        self.music_provider_var = tk.StringVar(value=self.settings.get("default_music_provider", "yandex_music"))
        providers = self.config["providers"]["supported_music_providers"]
        self.music_provider_combo = ttk.Combobox(frm, textvariable=self.music_provider_var, values=providers, state="readonly")
        self.music_provider_combo.pack(fill="x", padx=12)

        ttk.Label(frm, text="Провайдер веб-поиска по умолчанию:").pack(anchor="w", padx=12, pady=(12, 4))
        self.web_provider_var = tk.StringVar(value=self.settings.get("default_web_search_provider", "browser_google"))
        self.web_provider_combo = ttk.Combobox(frm, textvariable=self.web_provider_var, values=["browser_google"], state="readonly")
        self.web_provider_combo.pack(fill="x", padx=12)

        ttk.Label(frm, text="Провайдер YouTube поиска по умолчанию:").pack(anchor="w", padx=12, pady=(12, 4))
        self.youtube_provider_var = tk.StringVar(value=self.settings.get("default_youtube_provider", "youtube_search"))
        self.youtube_provider_combo = ttk.Combobox(frm, textvariable=self.youtube_provider_var, values=["youtube_search"], state="readonly")
        self.youtube_provider_combo.pack(fill="x", padx=12)

        ttk.Button(frm, text="Сохранить общие настройки", command=self.save_general).pack(anchor="e", padx=12, pady=16)

    def _build_voice_tab(self):
        frm = self.voice_tab

        voice_conf = self.config["voice"]

        self.voice_enabled_var = tk.BooleanVar(value=voice_conf.get("enabled", True))
        ttk.Checkbutton(frm, text="Включить голосовые ответы", variable=self.voice_enabled_var).pack(anchor="w", padx=12, pady=(12, 8))

        ttk.Label(frm, text="Скорость речи:").pack(anchor="w", padx=12)
        self.voice_rate_var = tk.IntVar(value=voice_conf.get("rate", 185))
        ttk.Entry(frm, textvariable=self.voice_rate_var).pack(fill="x", padx=12)

        ttk.Label(frm, text="Громкость (от 0.0 до 1.0):").pack(anchor="w", padx=12, pady=(12, 0))
        self.voice_volume_var = tk.DoubleVar(value=voice_conf.get("volume", 1.0))
        ttk.Entry(frm, textvariable=self.voice_volume_var).pack(fill="x", padx=12)

        ttk.Label(frm, text="Интервал напоминания 'ещё работаю' (сек):").pack(anchor="w", padx=12, pady=(12, 0))
        self.voice_interval_var = tk.IntVar(value=voice_conf.get("heartbeat_interval_sec", 8))
        ttk.Entry(frm, textvariable=self.voice_interval_var).pack(fill="x", padx=12)

        ttk.Button(frm, text="Сохранить голосовые настройки", command=self.save_voice).pack(anchor="e", padx=12, pady=16)

    def _build_paths_tab(self):
        frm = self.paths_tab

        ttk.Label(frm, text="Папки, которые ассистент обязан проверять в первую очередь:").pack(anchor="w", padx=12, pady=(12, 4))

        self.paths_listbox = tk.Listbox(frm, height=18)
        self.paths_listbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        for path in self.config["priority_roots"].get("extra_paths", []):
            self.paths_listbox.insert("end", path)

        entry_frame = ttk.Frame(frm)
        entry_frame.pack(fill="x", padx=12, pady=(0, 8))

        self.new_path_var = tk.StringVar()
        ttk.Entry(entry_frame, textvariable=self.new_path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(entry_frame, text="Добавить", command=self.add_path).pack(side="left", padx=(8, 0))
        ttk.Button(entry_frame, text="Удалить выбранную", command=self.remove_selected_path).pack(side="left", padx=(8, 0))

        ttk.Button(frm, text="Сохранить список папок", command=self.save_paths).pack(anchor="e", padx=12, pady=16)

    def _build_providers_tab(self):
        frm = self.providers_tab

        cols = ("provider_key", "provider_type", "title", "url_template", "is_enabled")
        self.providers_tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        self.providers_tree.pack(fill="both", expand=True, padx=12, pady=(12, 8))

        headers = {
            "provider_key": "Ключ",
            "provider_type": "Тип",
            "title": "Название",
            "url_template": "URL шаблон",
            "is_enabled": "Активен"
        }
        for col in cols:
            self.providers_tree.heading(col, text=headers[col])

        form = ttk.Frame(frm)
        form.pack(fill="x", padx=12, pady=8)

        self.provider_key_var = tk.StringVar()
        self.provider_type_var = tk.StringVar(value="music_search")
        self.provider_title_var = tk.StringVar()
        self.provider_url_var = tk.StringVar()
        self.provider_enabled_var = tk.BooleanVar(value=True)

        ttk.Label(form, text="Ключ").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.provider_key_var).grid(row=1, column=0, sticky="ew", padx=4)

        ttk.Label(form, text="Тип").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.provider_type_var,
            values=["web_search", "youtube_search", "music_search"],
            state="readonly"
        ).grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(form, text="Название").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.provider_title_var).grid(row=1, column=2, sticky="ew", padx=4)

        ttk.Label(form, text="URL шаблон").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.provider_url_var).grid(row=1, column=3, sticky="ew", padx=4)

        ttk.Checkbutton(form, text="Активен", variable=self.provider_enabled_var).grid(row=1, column=4, sticky="w", padx=4)

        for i in range(4):
            form.columnconfigure(i, weight=1)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Обновить список", command=self.refresh_providers).pack(side="left")
        ttk.Button(btns, text="Сохранить провайдер", command=self.save_provider).pack(side="left", padx=6)
        ttk.Button(btns, text="Удалить провайдер", command=self.delete_provider).pack(side="left", padx=6)

        self.providers_tree.bind("<<TreeviewSelect>>", self.on_provider_select)
        self.refresh_providers()

    def _build_quick_tab(self):
        frm = self.quick_tab

        cols = ("name", "target_type", "provider", "usage_count", "is_pinned", "target_path")
        self.quick_tree = ttk.Treeview(frm, columns=cols, show="headings", height=14)
        self.quick_tree.pack(fill="both", expand=True, padx=12, pady=(12, 8))

        headers = {
            "name": "Название",
            "target_type": "Тип",
            "provider": "Провайдер",
            "usage_count": "Использований",
            "is_pinned": "Закреплено",
            "target_path": "Путь / адрес"
        }
        for col in cols:
            self.quick_tree.heading(col, text=headers[col])

        form = ttk.Frame(frm)
        form.pack(fill="x", padx=12, pady=8)

        self.quick_name_var = tk.StringVar()
        self.quick_type_var = tk.StringVar(value="app")
        self.quick_provider_var = tk.StringVar(value="local")
        self.quick_pinned_var = tk.BooleanVar(value=False)
        self.quick_path_var = tk.StringVar()

        ttk.Label(form, text="Название").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.quick_name_var).grid(row=1, column=0, sticky="ew", padx=4)

        ttk.Label(form, text="Тип").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            form,
            textvariable=self.quick_type_var,
            values=["app", "file", "folder", "url"],
            state="readonly"
        ).grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(form, text="Провайдер").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=self.quick_provider_var).grid(row=1, column=2, sticky="ew", padx=4)

        ttk.Label(form, text="Путь / адрес").grid(row=0, column=3, sticky="w")
        ttk.Entry(form, textvariable=self.quick_path_var).grid(row=1, column=3, sticky="ew", padx=4)

        ttk.Checkbutton(form, text="Закрепить", variable=self.quick_pinned_var).grid(row=1, column=4, sticky="w", padx=4)

        for i in range(4):
            form.columnconfigure(i, weight=1)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(btns, text="Обновить список", command=self.refresh_quick_targets).pack(side="left")
        ttk.Button(btns, text="Сохранить цель", command=self.save_quick_target).pack(side="left", padx=6)
        ttk.Button(btns, text="Удалить цель", command=self.delete_quick_target).pack(side="left", padx=6)

        self.quick_tree.bind("<<TreeviewSelect>>", self.on_quick_select)
        self.refresh_quick_targets()

    def save_general(self):
        self.settings.set("default_music_provider", self.music_provider_var.get())
        self.settings.set("default_web_search_provider", self.web_provider_var.get())
        self.settings.set("default_youtube_provider", self.youtube_provider_var.get())
        messagebox.showinfo("Сохранено", "Общие настройки сохранены.")

    def save_voice(self):
        self.config["voice"]["enabled"] = self.voice_enabled_var.get()
        self.config["voice"]["rate"] = self.voice_rate_var.get()
        self.config["voice"]["volume"] = self.voice_volume_var.get()
        self.config["voice"]["heartbeat_interval_sec"] = self.voice_interval_var.get()
        self.loader.save(self.config)
        messagebox.showinfo("Сохранено", "Голосовые настройки сохранены.\nПерезапусти ассистента, чтобы они применились.")

    def add_path(self):
        value = self.new_path_var.get().strip()
        if not value:
            return
        self.paths_listbox.insert("end", value)
        self.new_path_var.set("")

    def remove_selected_path(self):
        selected = self.paths_listbox.curselection()
        if not selected:
            return
        self.paths_listbox.delete(selected[0])

    def save_paths(self):
        paths = list(self.paths_listbox.get(0, "end"))
        self.config["priority_roots"]["extra_paths"] = paths
        self.loader.save(self.config)
        messagebox.showinfo("Сохранено", "Список обязательных папок сохранён.\nДля новой индексации запусти build_index.py.")

    def refresh_providers(self):
        for item in self.providers_tree.get_children():
            self.providers_tree.delete(item)

        for row in self.provider_admin.list_routes():
            provider_type = PROVIDER_TYPE_LABELS.get(row["provider_type"], row["provider_type"])
            is_enabled = "Да" if row["is_enabled"] else "Нет"
            self.providers_tree.insert("", "end", values=(
                row["provider_key"],
                provider_type,
                row["title"],
                row["url_template"],
                is_enabled
            ))

    def on_provider_select(self, event=None):
        selected = self.providers_tree.selection()
        if not selected:
            return
        values = self.providers_tree.item(selected[0], "values")
        self.provider_key_var.set(values[0])

        reverse_map = {v: k for k, v in PROVIDER_TYPE_LABELS.items()}
        self.provider_type_var.set(reverse_map.get(values[1], values[1]))

        self.provider_title_var.set(values[2])
        self.provider_url_var.set(values[3])
        self.provider_enabled_var.set(values[4] == "Да")

    def save_provider(self):
        self.provider_admin.upsert_route(
            provider_key=self.provider_key_var.get().strip(),
            provider_type=self.provider_type_var.get().strip(),
            title=self.provider_title_var.get().strip(),
            url_template=self.provider_url_var.get().strip(),
            is_enabled=self.provider_enabled_var.get()
        )
        self.refresh_providers()
        messagebox.showinfo("Сохранено", "Провайдер сохранён.")

    def delete_provider(self):
        key = self.provider_key_var.get().strip()
        if not key:
            return
        self.provider_admin.delete_route(key)
        self.refresh_providers()
        messagebox.showinfo("Удалено", "Провайдер удалён.")

    def refresh_quick_targets(self):
        for item in self.quick_tree.get_children():
            self.quick_tree.delete(item)

        for row in self.quick_admin.list_targets():
            target_type = TARGET_TYPE_LABELS.get(row["target_type"], row["target_type"])
            is_pinned = "Да" if row["is_pinned"] else "Нет"
            self.quick_tree.insert("", "end", values=(
                row["name"],
                target_type,
                row["provider"],
                row["usage_count"],
                is_pinned,
                row["target_path"]
            ))

    def on_quick_select(self, event=None):
        selected = self.quick_tree.selection()
        if not selected:
            return
        values = self.quick_tree.item(selected[0], "values")
        self.quick_name_var.set(values[0])

        reverse_type = {v: k for k, v in TARGET_TYPE_LABELS.items()}
        self.quick_type_var.set(reverse_type.get(values[1], values[1]))

        self.quick_provider_var.set(values[2])
        self.quick_pinned_var.set(values[4] == "Да")
        self.quick_path_var.set(values[5])

    def save_quick_target(self):
        self.quick_admin.upsert_target(
            name=self.quick_name_var.get().strip(),
            target_path=self.quick_path_var.get().strip(),
            target_type=self.quick_type_var.get().strip(),
            provider=self.quick_provider_var.get().strip(),
            is_pinned=self.quick_pinned_var.get()
        )
        self.refresh_quick_targets()
        messagebox.showinfo("Сохранено", "Быстрая цель сохранена.")

    def delete_quick_target(self):
        path = self.quick_path_var.get().strip()
        if not path:
            return
        self.quick_admin.delete_target(path)
        self.refresh_quick_targets()
        messagebox.showinfo("Удалено", "Быстрая цель удалена.")


def main():
    root = tk.Tk()
    app = AssistantDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()