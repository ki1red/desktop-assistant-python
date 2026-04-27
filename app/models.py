from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class STTResult:
    text: str
    language: Optional[str] = None


@dataclass
class ParsedCommand:
    raw_text: str
    normalized_text: str
    intent: str
    target_text: str

    # Новые поля для plugin-architecture.
    # У них есть значения по умолчанию, поэтому старый код,
    # который создаёт ParsedCommand(raw, normalized, intent, target),
    # продолжит работать без изменений.
    plugin_id: Optional[str] = None
    command_id: Optional[str] = None
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Candidate:
    name: str
    path: str
    score: float
    target_type: str


@dataclass
class ResolvedTarget:
    success: bool
    target_type: Optional[str] = None
    target_name: Optional[str] = None
    target_path: Optional[str] = None
    candidates: List[Candidate] = field(default_factory=list)
    error: Optional[str] = None
    needs_confirmation: bool = False
    confirmation_message: Optional[str] = None
    suggests_deep_search: bool = False


@dataclass
class ExecutionResult:
    success: bool
    message: str
    intent: Optional[str] = None
    target_path: Optional[str] = None