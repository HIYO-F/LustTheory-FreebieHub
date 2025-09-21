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
    IMPORT = auto()
    FROM = auto()
    AS = auto()

    # Control flow
    BREAK = auto()
    CONTINUE = auto()
    EXIT = auto()
    PASS = auto()
    RETURN = auto()
    GLOBAL = auto()

    # Operations
    START = auto()
    STOP = auto()

    # Literals
    NUMBER = auto()
    STRING = auto()
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
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    DOT = auto()

    # Delimiters
    COLON = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
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
            'import': TokenType.IMPORT,
            'from': TokenType.FROM,
            'as': TokenType.AS,
            'break': TokenType.BREAK,
            'continue': TokenType.CONTINUE,
            'pass': TokenType.PASS,
            'return': TokenType.RETURN,
            'global': TokenType.GLOBAL,
            'start': TokenType.START,
            'stop': TokenType.STOP,
            'True': TokenType.TRUE,
            'False': TokenType.FALSE,
            'None': TokenType.NONE,
        }

        token_type = keywords.get(ident, TokenType.IDENTIFIER)
        return Token(token_type, ident, self.line, start_col)

    def handle_indentation(self):
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

            if self.peek() == '#':
                self.skip_comment()
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
                ',': TokenType.COMMA,
                '=': TokenType.ASSIGN,
                '+': TokenType.PLUS,
                '-': TokenType.MINUS,
                '*': TokenType.MULTIPLY,
                '/': TokenType.DIVIDE,
                '<': TokenType.LT,
                '>': TokenType.GT,
                '.': TokenType.DOT,
            }

            if char in single_char_tokens:
                col = self.column
                self.tokens.append(Token(single_char_tokens[char], char, self.line, col))
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