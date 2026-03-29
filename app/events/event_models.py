from dataclasses import dataclass
from typing import Optional


@dataclass
class AssistantAnnouncement:
    stage: str
    text: str
    intent: Optional[str] = None
    target_name: Optional[str] = None
    target_path: Optional[str] = None