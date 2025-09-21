from typing import List, Optional
from lexer import Token, TokenType, Lexer
from ast_nodes import *

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]  # Return EOF

    def peek_token(self, offset=1) -> Token:
        pos = self.pos + offset
        if pos < len(self.tokens):
            return self.tokens[pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        token = self.current_token()
        self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        token = self.current_token()
        if token.type != token_type:
            raise SyntaxError(f"Expected {token_type}, got {token.type} at line {token.line}")
        return self.advance()

    def skip_newlines(self):
        while self.current_token().type == TokenType.NEWLINE:
            self.advance()

    def parse(self) -> Program:
        declarations = []
        blocks = []
        main = None

        while self.current_token().type != TokenType.EOF:
            self.skip_newlines()

            if self.current_token().type == TokenType.EOF:
                break

            # Check for main block
            if self.current_token().type == TokenType.MAIN:
                if main is not None:
                    raise SyntaxError("Multiple main blocks defined")
                main = self.parse_main_block()
            # Check for block definitions
            elif self.current_token().type in [TokenType.OS, TokenType.DE, TokenType.FO, TokenType.PARALLEL]:
                blocks.append(self.parse_block())
            # Check for function declarations
            elif self.current_token().type == TokenType.DEF:
                declarations.append(self.parse_function())
            # Check for import statements
            elif self.current_token().type == TokenType.IMPORT:
                declarations.append(self.parse_import())
            elif self.current_token().type == TokenType.FROM:
                declarations.append(self.parse_from_import())
            # Variable declarations or assignments
            elif self.current_token().type == TokenType.IDENTIFIER:
                if self.peek_token().type == TokenType.ASSIGN:
                    declarations.append(self.parse_var_declaration())
                else:
                    raise SyntaxError(f"Unexpected identifier at line {self.current_token().line}")
            else:
                raise SyntaxError(f"Unexpected token {self.current_token().type} at line {self.current_token().line}")

            self.skip_newlines()

        if main is None:
            raise SyntaxError("No main block defined")

        return Program(declarations, blocks, main)

    def parse_main_block(self) -> MainBlock:
        self.expect(TokenType.MAIN)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        body = self.parse_statements()

        self.expect(TokenType.DEDENT)

        return MainBlock("main", body)

    def parse_block(self) -> Block:
        parallel = False
        if self.current_token().type == TokenType.PARALLEL:
            parallel = True
            self.advance()

        block_type = self.current_token().type
        self.advance()

        name_token = self.expect(TokenType.IDENTIFIER)
        name = name_token.value

        # Handle parentheses for all block types (optional for OS/FO, required for DE)
        iterations = None
        if self.current_token().type == TokenType.LPAREN:
            self.advance()
            if block_type == TokenType.DE:
                iterations_token = self.expect(TokenType.NUMBER)
                iterations = int(iterations_token.value)
            self.expect(TokenType.RPAREN)
        elif block_type == TokenType.DE:
            raise SyntaxError(f"DE block '{name}' requires iteration count in parentheses")

        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        body = self.parse_statements()

        self.expect(TokenType.DEDENT)

        if block_type == TokenType.OS:
            return OSBlock(name, body)
        elif block_type == TokenType.DE:
            if parallel:
                return ParallelDEBlock(name, body, iterations)
            return DEBlock(name, body, iterations)
        elif block_type == TokenType.FO:
            if parallel:
                return ParallelFOBlock(name, body)
            return FOBlock(name, body)

    def parse_function(self) -> FuncDeclaration:
        self.expect(TokenType.DEF)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)

        params = []
        while self.current_token().type != TokenType.RPAREN:
            params.append(self.expect(TokenType.IDENTIFIER).value)
            if self.current_token().type == TokenType.COMMA:
                self.advance()

        self.expect(TokenType.RPAREN)
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        body = self.parse_statements()

        self.expect(TokenType.DEDENT)

        return FuncDeclaration(name, params, body)

    def parse_var_declaration(self) -> VarDeclaration:
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        self.skip_newlines()
        return VarDeclaration(name, value)

    def parse_import(self) -> ImportDeclaration:
        self.expect(TokenType.IMPORT)
        module = self.expect(TokenType.IDENTIFIER).value

        alias = None
        if self.current_token().type == TokenType.AS:
            self.advance()
            alias = self.expect(TokenType.IDENTIFIER).value

        self.skip_newlines()
        return ImportDeclaration(module, alias)

    def parse_from_import(self) -> FromImportDeclaration:
        self.expect(TokenType.FROM)
        module = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.IMPORT)

        names = []
        aliases = []

        # Parse first name
        names.append(self.expect(TokenType.IDENTIFIER).value)
        if self.current_token().type == TokenType.AS:
            self.advance()
            aliases.append(self.expect(TokenType.IDENTIFIER).value)
        else:
            aliases.append(None)

        # Parse additional names
        while self.current_token().type == TokenType.COMMA:
            self.advance()
            names.append(self.expect(TokenType.IDENTIFIER).value)
            if self.current_token().type == TokenType.AS:
                self.advance()
                aliases.append(self.expect(TokenType.IDENTIFIER).value)
            else:
                aliases.append(None)

        self.skip_newlines()
        return FromImportDeclaration(module, names, aliases)

    def parse_statements(self) -> List[Statement]:
        statements = []
        while self.current_token().type not in [TokenType.DEDENT, TokenType.EOF]:
            self.skip_newlines()
            if self.current_token().type == TokenType.DEDENT:
                break
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            self.skip_newlines()
        return statements

    def parse_statement(self) -> Optional[Statement]:
        token = self.current_token()

        if token.type == TokenType.WHEN:
            return self.parse_when_statement()
        elif token.type == TokenType.BREAK:
            self.advance()
            return BreakStatement()
        elif token.type == TokenType.CONTINUE:
            self.advance()
            return ContinueStatement()
        elif token.type == TokenType.EXIT:
            self.advance()
            return ExitStatement()
        elif token.type == TokenType.PASS:
            self.advance()
            return PassStatement()
        elif token.type == TokenType.RETURN:
            self.advance()
            value = None
            if self.current_token().type not in [TokenType.NEWLINE, TokenType.EOF]:
                value = self.parse_expression()
            return ReturnStatement(value)
        elif token.type == TokenType.IDENTIFIER:
            if self.peek_token().type == TokenType.ASSIGN:
                name = self.advance().value
                self.advance()  # skip =
                value = self.parse_expression()
                return Assignment(name, value)
            else:
                expr = self.parse_expression()
                return ExpressionStatement(expr)
        else:
            expr = self.parse_expression()
            if expr:
                return ExpressionStatement(expr)
        return None

    def parse_when_statement(self) -> WhenStatement:
        self.expect(TokenType.WHEN)
        condition = self.parse_expression()
        self.expect(TokenType.COLON)
        self.skip_newlines()
        self.expect(TokenType.INDENT)

        body = self.parse_statements()

        self.expect(TokenType.DEDENT)

        return WhenStatement(condition, body)

    def parse_expression(self) -> Expression:
        return self.parse_comparison()

    def parse_comparison(self) -> Expression:
        left = self.parse_addition()

        while self.current_token().type in [TokenType.EQ, TokenType.NE, TokenType.LT,
                                           TokenType.GT, TokenType.LE, TokenType.GE]:
            op_token = self.advance()
            op = op_token.value if op_token.value else op_token.type.name.lower()
            right = self.parse_addition()
            left = BinaryOp(left, op, right)

        return left

    def parse_addition(self) -> Expression:
        left = self.parse_multiplication()

        while self.current_token().type in [TokenType.PLUS, TokenType.MINUS]:
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinaryOp(left, op, right)

        return left

    def parse_multiplication(self) -> Expression:
        left = self.parse_primary()

        while self.current_token().type in [TokenType.MULTIPLY, TokenType.DIVIDE]:
            op = self.advance().value
            right = self.parse_primary()
            left = BinaryOp(left, op, right)

        return left

    def parse_primary(self) -> Expression:
        token = self.current_token()

        if token.type == TokenType.NUMBER:
            self.advance()
            return NumberLiteral(token.value)
        elif token.type == TokenType.STRING:
            self.advance()
            return StringLiteral(token.value)
        elif token.type == TokenType.IDENTIFIER:
            name = self.advance().value

            # Check for function call
            if self.current_token().type == TokenType.LPAREN:
                self.advance()
                args = []
                while self.current_token().type != TokenType.RPAREN:
                    args.append(self.parse_expression())
                    if self.current_token().type == TokenType.COMMA:
                        self.advance()
                self.expect(TokenType.RPAREN)
                return CallExpression(name, args)
            # Check for member access (.start, .stop)
            elif self.current_token().type == TokenType.DOT:
                self.advance()
                # Check if next token is a keyword that would normally be an identifier
                if self.current_token().type in [TokenType.START, TokenType.STOP]:
                    member = self.advance().value
                else:
                    member = self.expect(TokenType.IDENTIFIER).value
                if member == "start":
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return StartExpression(name)
                elif member == "stop":
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return StopExpression(name)
                else:
                    # Check if this is a method call
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        args = []
                        while self.current_token().type != TokenType.RPAREN:
                            args.append(self.parse_expression())
                            if self.current_token().type == TokenType.COMMA:
                                self.advance()
                        self.expect(TokenType.RPAREN)
                        # Return a special method call expression
                        return MethodCall(Identifier(name), member, args)
                    else:
                        return MemberAccess(Identifier(name), member)
            else:
                return Identifier(name)
        elif token.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        raise SyntaxError(f"Unexpected token {token.type} at line {token.line}")