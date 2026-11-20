"""
test_multi_language.py - Test suite for Multi-Language Frontends
Validates compilation and execution across C, Python, Java, and C++.
"""

import unittest
from compiler import CompilerPipeline


class TestMultiLanguageFrontends(unittest.TestCase):
    def setUp(self):
        self.pipeline = CompilerPipeline()

    def test_python_compilation(self):
        py_code = """
x = 10
y = 20
total = x + y * 2
print(total)
"""
        res = self.pipeline.compile(py_code, language="python")
        self.assertFalse(res["has_errors"])
        self.assertIn("50\n", res["execution"]["stdout"])
        self.assertEqual(res["execution"]["variables"]["total"], 50)

    def test_java_compilation(self):
        java_code = """
public class Calculator {
    public static void main(String[] args) {
        int a = 15;
        int b = 30;
        int sum = a + b;
        System.out.println(sum);
    }
}
"""
        res = self.pipeline.compile(java_code, language="java")
        self.assertFalse(res["has_errors"])
        self.assertIn("45\n", res["execution"]["stdout"])
        self.assertEqual(res["execution"]["variables"]["sum"], 45)

    def test_cpp_compilation(self):
        cpp_code = """
#include <iostream>
using namespace std;

int width = 7;
int height = 6;
int area = width * height;
cout << area << endl;
"""
        res = self.pipeline.compile(cpp_code, language="cpp")
        self.assertFalse(res["has_errors"])
        self.assertIn("42\n", res["execution"]["stdout"])
        self.assertEqual(res["execution"]["variables"]["area"], 42)

    def test_c_compilation(self):
        c_code = """
#include <stdio.h>
int val = 100 / 5;
println(val);
"""
        res = self.pipeline.compile(c_code, language="c")
        self.assertFalse(res["has_errors"])
        self.assertIn("20\n", res["execution"]["stdout"])
        self.assertEqual(res["execution"]["variables"]["val"], 20)


if __name__ == "__main__":
    unittest.main()
