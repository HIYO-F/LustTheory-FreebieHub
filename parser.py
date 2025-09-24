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
                # Check if it's a number or identifier
                if self.current_token().type == TokenType.NUMBER:
                    iterations = int(self.current_token().value)
                    self.advance()
                elif self.current_token().type == TokenType.IDENTIFIER:
                    # Store variable name as string
                    iterations = self.current_token().value
                    self.advance()
                else:
                    raise SyntaxError(f"DE block requires iteration count or variable, got {self.current_token().type}")
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
            values = []
            if self.current_token().type not in [TokenType.NEWLINE, TokenType.EOF]:
                values.append(self.parse_expression())
                while self.current_token().type == TokenType.COMMA:
                    self.advance()
                    values.append(self.parse_expression())
            return ReturnStatement(values)
        elif token.type == TokenType.GLOBAL:
            self.advance()
            names = []
            names.append(self.expect(TokenType.IDENTIFIER).value)
            while self.current_token().type == TokenType.COMMA:
                self.advance()
                names.append(self.expect(TokenType.IDENTIFIER).value)
            return GlobalStatement(names)
        elif token.type == TokenType.IDENTIFIER:
            # Parse the left side as an expression first
            # Check for simple assignment shortcut
            if self.peek_token().type == TokenType.ASSIGN:
                # Simple assignment: var = value
                name = self.advance().value
                self.advance()  # skip =
                value = self.parse_expression()
                return Assignment(name, value)
            else:
                # Parse as expression and check if it's an assignment target
                expr = self.parse_expression()

                # Check if this expression is followed by an assignment
                if self.current_token().type == TokenType.ASSIGN:
                    self.advance()  # skip =
                    value = self.parse_expression()

                    # Determine what kind of assignment this is
                    if isinstance(expr, MemberAccess):
                        # obj.attr = value
                        return AttributeAssignment(expr.object, expr.member, value)
                    elif isinstance(expr, IndexExpression):
                        # obj[index] = value  or  obj.attr[index] = value
                        return IndexAssignment(expr.object, expr.index, value)
                    else:
                        # This shouldn't happen with valid syntax
                        raise SyntaxError(f"Invalid assignment target at line {self.current_token().line}")
                else:
                    # Just an expression statement
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
        return self.parse_ternary()

    def parse_ternary(self) -> Expression:
        # Parse the main expression (which could be the true_expr in ternary)
        expr = self.parse_comparison()

        # Check for ternary operator: expr when condition else false_expr
        if self.current_token().type == TokenType.WHEN:
            self.advance()  # consume 'when'
            condition = self.parse_comparison()
            self.expect(TokenType.ELSE)
            false_expr = self.parse_ternary()  # Allow nested ternaries
            return TernaryOp(expr, condition, false_expr)

        return expr

    def parse_comparison(self) -> Expression:
        left = self.parse_logical_and()

        while self.current_token().type in [TokenType.EQ, TokenType.NE, TokenType.LT,
                                           TokenType.GT, TokenType.LE, TokenType.GE, TokenType.IN, TokenType.NOT]:

            # Handle "not in" compound operator
            if self.current_token().type == TokenType.NOT and self.peek_token().type == TokenType.IN:
                self.advance()  # consume "not"
                self.advance()  # consume "in"
                op = "not in"
                right = self.parse_logical_and()
                left = BinaryOp(left, op, right)
            else:
                op_token = self.advance()
                op = op_token.value if op_token.value else op_token.type.name.lower()
                right = self.parse_logical_and()
                left = BinaryOp(left, op, right)

        return left

    def parse_logical_and(self) -> Expression:
        left = self.parse_logical_or()

        while self.current_token().type == TokenType.AND:
            op = self.advance().value
            right = self.parse_logical_or()
            left = BinaryOp(left, op, right)

        return left

    def parse_logical_or(self) -> Expression:
        left = self.parse_addition()

        while self.current_token().type == TokenType.OR:
            op = self.advance().value
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
        left = self.parse_unary()

        while self.current_token().type in [TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO, TokenType.FLOORDIV]:
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(left, op, right)

        return left

    def parse_unary(self) -> Expression:
        if self.current_token().type == TokenType.MINUS:
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op, operand)
        elif self.current_token().type == TokenType.NOT:
            # Check for "not in" compound operator
            if self.peek_token().type == TokenType.IN:
                # This is "not in" - let the comparison parser handle it
                return self.parse_postfix()
            else:
                # Regular "not" unary operator
                op = self.advance().value
                operand = self.parse_unary()
                return UnaryOp(op, operand)
        return self.parse_postfix()

    def parse_postfix(self) -> Expression:
        expr = self.parse_primary()

        while True:
            if self.current_token().type == TokenType.LBRACKET:
                self.advance()
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = IndexExpression(expr, index)
            elif self.current_token().type == TokenType.DOT:
                self.advance()

                # Check if next token is a keyword that would normally be an identifier
                if self.current_token().type in [TokenType.START, TokenType.STOP, TokenType.SAVE, TokenType.SAVESTOP, TokenType.STARTSAVE, TokenType.DISCARD]:
                    keyword_token = self.advance()
                    member = keyword_token.value
                else:
                    member_token = self.expect(TokenType.IDENTIFIER)
                    member = member_token.value

                # Handle special block operations
                if member == "start" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return StartExpression(expr.name)
                elif member == "stop" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return StopExpression(expr.name)
                elif member == "save" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return SaveExpression(expr.name)
                elif member == "savestop" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return SaveStopExpression(expr.name)
                elif member == "startsave" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return StartSaveExpression(expr.name)
                elif member == "discard" and isinstance(expr, Identifier):
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        self.expect(TokenType.RPAREN)
                    return DiscardExpression(expr.name)
                else:
                    # Check if this is a method call
                    if self.current_token().type == TokenType.LPAREN:
                        self.advance()
                        args = []
                        kwargs = []

                        while self.current_token().type != TokenType.RPAREN:
                            # Check if this is a keyword argument (identifier=value)
                            if (self.current_token().type == TokenType.IDENTIFIER and
                                self.peek_token().type == TokenType.ASSIGN):

                                kw_name = self.advance().value
                                self.advance()  # consume =
                                kw_value = self.parse_expression()
                                kwargs.append(KeywordArg(kw_name, kw_value))
                            else:
                                # Regular positional argument
                                args.append(self.parse_expression())

                            if self.current_token().type == TokenType.COMMA:
                                self.advance()

                        self.expect(TokenType.RPAREN)
                        # Create method call with current expression as object
                        expr = MethodCall(expr, member, args, kwargs if kwargs else None)
                    else:
                        # Regular member access
                        expr = MemberAccess(expr, member)
            else:
                break

        return expr

    def parse_primary(self) -> Expression:
        token = self.current_token()

        if token.type == TokenType.NUMBER:
            self.advance()
            return NumberLiteral(token.value)
        elif token.type == TokenType.STRING:
            self.advance()
            return StringLiteral(token.value)
        elif token.type == TokenType.FSTRING:
            self.advance()
            return FStringLiteral(token.value)
        elif token.type == TokenType.TRUE:
            self.advance()
            return BooleanLiteral(True)
        elif token.type == TokenType.FALSE:
            self.advance()
            return BooleanLiteral(False)
        elif token.type == TokenType.NONE:
            self.advance()
            return NoneLiteral()
        elif token.type == TokenType.LBRACKET:
            return self.parse_list()
        elif token.type == TokenType.LBRACE:
            return self.parse_dict()
        elif token.type == TokenType.LPAREN:
            # Check if this is a tuple or just a parenthesized expression
            self.advance()

            # Empty tuple case
            if self.current_token().type == TokenType.RPAREN:
                self.advance()
                return TupleLiteral([])

            # Parse first element
            first_expr = self.parse_expression()

            # If we see a comma, it's definitely a tuple
            if self.current_token().type == TokenType.COMMA:
                elements = [first_expr]
                self.advance()  # consume comma

                # Parse remaining elements
                while self.current_token().type != TokenType.RPAREN:
                    elements.append(self.parse_expression())
                    if self.current_token().type == TokenType.COMMA:
                        self.advance()
                    elif self.current_token().type != TokenType.RPAREN:
                        break

                self.expect(TokenType.RPAREN)
                return TupleLiteral(elements)
            else:
                # Single element in parentheses - check for trailing comma to disambiguate
                if self.current_token().type == TokenType.COMMA:
                    self.advance()  # consume trailing comma
                    self.expect(TokenType.RPAREN)
                    return TupleLiteral([first_expr])
                else:
                    # Just a parenthesized expression
                    self.expect(TokenType.RPAREN)
                    return first_expr
        elif token.type == TokenType.IDENTIFIER:
            name = self.advance().value

            # Check for function call
            if self.current_token().type == TokenType.LPAREN:
                self.advance()
                args = []
                kwargs = []

                while self.current_token().type != TokenType.RPAREN:
                    # Check if this is a keyword argument (identifier=value)
                    if (self.current_token().type == TokenType.IDENTIFIER and
                        self.peek_token().type == TokenType.ASSIGN):

                        kw_name = self.advance().value
                        self.advance()  # consume =
                        kw_value = self.parse_expression()
                        kwargs.append(KeywordArg(kw_name, kw_value))
                    else:
                        # Regular positional argument
                        args.append(self.parse_expression())

                    if self.current_token().type == TokenType.COMMA:
                        self.advance()

                self.expect(TokenType.RPAREN)
                return CallExpression(name, args, kwargs if kwargs else None)
            # Check for member access (.start, .stop) or chained member/method access
            elif self.current_token().type == TokenType.DOT:
                expr = Identifier(name)

                # Handle chained dot access
                while self.current_token().type == TokenType.DOT:
                    self.advance()

                    # Check if next token is a keyword that would normally be an identifier
                    if self.current_token().type in [TokenType.START, TokenType.STOP, TokenType.SAVE, TokenType.SAVESTOP, TokenType.STARTSAVE, TokenType.DISCARD]:
                        member = self.advance().value
                    else:
                        member = self.expect(TokenType.IDENTIFIER).value

                    # Special handling for block operations
                    if member == "start" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return StartExpression(expr.name)
                    elif member == "stop" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return StopExpression(expr.name)
                    elif member == "save" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return SaveExpression(expr.name)
                    elif member == "savestop" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return SaveStopExpression(expr.name)
                    elif member == "startsave" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return StartSaveExpression(expr.name)
                    elif member == "discard" and isinstance(expr, Identifier):
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            self.expect(TokenType.RPAREN)
                        return DiscardExpression(expr.name)
                    else:
                        # Check if this is a method call
                        if self.current_token().type == TokenType.LPAREN:
                            self.advance()
                            args = []
                            kwargs = []

                            while self.current_token().type != TokenType.RPAREN:
                                # Check if this is a keyword argument (identifier=value)
                                if (self.current_token().type == TokenType.IDENTIFIER and
                                    self.peek_token().type == TokenType.ASSIGN):

                                    kw_name = self.advance().value
                                    self.advance()  # consume =
                                    kw_value = self.parse_expression()
                                    kwargs.append(KeywordArg(kw_name, kw_value))
                                else:
                                    # Regular positional argument
                                    args.append(self.parse_expression())

                                if self.current_token().type == TokenType.COMMA:
                                    self.advance()

                            self.expect(TokenType.RPAREN)
                            # Create method call with current expression as object
                            expr = MethodCall(expr, member, args, kwargs if kwargs else None)
                        else:
                            # Regular member access
                            expr = MemberAccess(expr, member)

                return expr
            else:
                return Identifier(name)
        raise SyntaxError(f"Unexpected token {token.type} at line {token.line}")

    def parse_list(self) -> ListLiteral:
        self.expect(TokenType.LBRACKET)
        elements = []

        # Skip any newlines after opening bracket
        self.skip_newlines()

        if self.current_token().type != TokenType.RBRACKET:
            elements.append(self.parse_expression())

            while True:
                self.skip_newlines()
                if self.current_token().type != TokenType.COMMA:
                    break
                self.advance()  # consume comma
                self.skip_newlines()

                if self.current_token().type == TokenType.RBRACKET:
                    break  # trailing comma

                elements.append(self.parse_expression())

        self.skip_newlines()
        self.expect(TokenType.RBRACKET)
        return ListLiteral(elements)

    def parse_dict(self) -> DictLiteral:
        self.expect(TokenType.LBRACE)
        keys = []
        values = []

        # Skip any newlines after opening brace
        self.skip_newlines()

        if self.current_token().type != TokenType.RBRACE:
            # Parse first key-value pair
            key = self.parse_expression()
            self.skip_newlines()
            self.expect(TokenType.COLON)
            self.skip_newlines()
            value = self.parse_expression()
            keys.append(key)
            values.append(value)

            # Parse remaining key-value pairs
            while True:
                self.skip_newlines()
                if self.current_token().type != TokenType.COMMA:
                    break
                self.advance()  # consume comma
                self.skip_newlines()

                if self.current_token().type == TokenType.RBRACE:
                    break  # trailing comma

                key = self.parse_expression()
                self.skip_newlines()
                self.expect(TokenType.COLON)
                self.skip_newlines()
                value = self.parse_expression()
                keys.append(key)
                values.append(value)

        self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return DictLiteral(keys, values)