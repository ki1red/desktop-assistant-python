from datetime import datetime
from pathlib import Path
import zipfile

from app.logging_config import LOG_DIR


def default_logs_archive_name() -> str:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"LocalAssistant_logs_{stamp}.zip"


def build_logs_archive(output_path: str | Path) -> Path:
    output_path = Path(output_path)

    if output_path.suffix.lower() != ".zip":
        output_path = output_path.with_suffix(".zip")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(LOG_DIR.iterdir(), key=lambda p: p.name.lower()):
            if not item.is_file():
                continue

            # Чтобы случайно не вложить архив логов в архив,
            # если пользователь сохраняет его прямо в папку логов.
            if item.resolve() == output_path.resolve():
                continue

            archive.write(item, arcname=item.name)

    return output_path