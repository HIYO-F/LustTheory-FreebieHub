#!/usr/bin/env python3
"""
WHEN Language Interpreter
A command-line tool for running WHEN programs

Usage:
    when <filename.when>     - Run a WHEN program
    when -i                  - Interactive REPL mode
    when --hot-reload <filename.when> - Run with hot reload enabled
    when --version          - Show version
    when --help             - Show this help
"""

import sys
import os
from pathlib import Path

# Add the current directory to the path so we can import our modules
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from lexer import Lexer
from parser import Parser
from interpreter import Interpreter

__version__ = "1.0.0"

def show_help():
    print(__doc__)

def show_version():
    print(f"WHEN Language Interpreter v{__version__}")
    print("Built on Python", sys.version)

def run_file(filename: str, hot_reload: bool = False):
    """Run a WHEN program from a file"""
    try:
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found")
            sys.exit(1)

        if not filename.endswith('.when'):
            print("Warning: WHEN files should have .when extension")

        with open(filename, 'r', encoding='utf-8') as f:
            source = f.read()

        # Tokenize
        lexer = Lexer(source)
        tokens = lexer.tokenize()

        # Parse
        parser = Parser(tokens)
        ast = parser.parse()

        # Interpret with hot reload if enabled
        interpreter = Interpreter(enable_hot_reload=hot_reload, source_file=filename)
        interpreter.interpret(ast)

    except FileNotFoundError:
        print(f"Error: File '{filename}' not found")
        sys.exit(1)
    except SyntaxError as e:
        print(f"Syntax Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Runtime Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def interactive_mode():
    """Interactive REPL for WHEN (simplified for now)"""
    print(f"WHEN Language Interactive Shell v{__version__}")
    print("Type 'exit()' to quit")
    print("Note: Interactive mode is limited - use files for full WHEN programs")

    interpreter = Interpreter()

    while True:
        try:
            line = input(">>> ")
            if line.strip() in ['exit()', 'quit()', 'exit', 'quit']:
                break
            if line.strip() == '':
                continue

            # Simple expression evaluation for now
            try:
                lexer = Lexer(line)
                tokens = lexer.tokenize()
                parser = Parser(tokens)

                # Try to parse as expression for simple evaluation
                if len(tokens) > 1 and tokens[0].type.name != 'MAIN':
                    # Add a simple main wrapper for evaluation
                    wrapped = f"x = {line}\nmain:\n    print(x)\n    exit()"
                    lexer = Lexer(wrapped)
                    tokens = lexer.tokenize()
                    parser = Parser(tokens)

                ast = parser.parse()
                interpreter.interpret(ast)
            except Exception as e:
                print(f"Error: {e}")

        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
        except EOFError:
            break

    print("Goodbye!")

def main():
    """Main entry point"""
    if len(sys.argv) == 1:
        show_help()
        return

    arg = sys.argv[1]

    if arg in ['-h', '--help']:
        show_help()
    elif arg in ['-v', '--version']:
        show_version()
    elif arg in ['-i', '--interactive']:
        interactive_mode()
    elif arg == '--hot-reload':
        if len(sys.argv) < 3:
            print("Error: --hot-reload requires a filename")
            print("Usage: when --hot-reload <filename.when>")
            sys.exit(1)
        run_file(sys.argv[2], hot_reload=True)
    elif arg.startswith('-'):
        print(f"Unknown option: {arg}")
        print("Use 'when --help' for usage information")
        sys.exit(1)
    else:
        # Assume it's a filename
        run_file(arg)

if __name__ == "__main__":
    main()