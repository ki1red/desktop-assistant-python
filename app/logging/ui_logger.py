from app.logger import get_logger

ui_logger = get_logger("ui")


def log_ui_action(source: str, action: str, details: str = ""):
    if details:
        ui_logger.info("UI | %s | %s | %s", source, action, details)
    else:
        ui_logger.info("UI | %s | %s", source, action)