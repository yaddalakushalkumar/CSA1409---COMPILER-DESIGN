"""
cli.py - Multi-Language Command Line Interface for Visual Compiler System
Supports compiling and executing C, Python, Java, and C++ source code.
"""

import sys
import os
import argparse
import json
from compiler import CompilerPipeline


def print_banner():
    banner = r"""
=============================================================================
   UNIVERSAL MULTI-LANGUAGE VISUAL COMPILER SYSTEM (C, Python, Java, C++)
=============================================================================
"""
    print(banner)


def detect_language(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".py",):
        return "python"
    elif ext in (".java",):
        return "java"
    elif ext in (".cpp", ".hpp", ".cc"):
        return "cpp"
    return "c"


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Language Visual Compiler Pipeline for C, Python, Java, and C++",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="Path to source file (.c, .clite, .py, .java, .cpp)")
    parser.add_argument("--lang", choices=["c", "python", "java", "cpp"], default=None, help="Explicit language frontend")
    parser.add_argument("--tokens", action="store_true", help="Print token stream from Lexical Analysis")
    parser.add_argument("--ast", action="store_true", help="Print Abstract Syntax Tree")
    parser.add_argument("--cst", action="store_true", help="Print Concrete Parse Tree")
    parser.add_argument("--symbols", action="store_true", help="Print Symbol Table and Scopes")
    parser.add_argument("--tac", action="store_true", help="Print Three-Address Code (TAC)")
    parser.add_argument("--optimize", action="store_true", help="Print Optimized TAC & metrics")
    parser.add_argument("--run", action="store_true", help="Execute compiled program in Virtual Machine")
    parser.add_argument("--all", action="store_true", help="Run and display all compilation stages")
    parser.add_argument("--json", action="store_true", help="Output full compilation result in JSON format")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.")
        sys.exit(1)

    lang = args.lang or detect_language(args.file)

    with open(args.file, "r", encoding="utf-8") as f:
        source_code = f.read()

    pipeline = CompilerPipeline()
    result = pipeline.compile(
        source_code=source_code,
        language=lang,
        execute=args.run or args.all or not any([args.tokens, args.ast, args.cst, args.symbols, args.tac, args.optimize])
    )

    if args.json:
        print(json.dumps(result, indent=2))
        return

    print_banner()
    print(f"[*] Compiling Source: {args.file} (Frontend: {result['language_name']})")
    print(f"[*] Total Lines: {len(source_code.splitlines())}\n")

    # Diagnostics
    if result["diagnostics"]:
        print("-----------------------------------------------------------------------------")
        print(f"  DIAGNOSTICS REPORT ({len(result['diagnostics'])} items detected)")
        print("-----------------------------------------------------------------------------")
        for d in result["diagnostics"]:
            sev = d["severity"]
            stage = d["stage"]
            code = d["code"]
            line = d["line"]
            col = d["column"]
            msg = d["message"]
            print(f"[{sev}] {stage} ({code}) at Line {line}, Column {col}: {msg}")
            if d.get("snippet"):
                print(d["snippet"])
            if d.get("suggestion"):
                print(f"  --> Suggestion: {d['suggestion']}")
            print()

    # Stage 1: Tokens
    if args.tokens or args.all:
        print("-----------------------------------------------------------------------------")
        print("  STAGE 1: LEXICAL ANALYSIS (TOKEN STREAM)")
        print("-----------------------------------------------------------------------------")
        print(f"{'TYPE':<18} | {'CATEGORY':<12} | {'LINE:COL':<10} | {'LEXEME'}")
        print("-" * 65)
        for t in result["tokens"][:50]:
            loc = f"{t['line']}:{t['column']}"
            print(f"{t['type']:<18} | {t['category']:<12} | {loc:<10} | {t['lexeme']}")
        if len(result["tokens"]) > 50:
            print(f"... and {len(result['tokens']) - 50} more tokens.")
        print()

    # Stage 2: AST
    if args.ast or args.all:
        print("-----------------------------------------------------------------------------")
        print("  STAGE 2: UNIVERSAL ABSTRACT SYNTAX TREE (AST)")
        print("-----------------------------------------------------------------------------")
        def print_ast_node(node, depth=0):
            indent = "  " * depth
            name = node.get("name", "Node")
            details = node.get("details", "")
            cat = node.get("category", "")
            line = node.get("line", "")
            print(f"{indent}- [{cat}] {name} (Line {line}) {details}")
            for c in node.get("children", []):
                print_ast_node(c, depth + 1)
        if result["ast"]:
            print_ast_node(result["ast"])
        print()

    # Stage 3: Symbols
    if args.symbols or args.all:
        print("-----------------------------------------------------------------------------")
        print("  STAGE 3: SYMBOL TABLE & SCOPES")
        print("-----------------------------------------------------------------------------")
        print(f"{'NAME':<15} | {'TYPE':<10} | {'KIND':<12} | {'SCOPE':<15} | {'LINE'}")
        print("-" * 65)
        for s in result["symbols"]:
            print(f"{s['name']:<15} | {s['type']:<10} | {s['kind']:<12} | {s['scope_name']:<15} | {s['line']}")
        print()

    # Stage 4: TAC
    if args.tac or args.all:
        print("-----------------------------------------------------------------------------")
        print("  STAGE 4: THREE-ADDRESS CODE (UNIFIED IR)")
        print("-----------------------------------------------------------------------------")
        for q in result["raw_tac"]:
            cmt = f"  // {q['comment']}" if q['comment'] else ""
            print(f"{q['index']:3d}:  {q['text']:<35}{cmt}")
        print()

    # Stage 5: Optimization
    if args.optimize or args.all:
        print("-----------------------------------------------------------------------------")
        print("  STAGE 5: OPTIMIZED THREE-ADDRESS CODE")
        print("-----------------------------------------------------------------------------")
        metrics = result["optimization_metrics"]
        print(f"Instructions: {metrics['original_instructions']} -> {metrics['optimized_instructions']} ({metrics['reduction_percentage']} reduction)")
        print(f"Optimizations Applied: {metrics['optimizations_applied']}\n")
        for q in result["optimized_tac"]:
            cmt = f"  // {q['comment']}" if q['comment'] else ""
            print(f"{q['index']:3d}:  {q['text']:<35}{cmt}")
        print()

    # Stage 6: VM Run
    if args.run or args.all or not any([args.tokens, args.ast, args.cst, args.symbols, args.tac, args.optimize]):
        print("-----------------------------------------------------------------------------")
        print("  STAGE 6: TARGET VIRTUAL MACHINE EXECUTION (STDOUT)")
        print("-----------------------------------------------------------------------------")
        exec_res = result["execution"]
        if exec_res.get("stdout"):
            print(exec_res["stdout"].rstrip())
        else:
            print("(No output emitted)")
        print()
        print(f"Execution Status: {'SUCCESS' if exec_res.get('success') else 'FAILED'}")
        print(f"Total Steps: {exec_res.get('total_steps')} | Execution Time: {exec_res.get('execution_time_ms')} ms")
        if exec_res.get("variables"):
            print("Final Memory State:")
            for k, v in exec_res["variables"].items():
                print(f"  {k} = {v}")
        if exec_res.get("runtime_error"):
            print(f"\n[RUNTIME ERROR]: {exec_res['runtime_error']}")
        print("=============================================================================")


if __name__ == "__main__":
    main()
