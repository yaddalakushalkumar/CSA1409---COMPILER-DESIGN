"""
ast_nodes.py - Abstract Syntax Tree (AST) Node Definitions
Provides strongly-typed nodes with line/column coordinates and JSON serialization
for interactive visual graph rendering.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class ASTNode:
    line: int = 1
    column: int = 1
    end_column: int = 1
    inferred_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert node to hierarchical dict for D3 / SVG rendering."""
        raise NotImplementedError


# ==========================================
# Statements & Declarations
# ==========================================

@dataclass
class Program(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": "Program",
            "category": "Root",
            "line": self.line,
            "column": self.column,
            "details": f"{len(self.statements)} top-level declarations",
            "children": [stmt.to_dict() for stmt in self.statements],
        }


@dataclass
class VarDecl(ASTNode):
    var_type: str = "int"
    name: str = ""
    initializer: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.initializer:
            init_d = self.initializer.to_dict()
            init_d["edgeLabel"] = "initial_value"
            children.append(init_d)
        return {
            "name": f"VarDecl: {self.var_type} {self.name}",
            "category": "Declaration",
            "line": self.line,
            "column": self.column,
            "details": f"Type: {self.var_type}, Identifier: {self.name}",
            "children": children,
        }


@dataclass
class AssignStmt(ASTNode):
    name: str = ""
    operator: str = "="
    value: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.value:
            v_dict = self.value.to_dict()
            v_dict["edgeLabel"] = "assigned_value"
            children.append(v_dict)
        return {
            "name": f"Assign: {self.name} {self.operator}",
            "category": "Statement",
            "line": self.line,
            "column": self.column,
            "details": f"Target: {self.name}, Op: {self.operator}",
            "children": children,
        }


@dataclass
class Block(ASTNode):
    statements: List[ASTNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": "Block { }",
            "category": "Scope",
            "line": self.line,
            "column": self.column,
            "details": f"{len(self.statements)} statements",
            "children": [s.to_dict() for s in self.statements],
        }


@dataclass
class IfStmt(ASTNode):
    condition: Optional[ASTNode] = None
    then_branch: Optional[ASTNode] = None
    else_branch: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.condition:
            c_dict = self.condition.to_dict()
            c_dict["edgeLabel"] = "condition"
            children.append(c_dict)
        if self.then_branch:
            t_dict = self.then_branch.to_dict()
            t_dict["edgeLabel"] = "then"
            children.append(t_dict)
        if self.else_branch:
            e_dict = self.else_branch.to_dict()
            e_dict["edgeLabel"] = "else"
            children.append(e_dict)
        return {
            "name": "IfStmt",
            "category": "ControlFlow",
            "line": self.line,
            "column": self.column,
            "details": "Conditional branch",
            "children": children,
        }


@dataclass
class WhileStmt(ASTNode):
    condition: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.condition:
            c = self.condition.to_dict()
            c["edgeLabel"] = "condition"
            children.append(c)
        if self.body:
            b = self.body.to_dict()
            b["edgeLabel"] = "body"
            children.append(b)
        return {
            "name": "WhileLoop",
            "category": "ControlFlow",
            "line": self.line,
            "column": self.column,
            "details": "While loop structure",
            "children": children,
        }


@dataclass
class ForStmt(ASTNode):
    init: Optional[ASTNode] = None
    condition: Optional[ASTNode] = None
    update: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.init:
            i = self.init.to_dict()
            i["edgeLabel"] = "init"
            children.append(i)
        if self.condition:
            c = self.condition.to_dict()
            c["edgeLabel"] = "cond"
            children.append(c)
        if self.update:
            u = self.update.to_dict()
            u["edgeLabel"] = "update"
            children.append(u)
        if self.body:
            b = self.body.to_dict()
            b["edgeLabel"] = "body"
            children.append(b)
        return {
            "name": "ForLoop",
            "category": "ControlFlow",
            "line": self.line,
            "column": self.column,
            "details": "For loop structure",
            "children": children,
        }


@dataclass
class FunctionDecl(ASTNode):
    return_type: str = "void"
    name: str = ""
    params: List[Dict[str, str]] = field(default_factory=list)  # [{"type": "int", "name": "x"}]
    body: Optional[Block] = None

    def to_dict(self) -> Dict[str, Any]:
        param_str = ", ".join(f"{p['type']} {p['name']}" for p in self.params)
        children = []
        if self.body:
            children.append(self.body.to_dict())
        return {
            "name": f"Function: {self.name}({param_str}) -> {self.return_type}",
            "category": "Declaration",
            "line": self.line,
            "column": self.column,
            "details": f"Signature: {self.return_type} {self.name}({param_str})",
            "children": children,
        }


@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.value:
            v = self.value.to_dict()
            v["edgeLabel"] = "return_val"
            children.append(v)
        return {
            "name": "Return",
            "category": "Statement",
            "line": self.line,
            "column": self.column,
            "details": "Return statement",
            "children": children,
        }


@dataclass
class PrintStmt(ASTNode):
    expression: Optional[ASTNode] = None
    is_newline: bool = True

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.expression:
            e = self.expression.to_dict()
            e["edgeLabel"] = "arg"
            children.append(e)
        fn_name = "println" if self.is_newline else "print"
        return {
            "name": f"{fn_name}()",
            "category": "I/O",
            "line": self.line,
            "column": self.column,
            "details": f"Standard output ({fn_name})",
            "children": children,
        }


@dataclass
class ExprStmt(ASTNode):
    expression: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        if self.expression:
            return self.expression.to_dict()
        return {
            "name": "EmptyStmt",
            "category": "Statement",
            "line": self.line,
            "column": self.column,
            "children": [],
        }


# ==========================================
# Expressions
# ==========================================

@dataclass
class BinaryExpr(ASTNode):
    left: Optional[ASTNode] = None
    operator: str = "+"
    right: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.left:
            l = self.left.to_dict()
            l["edgeLabel"] = "left"
            children.append(l)
        if self.right:
            r = self.right.to_dict()
            r["edgeLabel"] = "right"
            children.append(r)
        return {
            "name": f"Op: {self.operator}",
            "category": "Expression",
            "inferred_type": self.inferred_type,
            "line": self.line,
            "column": self.column,
            "details": f"Binary Operator: {self.operator} (Type: {self.inferred_type or 'unknown'})",
            "children": children,
        }


@dataclass
class UnaryExpr(ASTNode):
    operator: str = "-"
    operand: Optional[ASTNode] = None

    def to_dict(self) -> Dict[str, Any]:
        children = []
        if self.operand:
            children.append(self.operand.to_dict())
        return {
            "name": f"Unary: {self.operator}",
            "category": "Expression",
            "inferred_type": self.inferred_type,
            "line": self.line,
            "column": self.column,
            "details": f"Unary Operator: {self.operator}",
            "children": children,
        }


@dataclass
class LiteralExpr(ASTNode):
    value: Any = None
    lit_type: str = "int"

    def to_dict(self) -> Dict[str, Any]:
        disp_val = f'"{self.value}"' if self.lit_type == "string" else str(self.value)
        return {
            "name": f"Lit: {disp_val}",
            "category": "Literal",
            "inferred_type": self.lit_type,
            "line": self.line,
            "column": self.column,
            "details": f"Type: {self.lit_type}, Value: {disp_val}",
            "children": [],
        }


@dataclass
class VariableExpr(ASTNode):
    name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": f"Var: {self.name}",
            "category": "Identifier",
            "inferred_type": self.inferred_type,
            "line": self.line,
            "column": self.column,
            "details": f"Identifier: {self.name} (Type: {self.inferred_type or 'unresolved'})",
            "children": [],
        }


@dataclass
class CallExpr(ASTNode):
    callee: str = ""
    args: List[ASTNode] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": f"Call: {self.callee}()",
            "category": "Expression",
            "inferred_type": self.inferred_type,
            "line": self.line,
            "column": self.column,
            "details": f"Call function '{self.callee}' with {len(self.args)} arguments",
            "children": [a.to_dict() for a in self.args],
        }


@dataclass
class InputExpr(ASTNode):
    input_type: str = "int"  # readInt or readFloat

    def to_dict(self) -> Dict[str, Any]:
        fn = "readInt()" if self.input_type == "int" else "readFloat()"
        return {
            "name": f"Input: {fn}",
            "category": "I/O",
            "inferred_type": self.input_type,
            "line": self.line,
            "column": self.column,
            "details": f"Read input stream as {self.input_type}",
            "children": [],
        }
