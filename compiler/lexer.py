"""
lexer.py - Lexical Analyzer (Scanner)
Converts raw source code into a stream of tokens, tracking line and column
coordinates, recognizing keywords, literals, operators, and capturing lexical errors.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple, Any
from .errors import DiagnosticCollector, ErrorStage, ErrorSeverity


class TokenType(str, Enum):
    # Keywords
    KW_INT = "int"
    KW_FLOAT = "float"
    KW_BOOL = "bool"
    KW_STRING = "string"
    KW_VOID = "void"
    KW_IF = "if"
    KW_ELSE = "else"
    KW_WHILE = "while"
    KW_FOR = "for"
    KW_RETURN = "return"
    KW_PRINT = "print"
    KW_PRINTLN = "println"
    KW_READ_INT = "readInt"
    KW_READ_FLOAT = "readFloat"

    # Literals
    LIT_INT = "INT_LITERAL"
    LIT_FLOAT = "FLOAT_LITERAL"
    LIT_STRING = "STRING_LITERAL"
    LIT_BOOL = "BOOL_LITERAL"

    # Identifiers
    IDENTIFIER = "IDENTIFIER"

    # Operators
    PLUS = "+"
    MINUS = "-"
    STAR = "*"
    SLASH = "/"
    PERCENT = "%"
    ASSIGN = "="
    PLUS_ASSIGN = "+="
    MINUS_ASSIGN = "-="
    STAR_ASSIGN = "*="
    SLASH_ASSIGN = "/="

    EQ = "=="
    NEQ = "!="
    LT = "<"
    LEQ = "<="
    GT = ">"
    GEQ = ">="

    AND = "&&"
    OR = "||"
    NOT = "!"

    # Delimiters
    LPAREN = "("
    RPAREN = ")"
    LBRACE = "{"
    RBRACE = "}"
    LBRACKET = "["
    RBRACKET = "]"
    SEMICOLON = ";"
    COMMA = ","

    # Special
    EOF = "EOF"
    ILLEGAL = "ILLEGAL"


KEYWORDS = {
    "int": TokenType.KW_INT,
    "float": TokenType.KW_FLOAT,
    "bool": TokenType.KW_BOOL,
    "string": TokenType.KW_STRING,
    "void": TokenType.KW_VOID,
    "if": TokenType.KW_IF,
    "else": TokenType.KW_ELSE,
    "while": TokenType.KW_WHILE,
    "for": TokenType.KW_FOR,
    "return": TokenType.KW_RETURN,
    "print": TokenType.KW_PRINT,
    "println": TokenType.KW_PRINTLN,
    "readInt": TokenType.KW_READ_INT,
    "readFloat": TokenType.KW_READ_FLOAT,
    "true": TokenType.LIT_BOOL,
    "false": TokenType.LIT_BOOL,
}


@dataclass
class Token:
    type: TokenType
    value: Any
    lexeme: str
    line: int
    column: int
    end_column: int

    @property
    def category(self) -> str:
        t = self.type.value
        if t in [k.value for k in KEYWORDS.values()] and self.type != TokenType.LIT_BOOL:
            return "Keyword"
        if "LITERAL" in self.type.name or self.type == TokenType.LIT_BOOL:
            return "Literal"
        if self.type == TokenType.IDENTIFIER:
            return "Identifier"
        if self.type in [
            TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH, TokenType.PERCENT,
            TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN,
            TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LEQ, TokenType.GT, TokenType.GEQ,
            TokenType.AND, TokenType.OR, TokenType.NOT
        ]:
            return "Operator"
        if self.type in [
            TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACE, TokenType.RBRACE,
            TokenType.LBRACKET, TokenType.RBRACKET, TokenType.SEMICOLON, TokenType.COMMA
        ]:
            return "Delimiter"
        return "Special"

    def to_dict(self):
        return {
            "type": self.type.value,
            "category": self.category,
            "lexeme": self.lexeme,
            "value": self.value,
            "line": self.line,
            "column": self.column,
            "end_column": self.end_column,
        }


class Lexer:
    """Multi-stage Lexical Analyzer with error recovery and diagnostic reporting."""

    def __init__(self, source_code: str, diagnostics: Optional[DiagnosticCollector] = None):
        self.source = source_code
        self.diagnostics = diagnostics or DiagnosticCollector(source_code)
        self.tokens: List[Token] = []
        self.index = 0
        self.line = 1
        self.column = 1
        self.length = len(source_code)

    def current_char(self) -> Optional[str]:
        if self.index < self.length:
            return self.source[self.index]
        return None

    def peek_char(self, offset: int = 1) -> Optional[str]:
        pos = self.index + offset
        if pos < self.length:
            return self.source[pos]
        return None

    def advance(self) -> Optional[str]:
        char = self.current_char()
        self.index += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def tokenize(self) -> List[Token]:
        self.tokens = []
        while self.index < self.length:
            char = self.current_char()

            # Skip whitespace
            if char in " \t\r\n":
                self.advance()
                continue

            # Comments
            if char == "/" and self.peek_char() == "/":
                # Single-line comment
                while self.current_char() is not None and self.current_char() != "\n":
                    self.advance()
                continue

            if char == "/" and self.peek_char() == "*":
                # Multi-line comment
                start_line = self.line
                start_col = self.column
                self.advance()  # /
                self.advance()  # *
                closed = False
                while self.index < self.length:
                    if self.current_char() == "*" and self.peek_char() == "/":
                        self.advance()
                        self.advance()
                        closed = True
                        break
                    self.advance()
                if not closed:
                    self.diagnostics.add(
                        stage=ErrorStage.LEXICAL,
                        code="LEX-001",
                        message="Unterminated multi-line comment. Expected '*/'.",
                        line=start_line,
                        column=start_col,
                        suggestion="Ensure all '/*' comment blocks are properly closed with '*/'.",
                    )
                continue

            start_col = self.column
            start_line = self.line

            # String literals
            if char == '"':
                self.scan_string()
                continue

            # Numbers (integers and floats)
            if char.isdigit():
                self.scan_number()
                continue

            # Identifiers and Keywords
            if char.isalpha() or char == "_":
                self.scan_identifier()
                continue

            # Two-character operators
            two_chars = self.source[self.index : self.index + 2]
            two_char_map = {
                "==": TokenType.EQ,
                "!=": TokenType.NEQ,
                "<=": TokenType.LEQ,
                ">=": TokenType.GEQ,
                "&&": TokenType.AND,
                "||": TokenType.OR,
                "+=": TokenType.PLUS_ASSIGN,
                "-=": TokenType.MINUS_ASSIGN,
                "*=": TokenType.STAR_ASSIGN,
                "/=": TokenType.SLASH_ASSIGN,
            }
            if two_chars in two_char_map:
                self.tokens.append(
                    Token(
                        type=two_char_map[two_chars],
                        value=two_chars,
                        lexeme=two_chars,
                        line=start_line,
                        column=start_col,
                        end_column=start_col + 1,
                    )
                )
                self.advance()
                self.advance()
                continue

            # Single-character tokens
            single_char_map = {
                "+": TokenType.PLUS,
                "-": TokenType.MINUS,
                "*": TokenType.STAR,
                "/": TokenType.SLASH,
                "%": TokenType.PERCENT,
                "=": TokenType.ASSIGN,
                "<": TokenType.LT,
                ">": TokenType.GT,
                "!": TokenType.NOT,
                "(": TokenType.LPAREN,
                ")": TokenType.RPAREN,
                "{": TokenType.LBRACE,
                "}": TokenType.RBRACE,
                "[": TokenType.LBRACKET,
                "]": TokenType.RBRACKET,
                ";": TokenType.SEMICOLON,
                ",": TokenType.COMMA,
            }

            if char in single_char_map:
                token_type = single_char_map[char]
                self.tokens.append(
                    Token(
                        type=token_type,
                        value=char,
                        lexeme=char,
                        line=start_line,
                        column=start_col,
                        end_column=start_col,
                    )
                )
                self.advance()
                continue

            # Unrecognized / Illegal character
            illegal_char = self.advance()
            suggestion = None
            if illegal_char in ["$", "@", "#", "`", "~"]:
                suggestion = f"The symbol '{illegal_char}' is not a valid operator or delimiter in C-Lite."

            self.diagnostics.add(
                stage=ErrorStage.LEXICAL,
                code="LEX-002",
                message=f"Illegal character '{illegal_char}' encountered.",
                line=start_line,
                column=start_col,
                end_column=start_col,
                suggestion=suggestion,
            )
            self.tokens.append(
                Token(
                    type=TokenType.ILLEGAL,
                    value=illegal_char,
                    lexeme=illegal_char,
                    line=start_line,
                    column=start_col,
                    end_column=start_col,
                )
            )

        # Append EOF
        self.tokens.append(
            Token(
                type=TokenType.EOF,
                value=None,
                lexeme="EOF",
                line=self.line,
                column=self.column,
                end_column=self.column,
            )
        )
        return self.tokens

    def scan_identifier(self):
        start_col = self.column
        start_line = self.line
        chars = []
        while self.current_char() is not None and (
            self.current_char().isalnum() or self.current_char() == "_"
        ):
            chars.append(self.advance())

        lexeme = "".join(chars)
        end_col = start_col + len(lexeme) - 1

        if lexeme in KEYWORDS:
            token_type = KEYWORDS[lexeme]
            val = True if lexeme == "true" else False if lexeme == "false" else lexeme
            self.tokens.append(
                Token(
                    type=token_type,
                    value=val,
                    lexeme=lexeme,
                    line=start_line,
                    column=start_col,
                    end_column=end_col,
                )
            )
        else:
            self.tokens.append(
                Token(
                    type=TokenType.IDENTIFIER,
                    value=lexeme,
                    lexeme=lexeme,
                    line=start_line,
                    column=start_col,
                    end_column=end_col,
                )
            )

    def scan_number(self):
        start_col = self.column
        start_line = self.line
        chars = []
        has_dot = False

        while self.current_char() is not None and (
            self.current_char().isdigit() or self.current_char() == "."
        ):
            if self.current_char() == ".":
                if has_dot:
                    # Multiple dots in number
                    chars.append(self.advance())
                    lexeme = "".join(chars)
                    self.diagnostics.add(
                        stage=ErrorStage.LEXICAL,
                        code="LEX-003",
                        message=f"Malformed float literal '{lexeme}' has multiple decimal points.",
                        line=start_line,
                        column=start_col,
                        end_column=self.column - 1,
                        suggestion="Remove the extra decimal point.",
                    )
                    self.tokens.append(
                        Token(
                            type=TokenType.ILLEGAL,
                            value=lexeme,
                            lexeme=lexeme,
                            line=start_line,
                            column=start_col,
                            end_column=self.column - 1,
                        )
                    )
                    return
                # Check if dot is followed by a digit
                if self.peek_char() and self.peek_char().isdigit():
                    has_dot = True
                    chars.append(self.advance())
                else:
                    break
            else:
                chars.append(self.advance())

        lexeme = "".join(chars)
        end_col = start_col + len(lexeme) - 1

        if has_dot:
            val = float(lexeme)
            t_type = TokenType.LIT_FLOAT
        else:
            val = int(lexeme)
            t_type = TokenType.LIT_INT

        self.tokens.append(
            Token(
                type=t_type,
                value=val,
                lexeme=lexeme,
                line=start_line,
                column=start_col,
                end_column=end_col,
            )
        )

    def scan_string(self):
        start_col = self.column
        start_line = self.line
        self.advance()  # consume opening quote
        chars = []
        closed = False

        while self.current_char() is not None:
            c = self.current_char()
            if c == "\n":
                break  # newlines cannot be raw inside string without escape
            if c == "\\":
                self.advance()
                esc = self.current_char()
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == '"':
                    chars.append('"')
                elif esc == "\\":
                    chars.append("\\")
                else:
                    chars.append(esc or "")
                self.advance()
                continue
            if c == '"':
                self.advance()  # consume closing quote
                closed = True
                break
            chars.append(self.advance())

        raw_content = "".join(chars)
        if not closed:
            self.diagnostics.add(
                stage=ErrorStage.LEXICAL,
                code="LEX-004",
                message="Unclosed string literal. Missing terminating quote (\").",
                line=start_line,
                column=start_col,
                end_column=self.column - 1,
                suggestion="Add a closing double quote '\"' at the end of the string.",
            )
            self.tokens.append(
                Token(
                    type=TokenType.ILLEGAL,
                    value=raw_content,
                    lexeme='"' + raw_content,
                    line=start_line,
                    column=start_col,
                    end_column=self.column - 1,
                )
            )
            return

        full_lexeme = f'"{raw_content}"'
        self.tokens.append(
            Token(
                type=TokenType.LIT_STRING,
                value=raw_content,
                lexeme=full_lexeme,
                line=start_line,
                column=start_col,
                end_column=self.column - 1,
            )
        )
