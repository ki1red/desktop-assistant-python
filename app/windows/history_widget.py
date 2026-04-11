from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QLabel

from app.indexing.db import get_connection


class HistoryWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("История выполнения команд ассистента."))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Время", "Запрос", "Intent", "Цель", "Тип", "Успех"
        ])
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)
        layout.addLayout(btn_row)

    def refresh(self):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT used_at, query_text, intent, target_name, target_type, success
        FROM usage_history
        ORDER BY id DESC
        LIMIT 300
        """)
        rows = cur.fetchall()
        conn.close()

        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(row["used_at"] or ""))
            self.table.setItem(i, 1, QTableWidgetItem(row["query_text"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(row["intent"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(row["target_name"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(row["target_type"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem("Да" if row["success"] else "Нет"))

        self.table.resizeColumnsToContents()