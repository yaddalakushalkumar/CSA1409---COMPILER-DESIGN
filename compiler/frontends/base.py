"""
base.py - Base interface for Language Frontends.
Defines standard contract for scanning and parsing language-specific source code
into the Universal Abstract Syntax Tree (AST) and Concrete Syntax Tree (CST).
"""

from typing import List, Tuple, Any, Dict, Optional
from ..lexer import Token
from ..errors import DiagnosticCollector
from ..ast_nodes import Program
from ..parser import ConcreteParseTreeNode


class LanguageFrontend:
    name: str = "base"
    display_name: str = "Base Language"

    def tokenize(self, source_code: str, diagnostics: DiagnosticCollector) -> List[Token]:
        raise NotImplementedError

    def parse(self, tokens: List[Token], source_code: str, diagnostics: DiagnosticCollector) -> Tuple[Program, ConcreteParseTreeNode]:
        raise NotImplementedError
