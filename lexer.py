import re
from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional

class TokenType(Enum):
    # Keywords
    MAIN = auto()
    OS = auto()
    DE = auto()
    FO = auto()
    PARALLEL = auto()
    WHEN = auto()
    DEF = auto()
    CLASS = auto()
    IMPORT = auto()
    FROM = auto()
    AS = auto()

    # Control flow
    ELSE = auto()
    BREAK = auto()
    CONTINUE = auto()
    EXIT = auto()
    PASS = auto()
    RETURN = auto()
    GLOBAL = auto()

    # Operations
    START = auto()
    STOP = auto()
    SAVE = auto()
    SAVESTOP = auto()
    STARTSAVE = auto()
    DISCARD = auto()

    # Additional operators
    FLOORDIV = auto()  # //

    # Literals
    NUMBER = auto()
    STRING = auto()
    FSTRING = auto()
    IDENTIFIER = auto()
    TRUE = auto()
    FALSE = auto()
    NONE = auto()

    # Operators
    ASSIGN = auto()
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    DOT = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    IN = auto()

    # Delimiters
    COLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()

    # Special
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: any
    line: int
    column: int

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.indent_stack = [0]
        self.brace_depth = 0  # Track nesting level of braces
        self.bracket_depth = 0  # Track nesting level of brackets
        self.paren_depth = 0  # Track nesting level of parentheses

    def peek(self, offset=0) -> Optional[str]:
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return None

    def advance(self) -> Optional[str]:
        if self.pos < len(self.source):
            char = self.source[self.pos]
            self.pos += 1
            if char == '\n':
                self.line += 1
                self.column = 1
            else:
                self.column += 1
            return char
        return None

    def skip_whitespace(self):
        while self.peek() and self.peek() in ' \t':
            self.advance()

    def skip_comment(self):
        if self.peek() == '#':
            while self.peek() and self.peek() != '\n':
                self.advance()

    def skip_block_comment(self):
        if self.peek() == '/' and self.peek(1) == '*':
            self.advance()  # Skip '/'
            self.advance()  # Skip '*'
            while self.peek():
                if self.peek() == '*' and self.peek(1) == '/':
                    self.advance()  # Skip '*'
                    self.advance()  # Skip '/'
                    return True
                self.advance()
            return False  # Unclosed block comment
        return False

    def read_number(self) -> Token:
        start_col = self.column
        num_str = ''

        # Handle negative numbers
        if self.peek() == '-':
            num_str += self.advance()

        while self.peek() and self.peek().isdigit():
            num_str += self.advance()
        if self.peek() == '.':
            num_str += self.advance()
            while self.peek() and self.peek().isdigit():
                num_str += self.advance()
            return Token(TokenType.NUMBER, float(num_str), self.line, start_col)
        return Token(TokenType.NUMBER, int(num_str), self.line, start_col)

    def read_string(self) -> Token:
        start_col = self.column
        quote = self.advance()  # Skip opening quote
        string_val = ''
        while self.peek() and self.peek() != quote:
            if self.peek() == '\\':
                self.advance()
                next_char = self.advance()
                if next_char == 'n':
                    string_val += '\n'
                elif next_char == 't':
                    string_val += '\t'
                else:
                    string_val += next_char
            else:
                string_val += self.advance()
        self.advance()  # Skip closing quote
        return Token(TokenType.STRING, string_val, self.line, start_col)

    def read_fstring(self) -> Token:
        start_col = self.column
        quote = self.advance()  # Skip opening quote
        parts = []
        current_str = ''

        while self.peek() and self.peek() != quote:
            if self.peek() == '{':
                # Save any string content before the expression
                if current_str:
                    parts.append(('str', current_str))
                    current_str = ''

                self.advance()  # Skip '{'

                # Read the expression inside {}
                expr = ''
                brace_count = 1
                while self.peek() and brace_count > 0:
                    char = self.advance()
                    if char == '{':
                        brace_count += 1
                        expr += char
                    elif char == '}':
                        brace_count -= 1
                        if brace_count > 0:
                            expr += char
                    else:
                        expr += char

                parts.append(('expr', expr.strip()))
            elif self.peek() == '\\':
                self.advance()
                next_char = self.advance()
                if next_char == 'n':
                    current_str += '\n'
                elif next_char == 't':
                    current_str += '\t'
                else:
                    current_str += next_char
            else:
                current_str += self.advance()

        # Add any remaining string content
        if current_str:
            parts.append(('str', current_str))

        self.advance()  # Skip closing quote
        return Token(TokenType.FSTRING, parts, self.line, start_col)

    def read_identifier(self) -> Token:
        start_col = self.column
        ident = ''
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            ident += self.advance()

        # Check for keywords
        keywords = {
            'main': TokenType.MAIN,
            'os': TokenType.OS,
            'de': TokenType.DE,
            'fo': TokenType.FO,
            'parallel': TokenType.PARALLEL,
            'when': TokenType.WHEN,
            'def': TokenType.DEF,
            'class': TokenType.CLASS,
            'import': TokenType.IMPORT,
            'from': TokenType.FROM,
            'as': TokenType.AS,
            'else': TokenType.ELSE,
            'break': TokenType.BREAK,
            'continue': TokenType.CONTINUE,
            'pass': TokenType.PASS,
            'return': TokenType.RETURN,
            'global': TokenType.GLOBAL,
            'start': TokenType.START,
            'stop': TokenType.STOP,
            'save': TokenType.SAVE,
            'savestop': TokenType.SAVESTOP,
            'startsave': TokenType.STARTSAVE,
            'discard': TokenType.DISCARD,
            'True': TokenType.TRUE,
            'False': TokenType.FALSE,
            'None': TokenType.NONE,
            'and': TokenType.AND,
            'or': TokenType.OR,
            'not': TokenType.NOT,
            'in': TokenType.IN,
        }

        token_type = keywords.get(ident, TokenType.IDENTIFIER)
        return Token(token_type, ident, self.line, start_col)

    def handle_indentation(self):
        # Skip indentation handling if we're inside braces, brackets, or parentheses
        if self.brace_depth > 0 or self.bracket_depth > 0 or self.paren_depth > 0:
            # Just consume spaces without generating indent/dedent tokens
            while self.peek() and self.peek() == ' ':
                self.advance()
            return

        if self.column == 1:
            indent_level = 0
            while self.peek() and self.peek() == ' ':
                indent_level += 1
                self.advance()

            if self.peek() and self.peek() not in '\n#':
                current_indent = self.indent_stack[-1]
                if indent_level > current_indent:
                    self.indent_stack.append(indent_level)
                    self.tokens.append(Token(TokenType.INDENT, indent_level, self.line, 1))
                elif indent_level < current_indent:
                    while len(self.indent_stack) > 1 and self.indent_stack[-1] > indent_level:
                        self.indent_stack.pop()
                        self.tokens.append(Token(TokenType.DEDENT, indent_level, self.line, 1))

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            # Handle indentation at start of line
            if self.column == 1:
                self.handle_indentation()

            self.skip_whitespace()

            # Skip single-line comments
            if self.peek() == '#':
                self.skip_comment()
                continue

            # Skip block comments
            if self.peek() == '/' and self.peek(1) == '*':
                if not self.skip_block_comment():
                    raise SyntaxError(f"Unclosed block comment starting at line {self.line}, column {self.column}")
                continue

            if not self.peek():
                break

            char = self.peek()

            # Newline
            if char == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, self.column))
                self.advance()
                continue

            # Numbers (including negative numbers)
            if char.isdigit() or (char == '-' and self.peek(1) and self.peek(1).isdigit()):
                self.tokens.append(self.read_number())
                continue

            # Check for f-strings (must come before regular strings)
            if char == 'f' and self.peek(1) and self.peek(1) in '"\'':
                self.advance()  # Skip 'f'
                self.tokens.append(self.read_fstring())
                continue

            # Strings
            if char in '"\'':
                self.tokens.append(self.read_string())
                continue

            # Identifiers and keywords
            if char.isalpha() or char == '_':
                self.tokens.append(self.read_identifier())
                continue

            # Two-character operators
            if self.peek() and self.peek(1):
                two_char = self.peek() + self.peek(1)
                token_map = {
                    '==': TokenType.EQ,
                    '!=': TokenType.NE,
                    '<=': TokenType.LE,
                    '>=': TokenType.GE,
                    '//': TokenType.FLOORDIV,
                }
                if two_char in token_map:
                    col = self.column
                    self.advance()
                    self.advance()
                    self.tokens.append(Token(token_map[two_char], two_char, self.line, col))
                    continue

            # Single-character tokens
            single_char_tokens = {
                ':': TokenType.COLON,
                '(': TokenType.LPAREN,
                ')': TokenType.RPAREN,
                '[': TokenType.LBRACKET,
                ']': TokenType.RBRACKET,
                '{': TokenType.LBRACE,
                '}': TokenType.RBRACE,
                ',': TokenType.COMMA,
                '=': TokenType.ASSIGN,
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
                '*': TokenType.MULTIPLY,
                '/': TokenType.DIVIDE,
                '%': TokenType.MODULO,
                '<': TokenType.LT,
                '>': TokenType.GT,
                '.': TokenType.DOT,
            }

            if char in single_char_tokens:
                col = self.column
                token_type = single_char_tokens[char]

                # Track nesting depth for proper indentation handling
                if token_type == TokenType.LBRACE:
                    self.brace_depth += 1
                elif token_type == TokenType.RBRACE:
                    self.brace_depth -= 1
                elif token_type == TokenType.LBRACKET:
                    self.bracket_depth += 1
                elif token_type == TokenType.RBRACKET:
                    self.bracket_depth -= 1
                elif token_type == TokenType.LPAREN:
                    self.paren_depth += 1
                elif token_type == TokenType.RPAREN:
                    self.paren_depth -= 1

                self.tokens.append(Token(token_type, char, self.line, col))
                self.advance()
                continue

            # Unknown character
            raise SyntaxError(f"Unexpected character '{char}' at line {self.line}, column {self.column}")

        # Add remaining dedents
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, 0, self.line, self.column))

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens