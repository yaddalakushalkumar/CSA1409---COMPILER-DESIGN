"""
cpp_frontend.py - C++ Language Frontend
Parses C++ source code, handling namespaces, iostream (cout / cin) streams,
preprocessor directives, and standard C++ functions into the Universal AST.
"""

import re
from typing import List, Tuple
from .base import LanguageFrontend
from ..lexer import Lexer, Token, TokenType
from ..parser import Parser, ConcreteParseTreeNode
from ..ast_nodes import Program
from ..errors import DiagnosticCollector


class CPPFrontend(LanguageFrontend):
    name = "cpp"
    display_name = "C++"

    def tokenize(self, source_code: str, diagnostics: DiagnosticCollector) -> List[Token]:
        preprocessed = self._preprocess_cpp(source_code)
        lexer = Lexer(preprocessed, diagnostics)
        return lexer.tokenize()

    def parse(self, tokens: List[Token], source_code: str, diagnostics: DiagnosticCollector) -> Tuple[Program, ConcreteParseTreeNode]:
        preprocessed = self._preprocess_cpp(source_code)
        clean_tokens = Lexer(preprocessed, diagnostics).tokenize()
        parser = Parser(clean_tokens, diagnostics)
        ast, cst = parser.parse()
        cst.name = "<CppProgram>"
        return ast, cst

    def _preprocess_cpp(self, code: str) -> str:
        """Translates C++ specific constructs (cout, cin, namespaces) into standard C-Lite."""
        lines = code.splitlines()
        clean_lines = []

        for line in lines:
            stripped = line.strip()
            # Ignore includes and using namespace
            if stripped.startswith("#include") or stripped.startswith("using namespace"):
                clean_lines.append("// " + line)
                continue

            # Transform cout << expr << endl; -> println(expr);
            if "cout" in stripped and "<<" in stripped:
                # Remove std::
                l = stripped.replace("std::cout", "cout").replace("std::endl", "endl")
                # Split parts by <<
                parts = [p.strip().rstrip(";") for p in l.split("<<") if p.strip()]
                # First part was 'cout'
                sub_stmts = []
                for p in parts[1:]:
                    if p in ("endl", '"\\n"'):
                        sub_stmts.append('println("");')
                    else:
                        sub_stmts.append(f'println({p});')
                clean_lines.append(" ".join(sub_stmts))
                continue

            clean_lines.append(line)

        res = "\n".join(clean_lines)
        # double -> float
        res = re.sub(r'\bdouble\b', 'float', res)
        return res
