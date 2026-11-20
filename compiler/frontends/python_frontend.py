"""
python_frontend.py - Python Language Frontend
Scans and parses Python source code, translates Python AST nodes into the
Universal Compiler AST, tracks indentation/tokens, and captures Python syntax errors.
"""

import ast
import io
import tokenize as py_tokenize
from typing import List, Tuple, Any, Optional

from .base import LanguageFrontend
from ..lexer import Token, TokenType
from ..parser import ConcreteParseTreeNode
from ..ast_nodes import (
    Program, ASTNode, VarDecl, AssignStmt, Block, IfStmt, WhileStmt,
    ForStmt, FunctionDecl, ReturnStmt, PrintStmt, ExprStmt,
    BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, CallExpr
)
from ..errors import DiagnosticCollector, ErrorStage, ErrorSeverity


class PythonASTTransformer:
    """Translates Python's native AST into our Universal AST."""

    def __init__(self, diagnostics: DiagnosticCollector):
        self.diagnostics = diagnostics
        self.declared_vars = set()

    def transform(self, py_tree: ast.Module) -> Program:
        statements = []
        for stmt in py_tree.body:
            node = self.transform_stmt(stmt)
            if node:
                statements.append(node)
        return Program(line=1, column=1, end_column=1, statements=statements)

    def transform_stmt(self, stmt: ast.AST) -> Optional[ASTNode]:
        line = getattr(stmt, "lineno", 1)
        col = getattr(stmt, "col_offset", 0) + 1

        if isinstance(stmt, ast.Assign):
            # Target variable
            target = stmt.targets[0]
            val_node = self.transform_expr(stmt.value)
            if isinstance(target, ast.Name):
                name = target.id
                # In Python, first assignment acts as variable declaration
                if name not in self.declared_vars:
                    self.declared_vars.add(name)
                    # Infer type from value if possible
                    inferred = getattr(val_node, "lit_type", "int") if isinstance(val_node, LiteralExpr) else "int"
                    return VarDecl(line=line, column=col, var_type=inferred, name=name, initializer=val_node)
                else:
                    return AssignStmt(line=line, column=col, name=name, operator="=", value=val_node)

        elif isinstance(stmt, ast.AugAssign):
            if isinstance(stmt.target, ast.Name):
                op_map = {ast.Add: "+=", ast.Sub: "-=", ast.Mult: "*=", ast.Div: "/="}
                op_str = op_map.get(type(stmt.op), "=")
                val_node = self.transform_expr(stmt.value)
                return AssignStmt(line=line, column=col, name=stmt.target.id, operator=op_str, value=val_node)

        elif isinstance(stmt, ast.FunctionDef):
            params = [{"type": "int", "name": arg.arg} for arg in stmt.args.args]
            body_stmts = [self.transform_stmt(s) for s in stmt.body if s]
            body_stmts = [s for s in body_stmts if s is not None]
            body_block = Block(line=line, column=col, statements=body_stmts)
            return FunctionDecl(line=line, column=col, return_type="int", name=stmt.name, params=params, body=body_block)

        elif isinstance(stmt, ast.If):
            cond = self.transform_expr(stmt.test)
            then_stmts = [self.transform_stmt(s) for s in stmt.body if s]
            then_block = Block(line=line, column=col, statements=[s for s in then_stmts if s])
            else_block = None
            if stmt.orelse:
                else_stmts = [self.transform_stmt(s) for s in stmt.orelse if s]
                else_block = Block(line=line, column=col, statements=[s for s in else_stmts if s])
            return IfStmt(line=line, column=col, condition=cond, then_branch=then_block, else_branch=else_block)

        elif isinstance(stmt, ast.While):
            cond = self.transform_expr(stmt.test)
            body_stmts = [self.transform_stmt(s) for s in stmt.body if s]
            body_block = Block(line=line, column=col, statements=[s for s in body_stmts if s])
            return WhileStmt(line=line, column=col, condition=cond, body=body_block)

        elif isinstance(stmt, ast.For):
            # Transform for i in range(...) into while or for loop structure
            iter_var = stmt.target.id if isinstance(stmt.target, ast.Name) else "i"
            body_stmts = [self.transform_stmt(s) for s in stmt.body if s]
            body_block = Block(line=line, column=col, statements=[s for s in body_stmts if s])
            return ForStmt(line=line, column=col, body=body_block)

        elif isinstance(stmt, ast.Return):
            val = self.transform_expr(stmt.value) if stmt.value else None
            return ReturnStmt(line=line, column=col, value=val)

        elif isinstance(stmt, ast.Expr):
            # Check for print()
            if isinstance(stmt.value, ast.Call) and isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == "print":
                arg_node = self.transform_expr(stmt.value.args[0]) if stmt.value.args else LiteralExpr(value="", lit_type="string")
                return PrintStmt(line=line, column=col, expression=arg_node, is_newline=True)
            expr = self.transform_expr(stmt.value)
            return ExprStmt(line=line, column=col, expression=expr)

        return None

    def transform_expr(self, expr: ast.AST) -> Optional[ASTNode]:
        line = getattr(expr, "lineno", 1)
        col = getattr(expr, "col_offset", 0) + 1

        if isinstance(expr, ast.Constant):
            val = expr.value
            if isinstance(val, bool):
                return LiteralExpr(line=line, column=col, value=val, lit_type="bool")
            elif isinstance(val, int):
                return LiteralExpr(line=line, column=col, value=val, lit_type="int")
            elif isinstance(val, float):
                return LiteralExpr(line=line, column=col, value=val, lit_type="float")
            elif isinstance(val, str):
                return LiteralExpr(line=line, column=col, value=val, lit_type="string")
            return LiteralExpr(line=line, column=col, value=str(val), lit_type="string")

        elif isinstance(expr, ast.Name):
            return VariableExpr(line=line, column=col, name=expr.id)

        elif isinstance(expr, ast.BinOp):
            op_map = {
                ast.Add: "+", ast.Sub: "-", ast.Mult: "*",
                ast.Div: "/", ast.Mod: "%"
            }
            op_str = op_map.get(type(expr.op), "+")
            left = self.transform_expr(expr.left)
            right = self.transform_expr(expr.right)
            return BinaryExpr(line=line, column=col, left=left, operator=op_str, right=right)

        elif isinstance(expr, ast.Compare):
            op_map = {
                ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<",
                ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="
            }
            op_str = op_map.get(type(expr.ops[0]), "==")
            left = self.transform_expr(expr.left)
            right = self.transform_expr(expr.comparators[0])
            return BinaryExpr(line=line, column=col, left=left, operator=op_str, right=right)

        elif isinstance(expr, ast.BoolOp):
            op_str = "&&" if isinstance(expr.op, ast.And) else "||"
            left = self.transform_expr(expr.values[0])
            right = self.transform_expr(expr.values[1])
            return BinaryExpr(line=line, column=col, left=left, operator=op_str, right=right)

        elif isinstance(expr, ast.UnaryOp):
            op_str = "!" if isinstance(expr.op, ast.Not) else "-"
            operand = self.transform_expr(expr.operand)
            return UnaryExpr(line=line, column=col, operator=op_str, operand=operand)

        elif isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name):
                fn_name = expr.func.id
                args = [self.transform_expr(a) for a in expr.args]
                return CallExpr(line=line, column=col, callee=fn_name, args=args)

        return LiteralExpr(line=line, column=col, value=0, lit_type="int")


class PythonFrontend(LanguageFrontend):
    name = "python"
    display_name = "Python 3"

    def tokenize(self, source_code: str, diagnostics: DiagnosticCollector) -> List[Token]:
        tokens: List[Token] = []
        try:
            reader = io.StringIO(source_code).readline
            for tok in py_tokenize.generate_tokens(reader):
                tok_type = tok.type
                tok_str = tok.string
                start_line, start_col = tok.start
                end_line, end_col = tok.end

                if tok_type in (py_tokenize.ENCODING, py_tokenize.ENDMARKER):
                    continue

                category = "Special"
                t_type = TokenType.IDENTIFIER
                val = tok_str

                if tok_type == py_tokenize.NAME:
                    if tok_str in ("def", "if", "elif", "else", "while", "for", "return", "in", "and", "or", "not", "print"):
                        category = "Keyword"
                        t_type = TokenType.KW_IF
                    elif tok_str in ("True", "False"):
                        category = "Literal"
                        t_type = TokenType.LIT_BOOL
                        val = (tok_str == "True")
                    else:
                        category = "Identifier"
                        t_type = TokenType.IDENTIFIER

                elif tok_type == py_tokenize.NUMBER:
                    category = "Literal"
                    if "." in tok_str:
                        t_type = TokenType.LIT_FLOAT
                        val = float(tok_str)
                    else:
                        t_type = TokenType.LIT_INT
                        val = int(tok_str)

                elif tok_type == py_tokenize.STRING:
                    category = "Literal"
                    t_type = TokenType.LIT_STRING
                    val = tok_str.strip("'\"")

                elif tok_type == py_tokenize.OP:
                    if tok_str in ("+", "-", "*", "/", "%", "=", "==", "!=", "<", ">", "<=", ">="):
                        category = "Operator"
                        t_type = TokenType.PLUS
                    else:
                        category = "Delimiter"
                        t_type = TokenType.SEMICOLON

                elif tok_type in (py_tokenize.INDENT, py_tokenize.DEDENT):
                    category = "Delimiter"
                    t_type = TokenType.LBRACE if tok_type == py_tokenize.INDENT else TokenType.RBRACE
                    tok_str = "INDENT" if tok_type == py_tokenize.INDENT else "DEDENT"

                tokens.append(Token(
                    type=t_type,
                    value=val,
                    lexeme=tok_str,
                    line=start_line,
                    column=start_col + 1,
                    end_column=end_col + 1
                ))
        except Exception as e:
            diagnostics.add(
                stage=ErrorStage.LEXICAL,
                code="LEX-PY-001",
                message=f"Python Tokenizer Error: {str(e)}",
                line=1,
                column=1
            )
        return tokens

    def parse(self, tokens: List[Token], source_code: str, diagnostics: DiagnosticCollector) -> Tuple[Program, ConcreteParseTreeNode]:
        cst_root = ConcreteParseTreeNode("<PythonProgram>")
        try:
            py_tree = ast.parse(source_code)
            transformer = PythonASTTransformer(diagnostics)
            universal_ast = transformer.transform(py_tree)

            # Build CST representation
            for node in py_tree.body:
                child_cst = ConcreteParseTreeNode(f"<{type(node).__name__}>")
                cst_root.add_child(child_cst)

            return universal_ast, cst_root

        except SyntaxError as e:
            diagnostics.add(
                stage=ErrorStage.SYNTACTIC,
                code="SYN-PY-001",
                message=f"Python SyntaxError: {e.msg}",
                line=e.lineno or 1,
                column=e.offset or 1,
                suggestion="Check indentation, colons (':'), and syntax structure."
            )
            return Program(line=1, column=1, statements=[]), cst_root
