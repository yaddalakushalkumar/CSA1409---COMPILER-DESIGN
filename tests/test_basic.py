import unittest
from compiler import CompilerPipeline


class TestCompilerPipeline(unittest.TestCase):
    def setUp(self):
        self.pipeline = CompilerPipeline()

    def test_arithmetic_and_output(self):
        code = """
        int x = 10;
        int y = 20;
        int sum = x + y * 2;
        println(sum);
        """
        result = self.pipeline.compile(code)
        self.assertFalse(result["has_errors"])
        self.assertEqual(len(result["diagnostics"]), 0)
        self.assertIn("50\n", result["execution"]["stdout"])
        self.assertEqual(result["execution"]["variables"]["sum"], 50)

    def test_control_flow(self):
        code = """
        int count = 0;
        int i = 0;
        while (i < 5) {
            count = count + i;
            i = i + 1;
        }
        println(count);
        """
        result = self.pipeline.compile(code)
        self.assertFalse(result["has_errors"])
        self.assertIn("10\n", result["execution"]["stdout"])
        self.assertEqual(result["execution"]["variables"]["count"], 10)

    def test_for_loop(self):
        code = """
        int fact = 1;
        for (int n = 1; n <= 5; n = n + 1) {
            fact = fact * n;
        }
        println(fact);
        """
        result = self.pipeline.compile(code)
        self.assertFalse(result["has_errors"])
        self.assertIn("120\n", result["execution"]["stdout"])
        self.assertEqual(result["execution"]["variables"]["fact"], 120)

    def test_lexical_error_detection(self):
        code = """
        int a = 10;
        int @bad = 20;
        """
        result = self.pipeline.compile(code)
        self.assertTrue(result["has_errors"])
        lex_errors = [d for d in result["diagnostics"] if d["stage"] == "LEXICAL"]
        self.assertTrue(len(lex_errors) > 0)
        self.assertIn("Illegal character '@'", lex_errors[0]["message"])

    def test_syntax_error_detection(self):
        code = """
        int a = 10
        int b = 20;
        """
        result = self.pipeline.compile(code)
        self.assertTrue(result["has_errors"])
        syn_errors = [d for d in result["diagnostics"] if d["stage"] == "SYNTACTIC"]
        self.assertTrue(len(syn_errors) > 0)
        self.assertIn("Expected ';'", syn_errors[0]["message"])

    def test_semantic_error_detection(self):
        code = """
        int a = 10;
        int a = 20;
        b = 30;
        """
        result = self.pipeline.compile(code)
        self.assertTrue(result["has_errors"])
        sem_errors = [d for d in result["diagnostics"] if d["stage"] == "SEMANTIC"]
        self.assertTrue(len(sem_errors) >= 2)
        messages = [e["message"] for e in sem_errors]
        self.assertTrue(any("Redeclaration of variable 'a'" in m for m in messages))
        self.assertTrue(any("Undeclared identifier 'b'" in m for m in messages))

    def test_type_mismatch_error(self):
        code = """
        int a = "hello";
        """
        result = self.pipeline.compile(code)
        self.assertTrue(result["has_errors"])
        sem_errors = [d for d in result["diagnostics"] if d["stage"] == "SEMANTIC"]
        self.assertTrue(any("Type mismatch" in m for m in [e["message"] for e in sem_errors]))


if __name__ == "__main__":
    unittest.main()
