from dataclasses import dataclass, field
from typing import List, Optional


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