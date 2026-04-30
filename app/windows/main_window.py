from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QApplication,
    QProxyStyle,
    QStyle,
    QScrollArea,
    QFrame,
)

from app.windows.logs_widget import LogsWidget
from app.windows.providers_widget import ProvidersWidget
from app.windows.quick_targets_widget import QuickTargetsWidget
from app.windows.paths_widget import PathsWidget
from app.windows.audio_widget import AudioSettingsWidget
from app.windows.history_widget import HistoryWidget
from app.windows.custom_commands_widget import CustomCommandsWidget
from app.windows.status_widget import StatusWidget
from app.windows.ai_widget import AISettingsWidget
from app.windows.assistant_widget import AssistantWidget
from app.windows.app_settings_widget import AppSettingsWidget
from app.windows.tooltip_manager import install_custom_tooltips
from app.settings_service import settings_service
from app.logger import get_logger
from app.plugins.ui_registry import get_plugin_tab_specs


logger = get_logger("ui")


LOGS_TAB_TITLE = "Логи"

SYSTEM_TABS = {
    "Быстрые цели",
    "Папки",
    "Провайдеры",
    "История",
    "Пользовательские команды",
}


class FastToolTipStyle(QProxyStyle):
    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 120

        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return 9000

        return super().styleHint(hint, option, widget, returnData)


class AssistantMainWindow(QMainWindow):
    def __init__(self, bg_service):
        logger.info("UI | MainWindow | init_start")

        super().__init__()
        self.setWindowTitle("Local PC Assistant")
        self.resize(1250, 860)

        self._install_tooltip_style()
        self._apply_window_style()

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._previous_tab_index = -1
        self._tab_indexes: dict[str, int] = {}

        self._plugin_tab_specs = get_plugin_tab_specs()
        self._plugin_tab_titles = {spec.title for spec in self._plugin_tab_specs}

        # Базовые вкладки — всегда есть.
        self._add_tab("Состояние", lambda: StatusWidget(bg_service))
        self._add_tab("ИИ", AISettingsWidget)
        self._add_tab("Аудио", AudioSettingsWidget)
        self._add_tab("Ассистент", AssistantWidget)
        self._add_tab("Настройки", AppSettingsWidget)
        self._add_tab(LOGS_TAB_TITLE, LogsWidget, wrap_scrollable=False)

        # Динамические plugin tabs должны идти сразу после "Логи".
        self._add_plugin_tabs()

        # Старые системные вкладки пока сохраняем, но скрываем по настройке.
        self._add_tab("Быстрые цели", QuickTargetsWidget)
        self._add_tab("Папки", PathsWidget)
        self._add_tab("Провайдеры", ProvidersWidget)
        self._add_tab("История", HistoryWidget)
        self._add_tab("Пользовательские команды", CustomCommandsWidget)

        self.setCentralWidget(self.tabs)

        settings_service.subscribe(self._on_settings_changed)

        initial_snapshot = settings_service.get_all()
        self._apply_system_tabs_visibility(initial_snapshot)
        self._apply_plugin_tabs_visibility(initial_snapshot)

        logger.info("UI | MainWindow | init_done")

    def _wrap_scrollable(self, widget):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setWidget(widget)

        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
        """)

        return scroll

    def _unwrap_tab_widget(self, widget):
        if isinstance(widget, QScrollArea):
            return widget.widget()
        return widget

    def _install_tooltip_style(self):
        app = QApplication.instance()
        if app is None:
            return

        current_style = app.style()
        if not isinstance(current_style, FastToolTipStyle):
            app.setStyle(FastToolTipStyle(current_style))

        install_custom_tooltips(app)

    def _apply_window_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #f7f8fb;
            }

            QTabWidget::pane {
                border: 1px solid #d6d9e0;
                background: #ffffff;
                border-radius: 10px;
            }

            QTabWidget::tab-bar {
                alignment: center;
            }

            QTabBar::tab {
                font-size: 15px;
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                background: #eceff5;
            }

            QTabBar::tab:selected {
                background: #ffffff;
                font-weight: 600;
            }

            QLabel {
                font-size: 17px;
            }

            QPushButton {
                font-size: 16px;
                padding: 8px 14px;
                border-radius: 8px;
                border: 1px solid #b8beca;
                background: #ffffff;
            }

            QPushButton:hover {
                background: #f0f3f8;
            }

            QPushButton:pressed {
                background: #e4e8f0;
            }

            QPushButton:disabled {
                color: #9aa3b2;
                background: #eef1f5;
                border: 1px solid #d6dbe5;
            }

            QLineEdit, QComboBox {
                font-size: 16px;
                padding: 7px;
                border-radius: 7px;
                border: 1px solid #b8beca;
                background: #ffffff;
            }

            QCheckBox {
                font-size: 17px;
                spacing: 10px;
            }

            QCheckBox::indicator {
                width: 24px;
                height: 24px;
            }

            QTableWidget {
                font-size: 14px;
            }
        """)

    def _add_tab(self, title: str, factory, wrap_scrollable: bool = True):
        logger.info("UI | MainWindow | create_tab_start | %s", title)

        try:
            widget = factory()
            page = self._wrap_scrollable(widget) if wrap_scrollable else widget

            index = self.tabs.addTab(page, title)
            self._tab_indexes[title] = index

            logger.info("UI | MainWindow | create_tab_done | %s", title)
        except Exception as e:
            logger.exception("UI | MainWindow | create_tab_failed | %s | %s", title, e)
            raise

    def _add_plugin_tabs(self):
        """
        Добавляет вкладки плагинов сразу после "Логи".

        Пока часть плагинов может не иметь UI — тогда вкладка просто
        не создаётся. Каркас всё равно уже готов.
        """
        if not self._plugin_tab_specs:
            logger.info("UI | MainWindow | plugin_tabs | no plugin tabs registered")
            return

        for spec in self._plugin_tab_specs:
            if spec.title in self._tab_indexes:
                logger.warning(
                    "UI | MainWindow | plugin_tabs | duplicate tab title skipped | plugin=%s title=%s",
                    spec.plugin_id,
                    spec.title,
                )
                continue

            self._add_tab(
                title=spec.title,
                factory=spec.factory,
                wrap_scrollable=bool(spec.scrollable),
            )

    def _on_settings_changed(self, config_snapshot: dict):
        self._apply_system_tabs_visibility(config_snapshot)
        self._apply_plugin_tabs_visibility(config_snapshot)

    def _apply_system_tabs_visibility(self, config_snapshot: dict):
        ui = config_snapshot.get("ui", {})
        show_system_tabs = bool(ui.get("show_system_tabs", False))

        for title in SYSTEM_TABS:
            index = self._tab_indexes.get(title)
            if index is not None:
                self.tabs.setTabVisible(index, show_system_tabs)

        self._ensure_current_tab_visible()

    def _is_plugin_enabled_in_snapshot(
        self,
        config_snapshot: dict,
        plugin_id: str,
        default_enabled: bool,
    ) -> bool:
        plugins_cfg = config_snapshot.get("plugins", {})
        enabled_map = plugins_cfg.get("enabled")

        if isinstance(enabled_map, dict):
            return bool(enabled_map.get(plugin_id, default_enabled))

        legacy_enabled = config_snapshot.get("assistant", {}).get("enabled_plugins")
        if isinstance(legacy_enabled, list):
            return plugin_id in {str(item) for item in legacy_enabled}

        return bool(default_enabled)

    def _apply_plugin_tabs_visibility(self, config_snapshot: dict):
        """
        Показывает или скрывает plugin tabs по состоянию plugins.enabled.

        Это не трогает обязательные вкладки и не зависит от show_system_tabs.
        """
        for spec in self._plugin_tab_specs:
            index = self._tab_indexes.get(spec.title)
            if index is None:
                continue

            visible = self._is_plugin_enabled_in_snapshot(
                config_snapshot=config_snapshot,
                plugin_id=spec.plugin_id,
                default_enabled=spec.default_enabled,
            )

            self.tabs.setTabVisible(index, visible)

        self._ensure_current_tab_visible()

    def _ensure_current_tab_visible(self):
        current_index = self.tabs.currentIndex()
        if current_index >= 0 and not self.tabs.isTabVisible(current_index):
            self.tabs.setCurrentIndex(0)

    def _on_tab_changed(self, index: int):
        if self._previous_tab_index >= 0 and self._previous_tab_index != index:
            previous_page = self.tabs.widget(self._previous_tab_index)
            previous_widget = self._unwrap_tab_widget(previous_page)
            previous_title = self.tabs.tabText(self._previous_tab_index)

            if previous_widget and hasattr(previous_widget, "on_tab_deactivated"):
                try:
                    logger.info("UI | MainWindow | deactivate_tab | %s", previous_title)
                    previous_widget.on_tab_deactivated()
                except Exception as e:
                    logger.exception(
                        "UI | MainWindow | tab deactivation failed | %s | %s",
                        previous_title,
                        e,
                    )

        title = self.tabs.tabText(index) if index >= 0 else ""
        logger.info("UI | MainWindow | switch_tab | %s", title)

        page = self.tabs.widget(index)
        widget = self._unwrap_tab_widget(page)

        if widget and hasattr(widget, "on_tab_activated"):
            try:
                widget.on_tab_activated()
            except Exception as e:
                logger.exception(
                    "UI | MainWindow | tab activation failed | %s | %s",
                    title,
                    e,
                )

        self._previous_tab_index = index

    def closeEvent(self, event):
        self.hide()
        event.ignore()