"""
java_frontend.py - Java Language Frontend
Parses Java source code, handles class wrappers, main method entry points,
System.out.println mappings, and generates the Universal AST.
"""

import re
from typing import List, Tuple
from .base import LanguageFrontend
from ..lexer import Lexer, Token, TokenType
from ..parser import Parser, ConcreteParseTreeNode
from ..ast_nodes import Program
from ..errors import DiagnosticCollector


class JavaFrontend(LanguageFrontend):
    name = "java"
    display_name = "Java"

    def tokenize(self, source_code: str, diagnostics: DiagnosticCollector) -> List[Token]:
        preprocessed = self._preprocess_java(source_code)
        lexer = Lexer(preprocessed, diagnostics)
        return lexer.tokenize()

    def parse(self, tokens: List[Token], source_code: str, diagnostics: DiagnosticCollector) -> Tuple[Program, ConcreteParseTreeNode]:
        preprocessed = self._preprocess_java(source_code)
        clean_tokens = Lexer(preprocessed, diagnostics).tokenize()
        parser = Parser(clean_tokens, diagnostics)
        ast, cst = parser.parse()
        cst.name = "<JavaProgram>"
        return ast, cst

    def _preprocess_java(self, code: str) -> str:
        """Normalizes Java specific boilerplate into clean C-Lite compatible syntax."""
        # Replace System.out.println and System.out.print
        res = re.sub(r'System\.out\.println\s*\(', 'println(', code)
        res = re.sub(r'System\.out\.print\s*\(', 'print(', res)

        # Replace Java types: boolean -> bool, double -> float, String -> string
        res = re.sub(r'\bboolean\b', 'bool', res)
        res = re.sub(r'\bdouble\b', 'float', res)
        res = re.sub(r'\bString\b', 'string', res)

        lines = res.splitlines()
        clean_lines = []
        braces_removed = 0

        for line in lines:
            stripped = line.strip()
            # Skip package and import statements
            if stripped.startswith("package ") or stripped.startswith("import "):
                clean_lines.append("// " + line)
                continue

            # Check for class wrapper
            if re.search(r'public\s+class\s+\w+\s*\{?', stripped):
                clean_lines.append("// " + line)
                if "{" in stripped:
                    braces_removed += 1
                continue

            # Check for main method wrapper
            if re.search(r'public\s+static\s+void\s+main\s*\(', stripped):
                clean_lines.append("// " + line)
                if "{" in stripped:
                    braces_removed += 1
                continue

            clean_lines.append(line)

        # Remove matching closing braces from the bottom
        for i in range(len(clean_lines) - 1, -1, -1):
            if braces_removed <= 0:
                break
            if clean_lines[i].strip() == "}":
                clean_lines[i] = "// }"
                braces_removed -= 1

        return "\n".join(clean_lines)
