"""
semantic.py - Semantic Analyzer & Type Checker
Performs multi-pass / scope-aware semantic analysis, verifies type safety,
detects undeclared variables with fuzzy correction suggestions,
and decorates the AST with resolved types.
"""

from typing import Optional, List
from .ast_nodes import (
    ASTNode, Program, VarDecl, AssignStmt, Block, IfStmt, WhileStmt,
    ForStmt, FunctionDecl, ReturnStmt, PrintStmt, ExprStmt,
    BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, CallExpr, InputExpr
)
from .symbol_table import SymbolTable, Symbol, SymbolKind
from .errors import DiagnosticCollector, ErrorStage, ErrorSeverity


class SemanticAnalyzer:
    """Walks the AST, populates the Symbol Table, checks semantics and types."""

    def __init__(self, diagnostics: Optional[DiagnosticCollector] = None):
        self.diagnostics = diagnostics or DiagnosticCollector()
        self.symbol_table = SymbolTable()
        self.current_function: Optional[FunctionDecl] = None

    def analyze(self, program: Program) -> SymbolTable:
        """Entry point for semantic analysis."""
        self.visit(program)
        return self.symbol_table

    def visit(self, node: ASTNode) -> Optional[str]:
        """Dispatches visit method based on node class name. Returns inferred type."""
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, self.generic_visit)
        return visitor(node)

    def generic_visit(self, node: ASTNode) -> Optional[str]:
        return None

    # ==========================================
    # Declarations & Statements
    # ==========================================

    def visit_Program(self, node: Program):
        for stmt in node.statements:
            self.visit(stmt)
        return None

    def visit_VarDecl(self, node: VarDecl):
        # Check if already declared in this exact scope
        existing = self.symbol_table.lookup_local(node.name)
        if existing:
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-001",
                message=f"Redeclaration of variable '{node.name}' in the same scope. (Previously declared at line {existing.line}).",
                line=node.line,
                column=node.column,
                end_column=node.end_column,
                suggestion=f"Rename '{node.name}' or assign to it without re-declaring its type.",
            )
            return None

        init_type = None
        if node.initializer:
            init_type = self.visit(node.initializer)
            if init_type and not self._types_compatible(node.var_type, init_type):
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-003",
                    message=f"Type mismatch: cannot initialize '{node.var_type}' variable '{node.name}' with expression of type '{init_type}'.",
                    line=node.initializer.line,
                    column=node.initializer.column,
                    end_column=node.initializer.end_column,
                    suggestion=f"Provide an expression that evaluates to '{node.var_type}' or change variable type.",
                )

        # Register in symbol table
        sym = Symbol(
            name=node.name,
            symbol_type=node.var_type,
            kind=SymbolKind.VARIABLE,
            line=node.line,
            column=node.column,
            scope_id=self.symbol_table.current_scope.scope_id,
            scope_name=self.symbol_table.current_scope.name,
            initialized=(node.initializer is not None),
        )
        self.symbol_table.define(sym)
        return None

    def visit_FunctionDecl(self, node: FunctionDecl):
        # Register function symbol in current (enclosing) scope
        existing = self.symbol_table.lookup_local(node.name)
        if existing:
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-001",
                message=f"Redeclaration of function '{node.name}' in current scope.",
                line=node.line,
                column=node.column,
            )
        else:
            param_types = [p["type"] for p in node.params]
            fn_sym = Symbol(
                name=node.name,
                symbol_type=node.return_type,
                kind=SymbolKind.FUNCTION,
                line=node.line,
                column=node.column,
                scope_id=self.symbol_table.current_scope.scope_id,
                scope_name=self.symbol_table.current_scope.name,
                param_types=param_types,
                initialized=True,
            )
            self.symbol_table.define(fn_sym)

        # Enter function scope
        self.symbol_table.enter_scope(f"Function: {node.name}")
        old_fn = self.current_function
        self.current_function = node

        # Register parameters in function scope
        for p in node.params:
            p_sym = Symbol(
                name=p["name"],
                symbol_type=p["type"],
                kind=SymbolKind.PARAMETER,
                line=node.line,
                column=node.column,
                scope_id=self.symbol_table.current_scope.scope_id,
                scope_name=self.symbol_table.current_scope.name,
                initialized=True,
            )
            self.symbol_table.define(p_sym)

        # Visit body statements
        if node.body:
            for s in node.body.statements:
                self.visit(s)

        self.current_function = old_fn
        self.symbol_table.exit_scope()
        return None

    def visit_AssignStmt(self, node: AssignStmt):
        sym = self.symbol_table.lookup(node.name)
        if not sym:
            all_known = self.symbol_table.get_all_identifier_names()
            suggestion = DiagnosticCollector.suggest_similar(node.name, all_known)
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-002",
                message=f"Undeclared identifier '{node.name}'. Variable must be declared before assignment.",
                line=node.line,
                column=node.column,
                end_column=node.end_column,
                suggestion=suggestion or f"Declare '{node.name}' first, e.g. 'int {node.name};'.",
            )
            val_type = self.visit(node.value) if node.value else None
            return None

        val_type = self.visit(node.value) if node.value else None
        if val_type and not self._types_compatible(sym.symbol_type, val_type):
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-003",
                message=f"Cannot assign value of type '{val_type}' to variable '{node.name}' of type '{sym.symbol_type}'.",
                line=node.line,
                column=node.column,
                end_column=node.end_column,
                suggestion=f"Ensure the right-hand expression matches the '{sym.symbol_type}' variable type.",
            )

        sym.initialized = True
        return None

    def visit_Block(self, node: Block):
        self.symbol_table.enter_scope("Block")
        for s in node.statements:
            self.visit(s)
        self.symbol_table.exit_scope()
        return None

    def visit_IfStmt(self, node: IfStmt):
        if node.condition:
            cond_t = self.visit(node.condition)
            if cond_t and cond_t != "bool":
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-004",
                    message=f"If condition must evaluate to 'bool', found '{cond_t}'.",
                    line=node.condition.line,
                    column=node.condition.column,
                    suggestion="Use a boolean or relational expression like (x > 0) or (flag == true).",
                )
        if node.then_branch:
            self.visit(node.then_branch)
        if node.else_branch:
            self.visit(node.else_branch)
        return None

    def visit_WhileStmt(self, node: WhileStmt):
        if node.condition:
            cond_t = self.visit(node.condition)
            if cond_t and cond_t != "bool":
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-004",
                    message=f"While loop condition must evaluate to 'bool', found '{cond_t}'.",
                    line=node.condition.line,
                    column=node.condition.column,
                    suggestion="Ensure the loop condition evaluates to boolean 'true' or 'false'.",
                )
        if node.body:
            self.visit(node.body)
        return None

    def visit_ForStmt(self, node: ForStmt):
        self.symbol_table.enter_scope("ForScope")
        if node.init:
            self.visit(node.init)
        if node.condition:
            cond_t = self.visit(node.condition)
            if cond_t and cond_t != "bool":
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-004",
                    message=f"For loop condition must evaluate to 'bool', found '{cond_t}'.",
                    line=node.condition.line,
                    column=node.condition.column,
                )
        if node.update:
            self.visit(node.update)
        if node.body:
            self.visit(node.body)
        self.symbol_table.exit_scope()
        return None

    def visit_ReturnStmt(self, node: ReturnStmt):
        ret_val_type = "void"
        if node.value:
            ret_val_type = self.visit(node.value) or "void"

        if not self.current_function:
            # Top-level return
            return None

        expected_type = self.current_function.return_type
        if expected_type == "void" and node.value is not None:
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-005",
                message=f"Void function '{self.current_function.name}' should not return a value.",
                line=node.line,
                column=node.column,
                suggestion="Use 'return;' without an expression.",
            )
        elif expected_type != "void" and not self._types_compatible(expected_type, ret_val_type):
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-005",
                message=f"Function '{self.current_function.name}' expects return type '{expected_type}', but returned '{ret_val_type}'.",
                line=node.line,
                column=node.column,
                suggestion=f"Return an expression of type '{expected_type}'.",
            )
        return None

    def visit_PrintStmt(self, node: PrintStmt):
        if node.expression:
            self.visit(node.expression)
        return None

    def visit_ExprStmt(self, node: ExprStmt):
        if node.expression:
            return self.visit(node.expression)
        return None

    # ==========================================
    # Expressions & Type Inference
    # ==========================================

    def visit_BinaryExpr(self, node: BinaryExpr) -> str:
        left_t = self.visit(node.left) if node.left else "unknown"
        right_t = self.visit(node.right) if node.right else "unknown"

        op = node.operator

        # String concatenation
        if op == "+" and (left_t == "string" or right_t == "string"):
            node.inferred_type = "string"
            return "string"

        # Arithmetic operators
        if op in ("+", "-", "*", "/", "%"):
            if left_t in ("int", "float") and right_t in ("int", "float"):
                res_type = "float" if (left_t == "float" or right_t == "float") else "int"
                node.inferred_type = res_type
                return res_type
            else:
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-006",
                    message=f"Operator '{op}' is not supported between types '{left_t}' and '{right_t}'.",
                    line=node.line,
                    column=node.column,
                    suggestion="Arithmetic operators require numeric operands ('int' or 'float').",
                )
                node.inferred_type = "int"
                return "int"

        # Relational comparisons
        if op in ("<", "<=", ">", ">="):
            if left_t in ("int", "float") and right_t in ("int", "float"):
                node.inferred_type = "bool"
                return "bool"
            else:
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-006",
                    message=f"Relational operator '{op}' cannot compare types '{left_t}' and '{right_t}'.",
                    line=node.line,
                    column=node.column,
                    suggestion="Relational comparisons require numeric operands.",
                )
                node.inferred_type = "bool"
                return "bool"

        # Equality
        if op in ("==", "!="):
            node.inferred_type = "bool"
            return "bool"

        # Logical operations
        if op in ("&&", "||"):
            if left_t != "bool" or right_t != "bool":
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-006",
                    message=f"Logical operator '{op}' requires boolean operands, found '{left_t}' and '{right_t}'.",
                    line=node.line,
                    column=node.column,
                    suggestion="Ensure both left and right expressions evaluate to 'bool'.",
                )
            node.inferred_type = "bool"
            return "bool"

        node.inferred_type = "unknown"
        return "unknown"

    def visit_UnaryExpr(self, node: UnaryExpr) -> str:
        op = node.operator
        sub_t = self.visit(node.operand) if node.operand else "unknown"

        if op == "!":
            if sub_t != "bool":
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-006",
                    message=f"Unary '!' operator requires a 'bool' operand, found '{sub_t}'.",
                    line=node.line,
                    column=node.column,
                )
            node.inferred_type = "bool"
            return "bool"
        elif op == "-":
            if sub_t not in ("int", "float"):
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-006",
                    message=f"Unary '-' operator requires a numeric operand, found '{sub_t}'.",
                    line=node.line,
                    column=node.column,
                )
            node.inferred_type = sub_t
            return sub_t

        node.inferred_type = sub_t
        return sub_t

    def visit_LiteralExpr(self, node: LiteralExpr) -> str:
        node.inferred_type = node.lit_type
        return node.lit_type

    def visit_VariableExpr(self, node: VariableExpr) -> str:
        sym = self.symbol_table.lookup(node.name)
        if not sym:
            all_known = self.symbol_table.get_all_identifier_names()
            suggestion = DiagnosticCollector.suggest_similar(node.name, all_known)
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-002",
                message=f"Undeclared identifier '{node.name}'.",
                line=node.line,
                column=node.column,
                suggestion=suggestion or f"Declare '{node.name}' before referencing it.",
            )
            node.inferred_type = "unknown"
            return "unknown"

        if not sym.initialized:
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-007",
                severity=ErrorSeverity.WARNING,
                message=f"Variable '{node.name}' may be uninitialized when read.",
                line=node.line,
                column=node.column,
                suggestion=f"Assign an initial value to '{node.name}' before use.",
            )

        node.inferred_type = sym.symbol_type
        return sym.symbol_type

    def visit_CallExpr(self, node: CallExpr) -> str:
        sym = self.symbol_table.lookup(node.callee)
        if not sym:
            all_known = self.symbol_table.get_all_identifier_names()
            suggestion = DiagnosticCollector.suggest_similar(node.callee, all_known)
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-002",
                message=f"Function '{node.callee}' is not defined.",
                line=node.line,
                column=node.column,
                suggestion=suggestion,
            )
            node.inferred_type = "unknown"
            return "unknown"

        if sym.kind != SymbolKind.FUNCTION:
            self.diagnostics.add(
                stage=ErrorStage.SEMANTIC,
                code="SEM-008",
                message=f"'{node.callee}' is a {sym.kind.value.lower()}, not a callable function.",
                line=node.line,
                column=node.column,
            )
            node.inferred_type = "unknown"
            return "unknown"

        # Check argument count and types
        expected_params = sym.param_types or []
        # Handle built-in variadic like print
        if expected_params != ["any"]:
            if len(node.args) != len(expected_params):
                self.diagnostics.add(
                    stage=ErrorStage.SEMANTIC,
                    code="SEM-009",
                    message=f"Function '{node.callee}' expects {len(expected_params)} arguments, but {len(node.args)} were given.",
                    line=node.line,
                    column=node.column,
                    suggestion=f"Provide exactly {len(expected_params)} arguments.",
                )
            else:
                for idx, (arg, exp_t) in enumerate(zip(node.args, expected_params)):
                    actual_t = self.visit(arg)
                    if actual_t and not self._types_compatible(exp_t, actual_t):
                        self.diagnostics.add(
                            stage=ErrorStage.SEMANTIC,
                            code="SEM-010",
                            message=f"Argument {idx + 1} of '{node.callee}' expects type '{exp_t}', found '{actual_t}'.",
                            line=arg.line,
                            column=arg.column,
                        )
        else:
            for arg in node.args:
                self.visit(arg)

        node.inferred_type = sym.symbol_type
        return sym.symbol_type

    def visit_InputExpr(self, node: InputExpr) -> str:
        node.inferred_type = node.input_type
        return node.input_type

    def _types_compatible(self, target: str, source: str) -> bool:
        if target == source:
            return True
        # Allow implicit widening of int to float
        if target == "float" and source == "int":
            return True
        return False
