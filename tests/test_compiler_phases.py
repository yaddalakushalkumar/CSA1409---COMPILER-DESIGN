"""
test_compiler_phases.py - Comprehensive Unit & Integration Test Suite
Validates all compiler stages: Lexer, Parser, AST, Semantic Analyzer,
Three-Address Code (TAC), Optimizer, and Target Virtual Machine.
"""

import unittest
from compiler.lexer import Lexer, TokenType
from compiler.parser import Parser
from compiler.semantic import SemanticAnalyzer
from compiler.icg import IntermediateCodeGenerator
from compiler.optimizer import CodeOptimizer
from compiler.vm import VirtualMachine
from compiler.errors import DiagnosticCollector, ErrorStage
from compiler import CompilerPipeline


class TestLexer(unittest.TestCase):
    def test_token_recognition(self):
        code = 'int count = 42; float rate = 3.14; string msg = "hello"; bool flag = true;'
        diag = DiagnosticCollector(code)
        lexer = Lexer(code, diag)
        tokens = [t for t in lexer.tokenize() if t.type != TokenType.EOF]

        types = [t.type for t in tokens]
        self.assertIn(TokenType.KW_INT, types)
        self.assertIn(TokenType.LIT_INT, types)
        self.assertIn(TokenType.KW_FLOAT, types)
        self.assertIn(TokenType.LIT_FLOAT, types)
        self.assertIn(TokenType.KW_STRING, types)
        self.assertIn(TokenType.LIT_STRING, types)
        self.assertIn(TokenType.KW_BOOL, types)
        self.assertIn(TokenType.LIT_BOOL, types)
        self.assertFalse(diag.has_errors())

    def test_lexical_unclosed_string(self):
        code = 'string s = "unclosed string without end;'
        diag = DiagnosticCollector(code)
        lexer = Lexer(code, diag)
        lexer.tokenize()
        self.assertTrue(diag.has_errors())
        errs = diag.errors_for_stage(ErrorStage.LEXICAL)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].code, "LEX-004")

    def test_lexical_illegal_character(self):
        code = "int #invalid = 5;"
        diag = DiagnosticCollector(code)
        lexer = Lexer(code, diag)
        lexer.tokenize()
        self.assertTrue(diag.has_errors())
        errs = diag.errors_for_stage(ErrorStage.LEXICAL)
        self.assertEqual(errs[0].code, "LEX-002")


class TestParser(unittest.TestCase):
    def test_precedence_parsing(self):
        # 2 + 3 * 4 should be 2 + (3 * 4) = 14, not (2 + 3) * 4 = 20
        code = "int val = 2 + 3 * 4;"
        diag = DiagnosticCollector(code)
        tokens = Lexer(code, diag).tokenize()
        parser = Parser(tokens, diag)
        ast, cst = parser.parse()
        self.assertFalse(diag.has_errors())
        self.assertEqual(len(ast.statements), 1)
        decl = ast.statements[0]
        # Root of init expr should be '+', left '2', right '*'
        self.assertEqual(decl.initializer.operator, "+")
        self.assertEqual(decl.initializer.right.operator, "*")


class TestSemanticAnalyzer(unittest.TestCase):
    def test_fuzzy_did_you_mean(self):
        code = """
        int myLongIdentifier = 100;
        myLongIdentifer = 200;
        """
        diag = DiagnosticCollector(code)
        tokens = Lexer(code, diag).tokenize()
        ast, _ = Parser(tokens, diag).parse()
        SemanticAnalyzer(diag).analyze(ast)
        self.assertTrue(diag.has_errors())
        errs = diag.errors_for_stage(ErrorStage.SEMANTIC)
        self.assertTrue(any("Did you mean 'myLongIdentifier'?" in str(e.suggestion) for e in errs))

    def test_type_compatibility(self):
        code = """
        bool flag = false;
        int num = 10;
        if (num) {
            println(1);
        }
        """
        diag = DiagnosticCollector(code)
        tokens = Lexer(code, diag).tokenize()
        ast, _ = Parser(tokens, diag).parse()
        SemanticAnalyzer(diag).analyze(ast)
        self.assertTrue(diag.has_errors())
        errs = diag.errors_for_stage(ErrorStage.SEMANTIC)
        self.assertTrue(any(e.code == "SEM-004" for e in errs))


class TestOptimizerAndVM(unittest.TestCase):
    def test_constant_folding_and_execution(self):
        code = """
        int a = 10 + 20 * 2;
        int b = 5;
        int c = a + b;
        println(c);
        """
        p = CompilerPipeline()
        res = p.compile(code)
        self.assertFalse(res["has_errors"])
        self.assertIn("55\n", res["execution"]["stdout"])
        # Check optimization metrics
        self.assertTrue(res["optimization_metrics"]["optimizations_applied"] > 0)

    def test_function_execution(self):
        code = """
        int mult(int x, int y) {
            return x * y;
        }
        int ans = mult(6, 7);
        println(ans);
        """
        p = CompilerPipeline()
        res = p.compile(code)
        self.assertFalse(res["has_errors"])
        self.assertIn("42\n", res["execution"]["stdout"])


if __name__ == "__main__":
    unittest.main()
