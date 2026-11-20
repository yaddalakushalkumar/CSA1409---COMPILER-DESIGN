"""
icg.py - Intermediate Code Generator (Three-Address Code & Quadruples)
Generates linear, machine-independent Three-Address Code (TAC) with
temporary variable allocation, label management, and quadruple listings.
"""

from dataclasses import dataclass
from typing import List, Optional, Any, Dict
from .ast_nodes import (
    ASTNode, Program, VarDecl, AssignStmt, Block, IfStmt, WhileStmt,
    ForStmt, FunctionDecl, ReturnStmt, PrintStmt, ExprStmt,
    BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, CallExpr, InputExpr
)


@dataclass
class Quadruple:
    op: str
    arg1: Optional[str] = None
    arg2: Optional[str] = None
    result: Optional[str] = None
    comment: Optional[str] = None

    def to_text(self) -> str:
        if self.op == "label":
            return f"{self.result}:"
        elif self.op == "=":
            return f"{self.result} = {self.arg1}"
        elif self.op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        elif self.op in ("unary-", "!"):
            op_sym = "-" if self.op == "unary-" else "!"
            return f"{self.result} = {op_sym}{self.arg1}"
        elif self.op == "goto":
            return f"goto {self.result}"
        elif self.op == "if_false":
            return f"if_false {self.arg1} goto {self.result}"
        elif self.op == "if_true":
            return f"if {self.arg1} goto {self.result}"
        elif self.op == "param":
            return f"param {self.arg1}"
        elif self.op == "call":
            if self.result:
                return f"{self.result} = call {self.arg1}, {self.arg2}"
            return f"call {self.arg1}, {self.arg2}"
        elif self.op == "return":
            if self.arg1 is not None:
                return f"return {self.arg1}"
            return "return"
        elif self.op in ("print", "println"):
            return f"{self.op} {self.arg1}"
        elif self.op == "readInt":
            return f"{self.result} = readInt()"
        elif self.op == "readFloat":
            return f"{self.result} = readFloat()"
        elif self.op == "func_begin":
            params = f"({self.arg1})" if self.arg1 else "()"
            return f"\n--- {self.result}{params} BEGIN ---"
        elif self.op == "func_end":
            return f"--- {self.result}() END ---\n"
        return f"{self.op} {self.arg1 or ''} {self.arg2 or ''} {self.result or ''}".strip()

    def to_dict(self, index: int = 0) -> Dict[str, Any]:
        return {
            "index": index,
            "op": self.op,
            "arg1": str(self.arg1) if self.arg1 is not None else "",
            "arg2": str(self.arg2) if self.arg2 is not None else "",
            "result": str(self.result) if self.result is not None else "",
            "text": self.to_text(),
            "comment": self.comment or "",
        }


class IntermediateCodeGenerator:
    """Walks the decorated AST and emits Three-Address Code."""

    def __init__(self):
        self.instructions: List[Quadruple] = []
        self.temp_counter = 0
        self.label_counter = 0

    def new_temp(self) -> str:
        self.temp_counter += 1
        return f"_t{self.temp_counter}"

    def new_label(self) -> str:
        self.label_counter += 1
        return f"L{self.label_counter}"

    def emit(self, op: str, arg1: Any = None, arg2: Any = None, result: Any = None, comment: Optional[str] = None) -> Quadruple:
        q = Quadruple(op=op, arg1=str(arg1) if arg1 is not None else None,
                      arg2=str(arg2) if arg2 is not None else None,
                      result=str(result) if result is not None else None,
                      comment=comment)
        self.instructions.append(q)
        return q

    def generate(self, program: Program) -> List[Quadruple]:
        self.instructions = []
        self.temp_counter = 0
        self.label_counter = 0

        for stmt in program.statements:
            self.visit_stmt(stmt)

        return self.instructions

    def visit_stmt(self, node: ASTNode):
        method_name = f"visit_{node.__class__.__name__}"
        visitor = getattr(self, method_name, None)
        if visitor:
            visitor(node)

    def visit_VarDecl(self, node: VarDecl):
        if node.initializer:
            val_reg = self.visit_expr(node.initializer)
            self.emit("=", arg1=val_reg, result=node.name, comment=f"Init {node.name}")

    def visit_AssignStmt(self, node: AssignStmt):
        val_reg = self.visit_expr(node.value) if node.value else "0"
        if node.operator == "=":
            self.emit("=", arg1=val_reg, result=node.name)
        else:
            base_op = node.operator[0]
            temp = self.new_temp()
            self.emit(base_op, arg1=node.name, arg2=val_reg, result=temp)
            self.emit("=", arg1=temp, result=node.name)

    def visit_Block(self, node: Block):
        for s in node.statements:
            self.visit_stmt(s)

    def visit_IfStmt(self, node: IfStmt):
        cond_reg = self.visit_expr(node.condition) if node.condition else "false"
        label_else = self.new_label()
        label_end = self.new_label()

        if node.else_branch:
            self.emit("if_false", arg1=cond_reg, result=label_else)
            if node.then_branch:
                self.visit_stmt(node.then_branch)
            self.emit("goto", result=label_end)
            self.emit("label", result=label_else)
            self.visit_stmt(node.else_branch)
            self.emit("label", result=label_end)
        else:
            self.emit("if_false", arg1=cond_reg, result=label_else)
            if node.then_branch:
                self.visit_stmt(node.then_branch)
            self.emit("label", result=label_else)

    def visit_WhileStmt(self, node: WhileStmt):
        label_start = self.new_label()
        label_end = self.new_label()

        self.emit("label", result=label_start)
        cond_reg = self.visit_expr(node.condition) if node.condition else "false"
        self.emit("if_false", arg1=cond_reg, result=label_end)

        if node.body:
            self.visit_stmt(node.body)

        self.emit("goto", result=label_start)
        self.emit("label", result=label_end)

    def visit_ForStmt(self, node: ForStmt):
        label_start = self.new_label()
        label_end = self.new_label()

        if node.init:
            self.visit_stmt(node.init)

        self.emit("label", result=label_start)
        if node.condition:
            cond_reg = self.visit_expr(node.condition)
            self.emit("if_false", arg1=cond_reg, result=label_end)

        if node.body:
            self.visit_stmt(node.body)

        if node.update:
            self.visit_stmt(node.update)

        self.emit("goto", result=label_start)
        self.emit("label", result=label_end)

    def visit_FunctionDecl(self, node: FunctionDecl):
        skip_label = self.new_label()
        self.emit("goto", result=skip_label, comment=f"Skip {node.name}() during sequential execution")
        param_names = [p["name"] for p in node.params]
        self.emit("func_begin", arg1=",".join(param_names), result=node.name)
        if node.body:
            self.visit_stmt(node.body)
        self.emit("func_end", result=node.name)
        self.emit("label", result=skip_label)

    def visit_ReturnStmt(self, node: ReturnStmt):
        if node.value:
            val_reg = self.visit_expr(node.value)
            self.emit("return", arg1=val_reg)
        else:
            self.emit("return")

    def visit_PrintStmt(self, node: PrintStmt):
        val_reg = self.visit_expr(node.expression) if node.expression else '""'
        op = "println" if node.is_newline else "print"
        self.emit(op, arg1=val_reg)

    def visit_ExprStmt(self, node: ExprStmt):
        if node.expression:
            self.visit_expr(node.expression)

    # ==========================================
    # Expressions -> Produces value/temp register
    # ==========================================

    def visit_expr(self, node: ASTNode) -> str:
        method_name = f"visit_expr_{node.__class__.__name__}"
        visitor = getattr(self, method_name, None)
        if visitor:
            return visitor(node)
        return "0"

    def visit_expr_BinaryExpr(self, node: BinaryExpr) -> str:
        left_reg = self.visit_expr(node.left) if node.left else "0"
        right_reg = self.visit_expr(node.right) if node.right else "0"
        temp = self.new_temp()
        self.emit(node.operator, arg1=left_reg, arg2=right_reg, result=temp)
        return temp

    def visit_expr_UnaryExpr(self, node: UnaryExpr) -> str:
        operand_reg = self.visit_expr(node.operand) if node.operand else "0"
        temp = self.new_temp()
        op = "unary-" if node.operator == "-" else "!"
        self.emit(op, arg1=operand_reg, result=temp)
        return temp

    def visit_expr_LiteralExpr(self, node: LiteralExpr) -> str:
        if node.lit_type == "string":
            return f'"{node.value}"'
        elif node.lit_type == "bool":
            return "true" if node.value else "false"
        return str(node.value)

    def visit_expr_VariableExpr(self, node: VariableExpr) -> str:
        return node.name

    def visit_expr_CallExpr(self, node: CallExpr) -> str:
        arg_regs = [self.visit_expr(arg) for arg in node.args]
        for a in arg_regs:
            self.emit("param", arg1=a)
        temp = self.new_temp()
        self.emit("call", arg1=node.callee, arg2=str(len(arg_regs)), result=temp)
        return temp

    def visit_expr_InputExpr(self, node: InputExpr) -> str:
        temp = self.new_temp()
        op = "readInt" if node.input_type == "int" else "readFloat"
        self.emit(op, result=temp)
        return temp
