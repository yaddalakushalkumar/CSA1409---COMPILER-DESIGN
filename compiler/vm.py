"""
vm.py - Target Virtual Machine & Execution Engine
Executes Three-Address Code with frame stacks, runtime environment tracking,
standard I/O interception, and step-by-step debugger instrumentation.
"""

from typing import List, Dict, Any, Optional, Tuple
from .icg import Quadruple
from .errors import DiagnosticCollector, ErrorStage, ErrorSeverity
import time


class VirtualMachine:
    """Virtual Machine for executing Three-Address Code."""

    def __init__(self, instructions: List[Quadruple], max_steps: int = 20000):
        self.instructions = instructions
        self.max_steps = max_steps
        self.memory: Dict[str, Any] = {}
        self.output: List[str] = []
        self.step_trace: List[Dict[str, Any]] = []
        self.labels: Dict[str, int] = {}
        self.functions: Dict[str, int] = {}
        self.call_stack: List[Tuple[int, Dict[str, Any], Optional[str]]] = []  # (return_pc, old_memory, result_reg)
        self.param_buffer: List[Any] = []
        self._index_labels()

    def _index_labels(self):
        for idx, q in enumerate(self.instructions):
            if q.op == "label" and q.result:
                self.labels[q.result] = idx
            elif q.op == "func_begin" and q.result:
                self.functions[q.result] = idx

    def _resolve(self, val_str: Optional[str]) -> Any:
        if val_str is None:
            return None
        # String literal
        if val_str.startswith('"') and val_str.endswith('"'):
            return val_str[1:-1]
        # Boolean literal
        if val_str == "true":
            return True
        if val_str == "false":
            return False
        # Integer literal
        try:
            return int(val_str)
        except ValueError:
            pass
        # Float literal
        try:
            return float(val_str)
        except ValueError:
            pass
        # Variable or Temporary lookup
        return self.memory.get(val_str, 0)

    def run(self, inputs: Optional[List[Any]] = None) -> Dict[str, Any]:
        """Runs the TAC instructions to completion or step limit."""
        input_queue = list(inputs or [])
        pc = 0
        step_count = 0
        start_time = time.perf_counter()
        runtime_error = None

        n = len(self.instructions)

        while pc < n and step_count < self.max_steps:
            q = self.instructions[pc]
            step_count += 1

            op = q.op

            # Record step state for debugger / UI
            if step_count <= 200:
                self.step_trace.append({
                    "step": step_count,
                    "pc": pc,
                    "instruction": q.to_text(),
                    "memory_snapshot": {k: str(v) for k, v in list(self.memory.items())[-10:]}
                })

            try:
                if op == "label":
                    pc += 1
                    continue

                elif op == "func_begin":
                    # When entered via call, bind arguments to parameters
                    param_names = [p.strip() for p in q.arg1.split(",")] if q.arg1 else []
                    # Parameters were passed into memory by 'call'
                    pc += 1
                    continue

                elif op == "func_end":
                    # Reached end of function without explicit return
                    if self.call_stack:
                        ret_pc, caller_mem, result_reg = self.call_stack.pop()
                        self.memory = caller_mem
                        pc = ret_pc
                    else:
                        pc += 1
                    continue

                elif op == "=":
                    val = self._resolve(q.arg1)
                    if q.result:
                        self.memory[q.result] = val
                    pc += 1

                elif op in ("+", "-", "*", "/", "%"):
                    a = self._resolve(q.arg1)
                    b = self._resolve(q.arg2)
                    res = 0
                    if op == "+":
                        res = a + b
                    elif op == "-":
                        res = a - b
                    elif op == "*":
                        res = a * b
                    elif op == "/":
                        if b == 0:
                            raise ZeroDivisionError(f"Runtime Exception: Division by zero at instruction {pc} ({q.to_text()})")
                        res = a / b if (isinstance(a, float) or isinstance(b, float)) else a // b
                    elif op == "%":
                        if b == 0:
                            raise ZeroDivisionError(f"Runtime Exception: Modulo by zero at instruction {pc} ({q.to_text()})")
                        res = a % b
                    if q.result:
                        self.memory[q.result] = res
                    pc += 1

                elif op in ("==", "!=", "<", "<=", ">", ">="):
                    a = self._resolve(q.arg1)
                    b = self._resolve(q.arg2)
                    if op == "==":
                        res = (a == b)
                    elif op == "!=":
                        res = (a != b)
                    elif op == "<":
                        res = (a < b)
                    elif op == "<=":
                        res = (a <= b)
                    elif op == ">":
                        res = (a > b)
                    elif op == ">=":
                        res = (a >= b)
                    if q.result:
                        self.memory[q.result] = res
                    pc += 1

                elif op in ("&&", "||"):
                    a = bool(self._resolve(q.arg1))
                    b = bool(self._resolve(q.arg2))
                    res = (a and b) if op == "&&" else (a or b)
                    if q.result:
                        self.memory[q.result] = res
                    pc += 1

                elif op in ("unary-", "!"):
                    a = self._resolve(q.arg1)
                    res = -a if op == "unary-" else not bool(a)
                    if q.result:
                        self.memory[q.result] = res
                    pc += 1

                elif op == "goto":
                    target = q.result
                    if target in self.labels:
                        pc = self.labels[target] + 1
                    else:
                        pc += 1

                elif op == "if_false":
                    cond = bool(self._resolve(q.arg1))
                    target = q.result
                    if not cond:
                        if target in self.labels:
                            pc = self.labels[target] + 1
                        else:
                            pc += 1
                    else:
                        pc += 1

                elif op == "if_true":
                    cond = bool(self._resolve(q.arg1))
                    target = q.result
                    if cond:
                        if target in self.labels:
                            pc = self.labels[target] + 1
                        else:
                            pc += 1
                    else:
                        pc += 1

                elif op == "param":
                    val = self._resolve(q.arg1)
                    self.param_buffer.append(val)
                    pc += 1

                elif op == "call":
                    fn_name = q.arg1
                    arg_count = int(q.arg2 or 0)
                    args = self.param_buffer[-arg_count:] if arg_count > 0 else []
                    self.param_buffer = self.param_buffer[:-arg_count] if arg_count > 0 else self.param_buffer

                    if fn_name in self.functions:
                        target_pc = self.functions[fn_name]
                        func_q = self.instructions[target_pc]
                        param_names = [p.strip() for p in func_q.arg1.split(",")] if func_q.arg1 else []

                        # Save caller frame and register to receive return value
                        self.call_stack.append((pc + 1, self.memory, q.result))

                        # Create new activation record inheriting globals but clean locals
                        new_mem = dict(self.memory)
                        for p_name, arg_val in zip(param_names, args):
                            new_mem[p_name] = arg_val

                        self.memory = new_mem
                        pc = target_pc + 1
                    else:
                        pc += 1

                elif op == "return":
                    ret_val = self._resolve(q.arg1) if q.arg1 else None
                    if self.call_stack:
                        ret_pc, caller_mem, result_reg = self.call_stack.pop()
                        self.memory = caller_mem
                        if result_reg and ret_val is not None:
                            self.memory[result_reg] = ret_val
                        pc = ret_pc
                    else:
                        break

                elif op == "print":
                    val = self._resolve(q.arg1)
                    self.output.append(str(val))
                    pc += 1

                elif op == "println":
                    val = self._resolve(q.arg1)
                    self.output.append(str(val) + "\n")
                    pc += 1

                elif op in ("readInt", "readFloat"):
                    in_val = input_queue.pop(0) if input_queue else (0 if op == "readInt" else 0.0)
                    cast_val = int(in_val) if op == "readInt" else float(in_val)
                    if q.result:
                        self.memory[q.result] = cast_val
                    pc += 1

                else:
                    pc += 1

            except Exception as e:
                runtime_error = str(e)
                break

        exec_time_ms = round((time.perf_counter() - start_time) * 1000, 3)

        if step_count >= self.max_steps:
            runtime_error = f"Execution terminated: Exceeded maximum allowed instruction steps ({self.max_steps}). Possible infinite loop."

        user_variables = {
            k: v for k, v in self.memory.items()
            if not k.startswith("_t") and not k.startswith("L")
        }

        return {
            "stdout": "".join(self.output),
            "total_steps": step_count,
            "execution_time_ms": exec_time_ms,
            "variables": user_variables,
            "all_memory": {k: str(v) for k, v in self.memory.items()},
            "trace": self.step_trace,
            "runtime_error": runtime_error,
            "success": runtime_error is None,
        }
