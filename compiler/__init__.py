"""
compiler package - Multi-Language Interactive Visual Compiler System
Supports frontends for C, Python, Java, and C++, converging on a Universal AST,
Hierarchical Symbol Table, Three-Address Code (TAC), Optimizer, and Target VM.
"""

from typing import Dict, Any, Optional, List
from .errors import DiagnosticCollector, ErrorStage
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer
from .icg import IntermediateCodeGenerator
from .optimizer import CodeOptimizer
from .vm import VirtualMachine

from .frontends.c_frontend import CFrontend
from .frontends.python_frontend import PythonFrontend
from .frontends.java_frontend import JavaFrontend
from .frontends.cpp_frontend import CPPFrontend


FRONTENDS = {
    "c": CFrontend(),
    "python": PythonFrontend(),
    "java": JavaFrontend(),
    "cpp": CPPFrontend(),
}


class CompilerPipeline:
    """Orchestrates multi-language parsing and unified middle-end/back-end compilation."""

    def __init__(self):
        self.frontends = FRONTENDS

    def compile(
        self,
        source_code: str,
        language: str = "c",
        execute: bool = True,
        inputs: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        diagnostics = DiagnosticCollector(source_code)
        lang_key = language.lower()
        frontend = self.frontends.get(lang_key, self.frontends["c"])

        # ----------------------------------------------------
        # Stage 1: Lexical Analysis (Language-specific frontend)
        # ----------------------------------------------------
        tokens = frontend.tokenize(source_code, diagnostics)
        token_dicts = [t.to_dict() for t in tokens if t.type.value != "EOF"]

        # ----------------------------------------------------
        # Stage 2: Syntax Analysis (AST + CST)
        # ----------------------------------------------------
        ast_root, cst_root = frontend.parse(tokens, source_code, diagnostics)
        ast_dict = ast_root.to_dict() if ast_root else {}
        cst_dict = cst_root.to_dict() if cst_root else {}

        # ----------------------------------------------------
        # Stage 3: Semantic Analysis & Symbol Table
        # ----------------------------------------------------
        semantic_analyzer = SemanticAnalyzer(diagnostics)
        symbol_table = semantic_analyzer.analyze(ast_root)
        symbol_list = symbol_table.get_all_symbols()
        scope_tree = symbol_table.root_scope.to_dict()

        ast_decorated_dict = ast_root.to_dict() if ast_root else {}

        # ----------------------------------------------------
        # Stage 4: Intermediate Code Generation (TAC)
        # ----------------------------------------------------
        icg = IntermediateCodeGenerator()
        raw_tac = []
        raw_tac_dicts = []
        if not diagnostics.has_errors():
            raw_tac = icg.generate(ast_root)
            raw_tac_dicts = [q.to_dict(idx + 1) for idx, q in enumerate(raw_tac)]

        # ----------------------------------------------------
        # Stage 5: Code Optimization
        # ----------------------------------------------------
        optimizer = CodeOptimizer()
        opt_tac = []
        opt_tac_dicts = []
        opt_logs = []
        opt_metrics = {
            "original_instructions": len(raw_tac),
            "optimized_instructions": len(raw_tac),
            "instructions_eliminated": 0,
            "reduction_percentage": "0.0%",
            "optimizations_applied": 0
        }

        if raw_tac:
            opt_tac, opt_logs, opt_metrics = optimizer.optimize(raw_tac)
            opt_tac_dicts = [q.to_dict(idx + 1) for idx, q in enumerate(opt_tac)]

        # ----------------------------------------------------
        # Stage 6: Virtual Machine Execution
        # ----------------------------------------------------
        execution_result = {
            "stdout": "",
            "total_steps": 0,
            "execution_time_ms": 0.0,
            "variables": {},
            "all_memory": {},
            "trace": [],
            "runtime_error": None,
            "success": False,
        }

        if execute and not diagnostics.has_errors() and opt_tac:
            vm = VirtualMachine(opt_tac)
            execution_result = vm.run(inputs=inputs or [])

        # Pipeline status indicators
        has_lex_err = any(d.stage == ErrorStage.LEXICAL for d in diagnostics.diagnostics)
        has_syn_err = any(d.stage == ErrorStage.SYNTACTIC for d in diagnostics.diagnostics)
        has_sem_err = any(d.stage == ErrorStage.SEMANTIC for d in diagnostics.diagnostics)

        pipeline_status = {
            "lexical": "error" if has_lex_err else "success",
            "syntactic": "error" if has_syn_err else "success",
            "semantic": "error" if has_sem_err else "success",
            "icg": "skipped" if diagnostics.has_errors() else "success",
            "optimizer": "skipped" if diagnostics.has_errors() else "success",
            "vm": "error" if execution_result.get("runtime_error") else ("skipped" if diagnostics.has_errors() else "success"),
        }

        return {
            "language": lang_key,
            "language_name": frontend.display_name,
            "source_code": source_code,
            "pipeline_status": pipeline_status,
            "has_errors": diagnostics.has_errors(),
            "diagnostics": diagnostics.to_list(),
            "tokens": token_dicts,
            "ast": ast_decorated_dict,
            "cst": cst_dict,
            "symbols": symbol_list,
            "scope_tree": scope_tree,
            "raw_tac": raw_tac_dicts,
            "optimized_tac": opt_tac_dicts,
            "optimization_logs": opt_logs,
            "optimization_metrics": opt_metrics,
            "execution": execution_result,
        }
