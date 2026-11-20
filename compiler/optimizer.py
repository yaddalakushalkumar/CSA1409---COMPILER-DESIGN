"""
optimizer.py - Middle-End Code Optimizer
Applies multi-pass optimizations on Three-Address Code:
1. Constant Folding (evaluates compile-time constant arithmetic and logic)
2. Constant Propagation (substitutes constant values forward)
3. Dead Code Elimination (removes unreachable instructions and unused temporaries)
4. Redundant Jump Removal (eliminates jumps to immediately adjacent labels)
Generates before-and-after optimization metrics and transformation logs.
"""

from typing import List, Dict, Any, Tuple, Optional
from .icg import Quadruple
import copy


class CodeOptimizer:
    """Optimizes Three-Address Code and records transformation provenance."""

    def __init__(self):
        self.logs: List[Dict[str, str]] = []

    def optimize(self, instructions: List[Quadruple]) -> Tuple[List[Quadruple], List[Dict[str, str]], Dict[str, Any]]:
        self.logs = []
        original_count = len(instructions)
        current = copy.deepcopy(instructions)

        max_passes = 5
        for pass_num in range(max_passes):
            changed = False

            # Pass 1: Constant Folding
            current, c_folded = self._constant_folding(current)
            if c_folded:
                changed = True

            # Pass 2: Constant Propagation
            current, c_prop = self._constant_propagation(current)
            if c_prop:
                changed = True

            # Pass 3: Redundant Jump Elimination
            current, c_jumps = self._remove_redundant_jumps(current)
            if c_jumps:
                changed = True

            # Pass 4: Unreachable Code Elimination
            current, c_dead = self._remove_unreachable_code(current)
            if c_dead:
                changed = True

            if not changed:
                break

        optimized_count = len(current)
        reduction = 0.0
        if original_count > 0:
            reduction = round(((original_count - optimized_count) / original_count) * 100, 1)

        metrics = {
            "original_instructions": original_count,
            "optimized_instructions": optimized_count,
            "instructions_eliminated": original_count - optimized_count,
            "reduction_percentage": f"{reduction}%",
            "optimizations_applied": len(self.logs),
        }

        return current, self.logs, metrics

    def _is_number(self, val: Optional[str]) -> bool:
        if val is None:
            return False
        try:
            float(val)
            return True
        except ValueError:
            return False

    def _eval_binary(self, op: str, a: str, b: str) -> Optional[str]:
        try:
            if a in ("true", "false") or b in ("true", "false"):
                val_a = True if a == "true" else False if a == "false" else None
                val_b = True if b == "true" else False if b == "false" else None
                if val_a is not None and val_b is not None:
                    if op == "&&":
                        return "true" if (val_a and val_b) else "false"
                    if op == "||":
                        return "true" if (val_a or val_b) else "false"
                    if op == "==":
                        return "true" if (val_a == val_b) else "false"
                    if op == "!=":
                        return "true" if (val_a != val_b) else "false"
                return None

            if not (self._is_number(a) and self._is_number(b)):
                return None

            num_a = float(a) if "." in a else int(a)
            num_b = float(b) if "." in b else int(b)

            if op == "+":
                res = num_a + num_b
            elif op == "-":
                res = num_a - num_b
            elif op == "*":
                res = num_a * num_b
            elif op == "/":
                if num_b == 0:
                    return None
                res = num_a / num_b if (isinstance(num_a, float) or isinstance(num_b, float)) else num_a // num_b
            elif op == "%":
                if num_b == 0:
                    return None
                res = num_a % num_b
            elif op == "==":
                return "true" if num_a == num_b else "false"
            elif op == "!=":
                return "true" if num_a != num_b else "false"
            elif op == "<":
                return "true" if num_a < num_b else "false"
            elif op == "<=":
                return "true" if num_a <= num_b else "false"
            elif op == ">":
                return "true" if num_a > num_b else "false"
            elif op == ">=":
                return "true" if num_a >= num_b else "false"
            else:
                return None

            return str(res)
        except Exception:
            return None

    def _constant_folding(self, instructions: List[Quadruple]) -> Tuple[List[Quadruple], bool]:
        new_insts = []
        changed = False

        for q in instructions:
            if q.op in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
                folded = self._eval_binary(q.op, q.arg1, q.arg2)
                if folded is not None:
                    orig_text = q.to_text()
                    new_q = Quadruple(op="=", arg1=folded, result=q.result, comment="Constant Folded")
                    new_insts.append(new_q)
                    self.logs.append({
                        "pass": "Constant Folding",
                        "original": orig_text,
                        "optimized": new_q.to_text(),
                        "details": f"Evaluated '{q.arg1} {q.op} {q.arg2}' to '{folded}' at compile time."
                    })
                    changed = True
                    continue

            new_insts.append(q)
        return new_insts, changed

    def _constant_propagation(self, instructions: List[Quadruple]) -> Tuple[List[Quadruple], bool]:
        new_insts = []
        changed = False
        const_map: Dict[str, str] = {}

        for q in instructions:
            if q.op in ("label", "func_begin", "func_end", "call"):
                const_map.clear()

            arg1 = q.arg1
            if arg1 and arg1 in const_map:
                arg1 = const_map[arg1]
                changed = True

            arg2 = q.arg2
            if arg2 and arg2 in const_map:
                arg2 = const_map[arg2]
                changed = True

            new_q = Quadruple(op=q.op, arg1=arg1, arg2=arg2, result=q.result, comment=q.comment)
            new_insts.append(new_q)

            if q.op == "=" and q.result and q.result.startswith("_t"):
                if self._is_number(arg1) or arg1 in ("true", "false"):
                    const_map[q.result] = arg1

            if q.result and q.result in const_map and q.op != "=":
                del const_map[q.result]

        return new_insts, changed

    def _remove_redundant_jumps(self, instructions: List[Quadruple]) -> Tuple[List[Quadruple], bool]:
        new_insts = []
        changed = False
        i = 0
        n = len(instructions)

        while i < n:
            q = instructions[i]
            if q.op == "goto" and (i + 1) < n:
                next_q = instructions[i + 1]
                if next_q.op == "label" and next_q.result == q.result:
                    self.logs.append({
                        "pass": "Redundant Jump Removal",
                        "original": q.to_text(),
                        "optimized": "(Eliminated)",
                        "details": f"Removed unnecessary jump to immediately following label '{q.result}:'."
                    })
                    changed = True
                    i += 1
                    continue

            new_insts.append(q)
            i += 1

        return new_insts, changed

    def _remove_unreachable_code(self, instructions: List[Quadruple]) -> Tuple[List[Quadruple], bool]:
        new_insts = []
        changed = False
        unreachable = False
        in_function = False

        for q in instructions:
            # Function definitions are callable and never dead code from top-level perspective
            if q.op == "func_begin":
                in_function = True
                unreachable = False

            if q.op == "label":
                unreachable = False

            if not unreachable:
                new_insts.append(q)
            elif q.op in ("label", "func_begin", "func_end"):
                new_insts.append(q)
            else:
                self.logs.append({
                    "pass": "Dead Code Elimination",
                    "original": q.to_text(),
                    "optimized": "(Removed)",
                    "details": f"Removed unreachable instruction '{q.to_text()}' after unconditional branch/return."
                })
                changed = True

            if q.op in ("goto", "return"):
                unreachable = True

            if q.op == "func_end":
                in_function = False
                unreachable = False

        return new_insts, changed
