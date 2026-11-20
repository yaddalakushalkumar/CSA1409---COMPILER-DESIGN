"""
parser.py - Syntax Analyzer (Parser)
Constructs both Concrete Syntax Tree (Parse Tree) and Abstract Syntax Tree (AST),
with robust panic-mode error recovery and context-aware syntax error diagnostics.
"""

from typing import List, Optional, Tuple, Dict, Any
from .lexer import Token, TokenType
from .errors import DiagnosticCollector, ErrorStage, ErrorSeverity
from .ast_nodes import (
    ASTNode, Program, VarDecl, AssignStmt, Block, IfStmt, WhileStmt,
    ForStmt, FunctionDecl, ReturnStmt, PrintStmt, ExprStmt,
    BinaryExpr, UnaryExpr, LiteralExpr, VariableExpr, CallExpr, InputExpr
)


class ConcreteParseTreeNode:
    """Represents a node in the Concrete Syntax Tree (CST)."""

    def __init__(self, name: str, is_terminal: bool = False, token: Optional[Token] = None):
        self.name = name
        self.is_terminal = is_terminal
        self.token = token
        self.children: List['ConcreteParseTreeNode'] = []

    def add_child(self, child: 'ConcreteParseTreeNode'):
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "name": self.name,
            "category": "Terminal" if self.is_terminal else "NonTerminal",
            "children": [c.to_dict() for c in self.children]
        }
        if self.token:
            result["line"] = self.token.line
            result["column"] = self.token.column
            result["lexeme"] = self.token.lexeme
        return result


class Parser:
    """Recursive Descent Parser with Operator Precedence and Error Recovery."""

    def __init__(self, tokens: List[Token], diagnostics: Optional[DiagnosticCollector] = None):
        self.tokens = tokens
        self.diagnostics = diagnostics or DiagnosticCollector()
        self.current = 0
        self.cst_root = ConcreteParseTreeNode("<Program>")

    def peek(self, offset: int = 0) -> Token:
        pos = self.current + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]  # Return EOF

    def is_at_end(self) -> bool:
        return self.peek().type == TokenType.EOF

    def advance(self) -> Token:
        if not self.is_at_end():
            self.current += 1
        return self.tokens[self.current - 1]

    def check(self, token_type: TokenType) -> bool:
        if self.is_at_end():
            return False
        return self.peek().type == token_type

    def match(self, *token_types: TokenType) -> bool:
        for t in token_types:
            if self.check(t):
                self.advance()
                return True
        return False

    def consume(self, token_type: TokenType, error_message: str, suggestion: Optional[str] = None) -> Token:
        if self.check(token_type):
            return self.advance()

        prev = self.tokens[self.current - 1] if self.current > 0 else self.peek()
        curr = self.peek()

        self.diagnostics.add(
            stage=ErrorStage.SYNTACTIC,
            code="SYN-001",
            message=f"{error_message}. Found '{curr.lexeme}'.",
            line=curr.line,
            column=curr.column,
            end_column=curr.end_column,
            suggestion=suggestion or f"Insert '{token_type.value}' here.",
        )
        # Create a synthetic token to attempt recovery
        return Token(
            type=token_type,
            value=token_type.value,
            lexeme=token_type.value,
            line=curr.line,
            column=curr.column,
            end_column=curr.end_column,
        )

    def synchronize(self):
        """Panic-mode recovery: advance until statement boundary."""
        self.advance()
        while not self.is_at_end():
            if self.tokens[self.current - 1].type == TokenType.SEMICOLON:
                return
            if self.peek().type in (
                TokenType.KW_INT, TokenType.KW_FLOAT, TokenType.KW_BOOL,
                TokenType.KW_STRING, TokenType.KW_VOID, TokenType.KW_IF,
                TokenType.KW_WHILE, TokenType.KW_FOR, TokenType.KW_RETURN,
                TokenType.KW_PRINT, TokenType.KW_PRINTLN, TokenType.RBRACE
            ):
                return
            self.advance()

    # ==========================================
    # Parsing Rules
    # ==========================================

    def parse(self) -> Tuple[Program, ConcreteParseTreeNode]:
        """Main entry point. Returns AST Program node and CST Root node."""
        statements: List[ASTNode] = []
        cst_root = ConcreteParseTreeNode("<Program>")

        while not self.is_at_end():
            try:
                stmt, cst_child = self.parse_declaration_or_statement()
                if stmt:
                    statements.append(stmt)
                if cst_child:
                    cst_root.add_child(cst_child)
            except Exception as e:
                # Catch unhandled parse faults to prevent crash and recover
                self.synchronize()

        program_ast = Program(
            line=1,
            column=1,
            end_column=1,
            statements=statements,
        )
        return program_ast, cst_root

    def parse_declaration_or_statement(self) -> Tuple[Optional[ASTNode], Optional[ConcreteParseTreeNode]]:
        # Check for function or variable declaration
        type_tokens = (TokenType.KW_INT, TokenType.KW_FLOAT, TokenType.KW_BOOL, TokenType.KW_STRING, TokenType.KW_VOID)
        if self.peek().type in type_tokens:
            # Look ahead: If `type IDENTIFIER ('(') -> FunctionDecl
            if self.peek(1).type == TokenType.IDENTIFIER and self.peek(2).type == TokenType.LPAREN:
                return self.parse_function_decl()
            elif self.peek().type != TokenType.KW_VOID:
                return self.parse_var_decl()

        return self.parse_statement()

    def parse_var_decl(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<VarDecl>")
        type_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode(f"Type: {type_tok.lexeme}", True, type_tok))

        name_tok = self.consume(
            TokenType.IDENTIFIER,
            "Expected variable identifier name after type declaration",
            "Provide a valid variable name, e.g., 'count' or 'total'."
        )
        cst.add_child(ConcreteParseTreeNode(f"Identifier: {name_tok.lexeme}", True, name_tok))

        initializer = None
        if self.match(TokenType.ASSIGN):
            eq_tok = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode("=", True, eq_tok))
            init_ast, init_cst = self.parse_expression()
            initializer = init_ast
            cst.add_child(init_cst)

        semi_tok = self.consume(
            TokenType.SEMICOLON,
            "Expected ';' after variable declaration",
            "Add ';' at the end of the declaration statement."
        )
        cst.add_child(ConcreteParseTreeNode(";", True, semi_tok))

        ast = VarDecl(
            line=type_tok.line,
            column=type_tok.column,
            end_column=semi_tok.end_column,
            var_type=type_tok.lexeme,
            name=name_tok.lexeme,
            initializer=initializer,
        )
        return ast, cst

    def parse_function_decl(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<FunctionDecl>")
        return_type_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode(f"ReturnType: {return_type_tok.lexeme}", True, return_type_tok))

        name_tok = self.consume(TokenType.IDENTIFIER, "Expected function name")
        cst.add_child(ConcreteParseTreeNode(f"FuncName: {name_tok.lexeme}", True, name_tok))

        lparen = self.consume(TokenType.LPAREN, "Expected '(' after function name")
        cst.add_child(ConcreteParseTreeNode("(", True, lparen))

        params = []
        if not self.check(TokenType.RPAREN):
            while True:
                p_type = self.advance()
                p_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name")
                params.append({"type": p_type.lexeme, "name": p_name.lexeme})
                cst.add_child(ConcreteParseTreeNode(f"Param: {p_type.lexeme} {p_name.lexeme}", True))
                if not self.match(TokenType.COMMA):
                    break

        rparen = self.consume(TokenType.RPAREN, "Expected ')' after parameter list")
        cst.add_child(ConcreteParseTreeNode(")", True, rparen))

        body_ast, body_cst = self.parse_block()
        cst.add_child(body_cst)

        ast = FunctionDecl(
            line=return_type_tok.line,
            column=return_type_tok.column,
            end_column=body_ast.end_column,
            return_type=return_type_tok.lexeme,
            name=name_tok.lexeme,
            params=params,
            body=body_ast,
        )
        return ast, cst

    def parse_statement(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        curr = self.peek()

        if curr.type == TokenType.LBRACE:
            return self.parse_block()
        if curr.type == TokenType.KW_IF:
            return self.parse_if_stmt()
        if curr.type == TokenType.KW_WHILE:
            return self.parse_while_stmt()
        if curr.type == TokenType.KW_FOR:
            return self.parse_for_stmt()
        if curr.type == TokenType.KW_RETURN:
            return self.parse_return_stmt()
        if curr.type in (TokenType.KW_PRINT, TokenType.KW_PRINTLN):
            return self.parse_print_stmt()

        # Check for assignment statement: identifier followed by = or += etc.
        assign_ops = (TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN)
        if curr.type == TokenType.IDENTIFIER and self.peek(1).type in assign_ops:
            return self.parse_assign_stmt()

        # Otherwise expression statement
        return self.parse_expr_stmt()

    def parse_block(self) -> Tuple[Block, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<Block>")
        lbrace = self.consume(TokenType.LBRACE, "Expected '{' to begin block")
        cst.add_child(ConcreteParseTreeNode("{", True, lbrace))

        statements = []
        while not self.check(TokenType.RBRACE) and not self.is_at_end():
            stmt, child_cst = self.parse_declaration_or_statement()
            if stmt:
                statements.append(stmt)
            if child_cst:
                cst.add_child(child_cst)

        rbrace = self.consume(TokenType.RBRACE, "Expected '}' to close block", "Ensure every '{' has a matching '}'.")
        cst.add_child(ConcreteParseTreeNode("}", True, rbrace))

        ast = Block(
            line=lbrace.line,
            column=lbrace.column,
            end_column=rbrace.end_column,
            statements=statements,
        )
        return ast, cst

    def parse_if_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<IfStmt>")
        if_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode("if", True, if_tok))

        lparen = self.consume(TokenType.LPAREN, "Expected '(' after 'if'")
        cond_ast, cond_cst = self.parse_expression()
        cst.add_child(cond_cst)
        rparen = self.consume(TokenType.RPAREN, "Expected ')' after if condition")

        then_ast, then_cst = self.parse_statement()
        cst.add_child(then_cst)

        else_ast = None
        if self.match(TokenType.KW_ELSE):
            else_tok = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode("else", True, else_tok))
            else_ast, else_cst = self.parse_statement()
            cst.add_child(else_cst)

        ast = IfStmt(
            line=if_tok.line,
            column=if_tok.column,
            end_column=else_ast.end_column if else_ast else then_ast.end_column,
            condition=cond_ast,
            then_branch=then_ast,
            else_branch=else_ast,
        )
        return ast, cst

    def parse_while_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<WhileStmt>")
        w_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode("while", True, w_tok))

        self.consume(TokenType.LPAREN, "Expected '(' after 'while'")
        cond_ast, cond_cst = self.parse_expression()
        cst.add_child(cond_cst)
        self.consume(TokenType.RPAREN, "Expected ')' after condition")

        body_ast, body_cst = self.parse_statement()
        cst.add_child(body_cst)

        ast = WhileStmt(
            line=w_tok.line,
            column=w_tok.column,
            end_column=body_ast.end_column,
            condition=cond_ast,
            body=body_ast,
        )
        return ast, cst

    def parse_for_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<ForStmt>")
        f_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode("for", True, f_tok))

        self.consume(TokenType.LPAREN, "Expected '(' after 'for'")

        # Init
        init_ast = None
        if self.match(TokenType.SEMICOLON):
            pass
        elif self.peek().type in (TokenType.KW_INT, TokenType.KW_FLOAT):
            init_ast, init_cst = self.parse_var_decl()
            cst.add_child(init_cst)
        else:
            init_ast, init_cst = self.parse_assign_stmt()
            cst.add_child(init_cst)

        # Cond
        cond_ast = None
        if not self.check(TokenType.SEMICOLON):
            cond_ast, cond_cst = self.parse_expression()
            cst.add_child(cond_cst)
        self.consume(TokenType.SEMICOLON, "Expected ';' after for loop condition")

        # Update
        update_ast = None
        if not self.check(TokenType.RPAREN):
            # Parse assignment or expression without trailing semicolon
            if self.peek().type == TokenType.IDENTIFIER and self.peek(1).type in (
                TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN,
                TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN
            ):
                id_tok = self.advance()
                op_tok = self.advance()
                val_ast, val_cst = self.parse_expression()
                update_ast = AssignStmt(
                    line=id_tok.line,
                    column=id_tok.column,
                    name=id_tok.lexeme,
                    operator=op_tok.lexeme,
                    value=val_ast
                )
            else:
                update_ast, _ = self.parse_expression()

        self.consume(TokenType.RPAREN, "Expected ')' after for clauses")

        body_ast, body_cst = self.parse_statement()
        cst.add_child(body_cst)

        ast = ForStmt(
            line=f_tok.line,
            column=f_tok.column,
            end_column=body_ast.end_column,
            init=init_ast,
            condition=cond_ast,
            update=update_ast,
            body=body_ast,
        )
        return ast, cst

    def parse_return_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<ReturnStmt>")
        ret_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode("return", True, ret_tok))

        val_ast = None
        if not self.check(TokenType.SEMICOLON):
            val_ast, val_cst = self.parse_expression()
            cst.add_child(val_cst)

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after return statement")
        cst.add_child(ConcreteParseTreeNode(";", True, semi))

        ast = ReturnStmt(
            line=ret_tok.line,
            column=ret_tok.column,
            end_column=semi.end_column,
            value=val_ast,
        )
        return ast, cst

    def parse_print_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<PrintStmt>")
        p_tok = self.advance()
        is_nl = (p_tok.type == TokenType.KW_PRINTLN)
        cst.add_child(ConcreteParseTreeNode(p_tok.lexeme, True, p_tok))

        self.consume(TokenType.LPAREN, f"Expected '(' after '{p_tok.lexeme}'")
        expr_ast, expr_cst = self.parse_expression()
        cst.add_child(expr_cst)
        self.consume(TokenType.RPAREN, f"Expected ')' after argument to '{p_tok.lexeme}'")

        semi = self.consume(TokenType.SEMICOLON, f"Expected ';' after '{p_tok.lexeme}' statement")
        cst.add_child(ConcreteParseTreeNode(";", True, semi))

        ast = PrintStmt(
            line=p_tok.line,
            column=p_tok.column,
            end_column=semi.end_column,
            expression=expr_ast,
            is_newline=is_nl,
        )
        return ast, cst

    def parse_assign_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<AssignStmt>")
        name_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode(f"Identifier: {name_tok.lexeme}", True, name_tok))

        op_tok = self.advance()
        cst.add_child(ConcreteParseTreeNode(f"Op: {op_tok.lexeme}", True, op_tok))

        val_ast, val_cst = self.parse_expression()
        cst.add_child(val_cst)

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after assignment")
        cst.add_child(ConcreteParseTreeNode(";", True, semi))

        ast = AssignStmt(
            line=name_tok.line,
            column=name_tok.column,
            end_column=semi.end_column,
            name=name_tok.lexeme,
            operator=op_tok.lexeme,
            value=val_ast,
        )
        return ast, cst

    def parse_expr_stmt(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<ExprStmt>")
        expr_ast, expr_cst = self.parse_expression()
        cst.add_child(expr_cst)

        semi = self.consume(TokenType.SEMICOLON, "Expected ';' after expression")
        cst.add_child(ConcreteParseTreeNode(";", True, semi))

        ast = ExprStmt(
            line=expr_ast.line,
            column=expr_ast.column,
            end_column=semi.end_column,
            expression=expr_ast,
        )
        return ast, cst

    # ==========================================
    # Expression Parsing with Precedence
    # ==========================================

    def parse_expression(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<LogicalOr>")
        left, left_cst = self.parse_logical_and()
        cst.add_child(left_cst)

        while self.match(TokenType.OR):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode("||", True, op))
            right, right_cst = self.parse_logical_and()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator="||",
                right=right,
            )
        return left, cst

    def parse_logical_and(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<LogicalAnd>")
        left, left_cst = self.parse_equality()
        cst.add_child(left_cst)

        while self.match(TokenType.AND):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode("&&", True, op))
            right, right_cst = self.parse_equality()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator="&&",
                right=right,
            )
        return left, cst

    def parse_equality(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<Equality>")
        left, left_cst = self.parse_relational()
        cst.add_child(left_cst)

        while self.match(TokenType.EQ, TokenType.NEQ):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode(op.lexeme, True, op))
            right, right_cst = self.parse_relational()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator=op.lexeme,
                right=right,
            )
        return left, cst

    def parse_relational(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<Relational>")
        left, left_cst = self.parse_additive()
        cst.add_child(left_cst)

        while self.match(TokenType.LT, TokenType.LEQ, TokenType.GT, TokenType.GEQ):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode(op.lexeme, True, op))
            right, right_cst = self.parse_additive()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator=op.lexeme,
                right=right,
            )
        return left, cst

    def parse_additive(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<Additive>")
        left, left_cst = self.parse_multiplicative()
        cst.add_child(left_cst)

        while self.match(TokenType.PLUS, TokenType.MINUS):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode(op.lexeme, True, op))
            right, right_cst = self.parse_multiplicative()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator=op.lexeme,
                right=right,
            )
        return left, cst

    def parse_multiplicative(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        cst = ConcreteParseTreeNode("<Multiplicative>")
        left, left_cst = self.parse_unary()
        cst.add_child(left_cst)

        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self.tokens[self.current - 1]
            cst.add_child(ConcreteParseTreeNode(op.lexeme, True, op))
            right, right_cst = self.parse_unary()
            cst.add_child(right_cst)
            left = BinaryExpr(
                line=left.line,
                column=left.column,
                end_column=right.end_column,
                left=left,
                operator=op.lexeme,
                right=right,
            )
        return left, cst

    def parse_unary(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        if self.match(TokenType.NOT, TokenType.MINUS):
            op = self.tokens[self.current - 1]
            cst = ConcreteParseTreeNode("<Unary>")
            cst.add_child(ConcreteParseTreeNode(op.lexeme, True, op))
            operand, op_cst = self.parse_unary()
            cst.add_child(op_cst)
            ast = UnaryExpr(
                line=op.line,
                column=op.column,
                end_column=operand.end_column,
                operator=op.lexeme,
                operand=operand,
            )
            return ast, cst

        return self.parse_primary()

    def parse_primary(self) -> Tuple[ASTNode, ConcreteParseTreeNode]:
        curr = self.peek()

        # Literals
        if curr.type == TokenType.LIT_INT:
            self.advance()
            return LiteralExpr(line=curr.line, column=curr.column, end_column=curr.end_column, value=curr.value, lit_type="int"), ConcreteParseTreeNode(str(curr.value), True, curr)
        if curr.type == TokenType.LIT_FLOAT:
            self.advance()
            return LiteralExpr(line=curr.line, column=curr.column, end_column=curr.end_column, value=curr.value, lit_type="float"), ConcreteParseTreeNode(str(curr.value), True, curr)
        if curr.type == TokenType.LIT_STRING:
            self.advance()
            return LiteralExpr(line=curr.line, column=curr.column, end_column=curr.end_column, value=curr.value, lit_type="string"), ConcreteParseTreeNode(f'"{curr.value}"', True, curr)
        if curr.type == TokenType.LIT_BOOL:
            self.advance()
            return LiteralExpr(line=curr.line, column=curr.column, end_column=curr.end_column, value=curr.value, lit_type="bool"), ConcreteParseTreeNode(str(curr.value), True, curr)

        # I/O expressions: readInt() or readFloat()
        if curr.type in (TokenType.KW_READ_INT, TokenType.KW_READ_FLOAT):
            fn_tok = self.advance()
            self.consume(TokenType.LPAREN, "Expected '(' after input function")
            self.consume(TokenType.RPAREN, "Expected ')' after input function")
            t = "int" if fn_tok.type == TokenType.KW_READ_INT else "float"
            return InputExpr(line=fn_tok.line, column=fn_tok.column, end_column=fn_tok.end_column + 2, input_type=t), ConcreteParseTreeNode(f"{fn_tok.lexeme}()", True, fn_tok)

        # Identifier or Function Call
        if curr.type == TokenType.IDENTIFIER:
            id_tok = self.advance()
            if self.match(TokenType.LPAREN):
                # Call expression
                args = []
                cst = ConcreteParseTreeNode(f"<CallExpr: {id_tok.lexeme}>")
                if not self.check(TokenType.RPAREN):
                    while True:
                        arg_ast, arg_cst = self.parse_expression()
                        args.append(arg_ast)
                        cst.add_child(arg_cst)
                        if not self.match(TokenType.COMMA):
                            break
                rparen = self.consume(TokenType.RPAREN, f"Expected ')' after argument list for call to '{id_tok.lexeme}'")
                ast = CallExpr(
                    line=id_tok.line,
                    column=id_tok.column,
                    end_column=rparen.end_column,
                    callee=id_tok.lexeme,
                    args=args,
                )
                return ast, cst
            else:
                # Variable expression
                return VariableExpr(line=id_tok.line, column=id_tok.column, end_column=id_tok.end_column, name=id_tok.lexeme), ConcreteParseTreeNode(id_tok.lexeme, True, id_tok)

        # Parenthesized expression
        if self.match(TokenType.LPAREN):
            lp = self.tokens[self.current - 1]
            expr_ast, expr_cst = self.parse_expression()
            rp = self.consume(TokenType.RPAREN, "Expected closing ')' after parenthesized expression")
            return expr_ast, expr_cst

        # Unexpected token
        self.diagnostics.add(
            stage=ErrorStage.SYNTACTIC,
            code="SYN-002",
            message=f"Unexpected token '{curr.lexeme}' in expression.",
            line=curr.line,
            column=curr.column,
            end_column=curr.end_column,
            suggestion="Check expression syntax for missing operands, operators, or mismatched parentheses.",
        )
        self.advance()
        return LiteralExpr(line=curr.line, column=curr.column, end_column=curr.end_column, value=0, lit_type="int"), ConcreteParseTreeNode("<?>", True, curr)
