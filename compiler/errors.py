"""
errors.py - Automated Error Detection and Diagnostic Engine.
Provides structured diagnostic reporting with line/column coordinates,
source code context snippets, error codes, and heuristic suggestions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import difflib


class ErrorSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    HINT = "HINT"


class ErrorStage(str, Enum):
    LEXICAL = "LEXICAL"
    SYNTACTIC = "SYNTACTIC"
    SEMANTIC = "SEMANTIC"
    RUNTIME = "RUNTIME"


@dataclass
class Diagnostic:
    stage: ErrorStage
    code: str
    message: str
    line: int
    column: int
    end_column: Optional[int] = None
    severity: ErrorSeverity = ErrorSeverity.ERROR
    suggestion: Optional[str] = None
    snippet: Optional[str] = None

    def to_dict(self):
        return {
            "stage": self.stage.value,
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "end_column": self.end_column or self.column,
            "severity": self.severity.value,
            "suggestion": self.suggestion,
            "snippet": self.snippet,
        }

    def format_cli(self, source_lines: Optional[List[str]] = None) -> str:
        header = f"[{self.severity.value}] {self.stage.value} ({self.code}) at Line {self.line}, Col {self.column}: {self.message}"
        lines = [header]
        if source_lines and 1 <= self.line <= len(source_lines):
            src_line = source_lines[self.line - 1]
            lines.append(f"  {self.line:4d} | {src_line}")
            start_col = max(1, self.column)
            end_col = max(start_col, self.end_column or start_col)
            indicator_len = max(1, end_col - start_col + 1)
            pointer = " " * (start_col - 1) + "^" + ("~" * (indicator_len - 1))
            lines.append(f"       | {pointer}")
        if self.suggestion:
            lines.append(f"  --> Suggestion: {self.suggestion}")
        return "\n".join(lines)


class DiagnosticCollector:
    """Collects and organizes diagnostics from all compilation stages."""

    def __init__(self, source_code: str = ""):
        self.source_code = source_code
        self.source_lines = source_code.splitlines() if source_code else []
        self.diagnostics: List[Diagnostic] = []

    def set_source(self, source_code: str):
        self.source_code = source_code
        self.source_lines = source_code.splitlines()

    def add(
        self,
        stage: ErrorStage,
        code: str,
        message: str,
        line: int,
        column: int,
        end_column: Optional[int] = None,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        suggestion: Optional[str] = None,
    ) -> Diagnostic:
        # Generate snippet automatically if available
        snippet = None
        if self.source_lines and 1 <= line <= len(self.source_lines):
            src = self.source_lines[line - 1]
            s_col = max(1, column)
            e_col = max(s_col, end_column or s_col)
            pointer = " " * (s_col - 1) + "^" + ("~" * max(0, e_col - s_col))
            snippet = f"{line:4d} | {src}\n     | {pointer}"

        diag = Diagnostic(
            stage=stage,
            code=code,
            message=message,
            line=line,
            column=column,
            end_column=end_column,
            severity=severity,
            suggestion=suggestion,
            snippet=snippet,
        )
        self.diagnostics.append(diag)
        return diag

    def has_errors(self) -> bool:
        return any(d.severity == ErrorSeverity.ERROR for d in self.diagnostics)

    def errors_for_stage(self, stage: ErrorStage) -> List[Diagnostic]:
        return [d for d in self.diagnostics if d.stage == stage]

    def to_list(self):
        return [d.to_dict() for d in self.diagnostics]

    @staticmethod
    def suggest_similar(target: str, candidates: List[str]) -> Optional[str]:
        """Finds closest identifier or keyword match using Levenshtein distance."""
        matches = difflib.get_close_matches(target, candidates, n=1, cutoff=0.55)
        if matches:
            return f"Did you mean '{matches[0]}'?"
        return None
