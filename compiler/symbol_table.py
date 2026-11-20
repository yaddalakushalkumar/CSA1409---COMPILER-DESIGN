"""
symbol_table.py - Hierarchical Symbol Table and Scope Management
Maintains nested lexical scopes, variable/function symbol bindings,
data types, scope depths, and memory offset tracking.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class SymbolKind(str, Enum):
    VARIABLE = "VARIABLE"
    PARAMETER = "PARAMETER"
    FUNCTION = "FUNCTION"


@dataclass
class Symbol:
    name: str
    symbol_type: str
    kind: SymbolKind
    line: int
    column: int
    scope_id: int
    scope_name: str
    offset: int = 0
    initialized: bool = False
    param_types: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.symbol_type,
            "kind": self.kind.value,
            "line": self.line,
            "column": self.column,
            "scope_id": self.scope_id,
            "scope_name": self.scope_name,
            "offset": self.offset,
            "initialized": self.initialized,
            "param_types": self.param_types or [],
        }


class Scope:
    """Represents a lexical scope in the hierarchical symbol table."""

    def __init__(self, scope_id: int, name: str, parent: Optional['Scope'] = None, depth: int = 0):
        self.scope_id = scope_id
        self.name = name
        self.parent = parent
        self.depth = depth
        self.symbols: Dict[str, Symbol] = {}
        self.children: List['Scope'] = []
        self.current_offset = 0

    def define(self, symbol: Symbol) -> bool:
        """Defines symbol in current scope. Returns False if already defined in THIS scope."""
        if symbol.name in self.symbols:
            return False
        symbol.offset = self.current_offset
        self.current_offset += 4  # Standard 4-byte slot allocation
        self.symbols[symbol.name] = symbol
        return True

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def lookup(self, name: str) -> Optional[Symbol]:
        """Resolves symbol upwards through enclosing scopes."""
        curr = self
        while curr is not None:
            if name in curr.symbols:
                return curr.symbols[name]
            curr = curr.parent
        return None

    def get_all_symbols_in_hierarchy(self) -> List[Symbol]:
        res = list(self.symbols.values())
        for c in self.children:
            res.extend(c.get_all_symbols_in_hierarchy())
        return res

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.scope_id,
            "name": self.name,
            "depth": self.depth,
            "symbols": [s.to_dict() for s in self.symbols.values()],
            "children": [c.to_dict() for c in self.children],
        }


class SymbolTable:
    """Manages the lifecycle of nested scopes during semantic analysis."""

    def __init__(self):
        self.scope_counter = 0
        self.root_scope = Scope(self.scope_counter, "Global", None, 0)
        self.current_scope = self.root_scope
        self.all_scopes: List[Scope] = [self.root_scope]

        # Register built-in standard library functions
        self._register_builtins()

    def _register_builtins(self):
        builtins = [
            ("print", "void", ["any"]),
            ("println", "void", ["any"]),
            ("printf", "void", ["any"]),
            ("readInt", "int", []),
            ("readFloat", "float", []),
        ]
        for name, ret_type, params in builtins:
            sym = Symbol(
                name=name,
                symbol_type=ret_type,
                kind=SymbolKind.FUNCTION,
                line=0,
                column=0,
                scope_id=0,
                scope_name="Global",
                param_types=params,
                initialized=True,
            )
            self.root_scope.define(sym)

    def enter_scope(self, name: str) -> Scope:
        self.scope_counter += 1
        new_scope = Scope(
            scope_id=self.scope_counter,
            name=name,
            parent=self.current_scope,
            depth=self.current_scope.depth + 1
        )
        self.current_scope.children.append(new_scope)
        self.all_scopes.append(new_scope)
        self.current_scope = new_scope
        return new_scope

    def exit_scope(self) -> Optional[Scope]:
        if self.current_scope.parent is not None:
            self.current_scope = self.current_scope.parent
        return self.current_scope

    def define(self, symbol: Symbol) -> bool:
        return self.current_scope.define(symbol)

    def lookup(self, name: str) -> Optional[Symbol]:
        return self.current_scope.lookup(name)

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self.current_scope.lookup_local(name)

    def get_all_symbols(self) -> List[Dict[str, Any]]:
        symbols = []
        for scope in self.all_scopes:
            for s in scope.symbols.values():
                symbols.append(s.to_dict())
        return symbols

    def get_all_identifier_names(self) -> List[str]:
        names = set()
        for scope in self.all_scopes:
            names.update(scope.symbols.keys())
        return list(names)
