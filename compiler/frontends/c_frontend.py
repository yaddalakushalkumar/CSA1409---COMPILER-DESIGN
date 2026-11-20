"""
c_frontend.py - C Language Frontend
Parses C / C-Lite source code, handling preprocessor directives, standard types,
printf/scanf mappings, and building the Universal AST.
"""

import re
from typing import List, Tuple
from .base import LanguageFrontend
from ..lexer import Lexer, Token, TokenType
from ..parser import Parser, ConcreteParseTreeNode
from ..ast_nodes import Program
from ..errors import DiagnosticCollector


class CFrontend(LanguageFrontend):
    name = "c"
    display_name = "C / C-Lite"

    def tokenize(self, source_code: str, diagnostics: DiagnosticCollector) -> List[Token]:
        clean_code = []
        for line in source_code.splitlines():
            stripped = line.strip()
            if stripped.startswith("#include") or stripped.startswith("#define"):
                clean_code.append("// " + line)
            else:
                clean_code.append(line)
        processed_source = "\n".join(clean_code)

        # Map printf to print for standard output
        processed_source = re.sub(r'\bprintf\s*\(', 'print(', processed_source)

        lexer = Lexer(processed_source, diagnostics)
        return lexer.tokenize()

    def parse(self, tokens: List[Token], source_code: str, diagnostics: DiagnosticCollector) -> Tuple[Program, ConcreteParseTreeNode]:
        clean_code = []
        for line in source_code.splitlines():
            stripped = line.strip()
            if stripped.startswith("#include") or stripped.startswith("#define"):
                clean_code.append("// " + line)
            else:
                clean_code.append(line)
        processed_source = "\n".join(clean_code)
        processed_source = re.sub(r'\bprintf\s*\(', 'print(', processed_source)

        clean_tokens = Lexer(processed_source, diagnostics).tokenize()
        parser = Parser(clean_tokens, diagnostics)
        return parser.parse()
