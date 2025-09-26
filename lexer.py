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
    WITH = auto()
    IS = auto()

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

    def peek_ahead(self, length) -> str:
        """Peek ahead multiple characters"""
        result = ""
        for i in range(length):
            char = self.peek(i)
            if char:
                result += char
            else:
                break
        return result

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

        # Handle triple quotes for multi-line strings
        is_triple = False
        if self.peek() == quote and self.peek(1) == quote:
            is_triple = True
            self.advance()  # Skip second quote
            self.advance()  # Skip third quote

        while self.peek():
            if is_triple:
                # Check for triple quote ending
                if (self.peek() == quote and
                    self.peek(1) == quote and
                    self.peek(2) == quote):
                    self.advance()  # Skip first quote
                    self.advance()  # Skip second quote
                    self.advance()  # Skip third quote
                    break
            else:
                # Single quote string
                if self.peek() == quote:
                    self.advance()  # Skip closing quote
                    break

            if self.peek() == '\\':
                self.advance()
                next_char = self.advance()
                if next_char == 'n':
                    string_val += '\n'
                elif next_char == 't':
                    string_val += '\t'
                elif next_char == 'r':
                    string_val += '\r'
                elif next_char == '\\':
                    string_val += '\\'
                elif next_char == '\"':
                    string_val += '\"'
                elif next_char == "'":
                    string_val += "'"
                elif next_char == 'b':
                    string_val += '\b'
                elif next_char == 'f':
                    string_val += '\f'
                elif next_char == 'v':
                    string_val += '\v'
                elif next_char == '0':
                    string_val += '\0'
                elif next_char == 'x':
                    # Hex escape sequence
                    hex_digits = ''
                    for _ in range(2):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 2:
                        string_val += chr(int(hex_digits, 16))
                    else:
                        string_val += '\\x' + hex_digits
                elif next_char == 'u':
                    # Unicode escape sequence
                    hex_digits = ''
                    for _ in range(4):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 4:
                        string_val += chr(int(hex_digits, 16))
                    else:
                        string_val += '\\u' + hex_digits
                elif next_char == 'U':
                    # Long unicode escape sequence
                    hex_digits = ''
                    for _ in range(8):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 8:
                        string_val += chr(int(hex_digits, 16))
                    else:
                        string_val += '\\U' + hex_digits
                else:
                    # For unrecognized escape sequences, just include the character
                    string_val += next_char
            else:
                string_val += self.advance()

        return Token(TokenType.STRING, string_val, self.line, start_col)

    def read_raw_string(self) -> Token:
        """Read a raw string (r-string) where backslashes are literal"""
        start_col = self.column
        quote = self.advance()  # Skip opening quote
        string_val = ''

        # Handle triple quotes for multi-line raw strings
        is_triple = False
        if self.peek() == quote and self.peek(1) == quote:
            is_triple = True
            self.advance()  # Skip second quote
            self.advance()  # Skip third quote

        while self.peek():
            if is_triple:
                # Check for triple quote ending
                if (self.peek() == quote and
                    self.peek(1) == quote and
                    self.peek(2) == quote):
                    self.advance()  # Skip first quote
                    self.advance()  # Skip second quote
                    self.advance()  # Skip third quote
                    break
                string_val += self.advance()
            else:
                # Single quote raw string
                if self.peek() == quote:
                    self.advance()  # Skip closing quote
                    break
                # In raw strings, backslashes are literal
                string_val += self.advance()

        return Token(TokenType.STRING, string_val, self.line, start_col)

    def read_fstring(self, is_raw=False) -> Token:
        """Read an f-string, optionally as raw (rf or fr)"""
        start_col = self.column
        quote = self.advance()  # Skip opening quote
        parts = []
        current_str = ''

        # Handle triple quotes for multi-line f-strings
        is_triple = False
        if self.peek() == quote and self.peek(1) == quote:
            is_triple = True
            self.advance()  # Skip second quote
            self.advance()  # Skip third quote

        while self.peek():
            # Check for end quote(s)
            if is_triple:
                if (self.peek() == quote and
                    self.peek(1) == quote and
                    self.peek(2) == quote):
                    # Add any remaining string content
                    if current_str:
                        parts.append(('str', current_str))
                    self.advance()  # Skip first quote
                    self.advance()  # Skip second quote
                    self.advance()  # Skip third quote
                    break
            else:
                if self.peek() == quote:
                    # Add any remaining string content
                    if current_str:
                        parts.append(('str', current_str))
                    self.advance()  # Skip closing quote
                    break

            if self.peek() == '{':
                # Check for {{ escape
                if self.peek(1) == '{':
                    current_str += '{'
                    self.advance()  # Skip first {
                    self.advance()  # Skip second {
                    continue

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
            elif self.peek() == '}':
                # Check for }} escape
                if self.peek(1) == '}':
                    current_str += '}'
                    self.advance()  # Skip first }
                    self.advance()  # Skip second }
                else:
                    # Single } is an error in f-strings
                    raise SyntaxError(f"Single '}}' is not allowed in f-string at line {self.line}")
            elif self.peek() == '\\' and not is_raw:
                # Process escape sequences (unless it's a raw f-string)
                self.advance()
                next_char = self.advance()
                if next_char == 'n':
                    current_str += '\n'
                elif next_char == 't':
                    current_str += '\t'
                elif next_char == 'r':
                    current_str += '\r'
                elif next_char == '\\':
                    current_str += '\\'
                elif next_char == '\"':
                    current_str += '\"'
                elif next_char == "'":
                    current_str += "'"
                elif next_char == 'b':
                    current_str += '\b'
                elif next_char == 'f':
                    current_str += '\f'
                elif next_char == 'v':
                    current_str += '\v'
                elif next_char == '0':
                    current_str += '\0'
                elif next_char == 'x':
                    # Hex escape sequence
                    hex_digits = ''
                    for _ in range(2):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 2:
                        current_str += chr(int(hex_digits, 16))
                    else:
                        current_str += '\\x' + hex_digits
                elif next_char == 'u':
                    # Unicode escape sequence
                    hex_digits = ''
                    for _ in range(4):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 4:
                        current_str += chr(int(hex_digits, 16))
                    else:
                        current_str += '\\u' + hex_digits
                elif next_char == 'U':
                    # Long unicode escape sequence
                    hex_digits = ''
                    for _ in range(8):
                        if self.peek() and self.peek() in '0123456789abcdefABCDEF':
                            hex_digits += self.advance()
                    if len(hex_digits) == 8:
                        current_str += chr(int(hex_digits, 16))
                    else:
                        current_str += '\\U' + hex_digits
                else:
                    # For unrecognized escape sequences, include the character
                    current_str += next_char
            else:
                # Regular character (or backslash in raw f-string)
                current_str += self.advance()

        return Token(TokenType.FSTRING, parts, self.line, start_col)

    def read_identifier(self) -> Token:
        start_col = self.column
        ident = ''
        while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
            ident += self.advance()

        # Check for keywords (removed 'os' from keywords - it's now context-sensitive)
        keywords = {
            'main': TokenType.MAIN,
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
            'with': TokenType.WITH,
            'is': TokenType.IS,
        }

        # Handle 'os' context-sensitively
        if ident == 'os':
            # Save current position
            saved_pos = self.pos
            saved_col = self.column
            saved_line = self.line

            # Skip whitespace
            while self.peek() and self.peek() in ' \t':
                self.advance()

            # Check what follows 'os'
            next_char = self.peek()

            # os is an IDENTIFIER (import) if:
            # 1. Followed by a dot (os.something)
            # 2. At end of line/file (import os)
            # 3. Followed by comma (import os, sys)
            # 4. Followed by 'as' (import os as operating_system)

            # os is a KEYWORD (OS block) if:
            # Followed by identifier then : or ( (os blockname: or os blockname():)

            # Quick check for os.something (module access)
            if next_char == '.':
                # Restore position
                self.pos = saved_pos
                self.column = saved_col
                self.line = saved_line
                return Token(TokenType.IDENTIFIER, ident, self.line, start_col)

            # Check for import statement context (comma, newline, as, etc)
            if next_char in [',', '\n', None] or not next_char.isalpha():
                # Restore position
                self.pos = saved_pos
                self.column = saved_col
                self.line = saved_line
                return Token(TokenType.IDENTIFIER, ident, self.line, start_col)

            # Now check if it's a block declaration
            if next_char and next_char.isalpha():
                # os blockname: or os blockname():
                # Read the next word
                next_word = ''
                temp_pos = self.pos
                while self.peek() and (self.peek().isalnum() or self.peek() == '_'):
                    next_word += self.peek()
                    self.pos += 1

                # Skip more whitespace
                while self.peek() and self.peek() in ' \t':
                    self.advance()

                # Check what comes after the identifier
                following = self.peek()

                # It's an OS block if:
                # - followed by ':' (os blockname:)
                # - followed by '(' (os blockname(): or os blockname(args):)
                if following == ':' or following == '(':
                    # Restore position
                    self.pos = saved_pos
                    self.column = saved_col
                    self.line = saved_line
                    return Token(TokenType.OS, ident, self.line, start_col)

            # Restore position
            self.pos = saved_pos
            self.column = saved_col
            self.line = saved_line

            # Not a block declaration, treat as identifier
            return Token(TokenType.IDENTIFIER, ident, self.line, start_col)

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

            # Check for f-strings and raw strings (rf, fr, rb, br, etc.)
            # Handle all possible prefix combinations
            if char.lower() in 'rfbu':
                # Check for string prefixes (f, r, b, u, rf, fr, rb, br, etc.)
                prefix = ''
                saved_pos = self.pos
                saved_col = self.column
                saved_line = self.line

                # Collect all prefix characters (up to 3 for safety but typically 2)
                while self.peek() and self.peek().lower() in 'rfbu' and len(prefix) < 3:
                    prefix += self.peek().lower()
                    self.advance()

                # Check if this is followed by a quote (including triple quotes)
                next_char = self.peek()
                if next_char and next_char in '"\'':
                    # Check what type of string this is
                    if 'f' in prefix and 'r' in prefix:
                        # It's a raw f-string (rf or fr)
                        self.tokens.append(self.read_fstring(is_raw=True))
                        continue
                    elif 'f' in prefix:
                        # It's a regular f-string
                        self.tokens.append(self.read_fstring(is_raw=False))
                        continue
                    elif 'b' in prefix and 'r' in prefix:
                        # Raw bytes string - treat as raw string
                        self.tokens.append(self.read_raw_string())
                        continue
                    elif 'b' in prefix:
                        # It's a bytes string - treat as regular string for now
                        self.tokens.append(self.read_string())
                        continue
                    elif 'r' in prefix:
                        # It's a raw string - read without escape processing
                        self.tokens.append(self.read_raw_string())
                        continue
                    elif 'u' in prefix:
                        # Unicode string (same as regular in Python 3)
                        self.tokens.append(self.read_string())
                        continue
                else:
                    # Not a string prefix, restore position and treat as identifier
                    self.pos = saved_pos
                    self.column = saved_col
                    self.line = saved_line
                    self.tokens.append(self.read_identifier())
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