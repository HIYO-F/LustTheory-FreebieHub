import time
import sys
import threading
import queue
from typing import Dict, Any, Optional, List
from ast_nodes import *
from enum import Enum, auto

class ControlFlow(Exception):
    pass

class BreakException(ControlFlow):
    pass

class ContinueException(ControlFlow):
    pass

class ExitException(ControlFlow):
    pass

class ReturnException(ControlFlow):
    def __init__(self, value=None):
        self.value = value

class BlockStatus(Enum):
    STOPPED = auto()
    RUNNING = auto()
    COMPLETED = auto()

class Block:
    def __init__(self, name: str, body: List[Statement], iterations: Optional[int] = None, block_type: str = "fo", is_parallel: bool = False):
        self.name = name
        self.body = body
        self.iterations = iterations
        self.current_iteration = 0
        self.status = BlockStatus.STOPPED
        self.block_type = block_type  # "os", "de", "fo"
        self.is_parallel = is_parallel
        self.thread = None
        self.should_stop = threading.Event()

        # Save/restore functionality
        self.saved_iteration = None
        self.saved_status = None
        self.has_saved_state = False

    def reset(self):
        self.current_iteration = 0
        self.status = BlockStatus.STOPPED
        self.should_stop.clear()
        if self.thread and self.thread.is_alive():
            self.should_stop.set()
            self.thread.join(timeout=1.0)

    def save_state(self):
        """Save current execution state"""
        self.saved_iteration = self.current_iteration
        self.saved_status = self.status
        self.has_saved_state = True

    def restore_state(self):
        """Restore execution state from saved checkpoint"""
        if self.has_saved_state:
            self.current_iteration = self.saved_iteration
            self.status = self.saved_status
            return True
        return False

    def clear_saved_state(self):
        """Clear saved state"""
        self.saved_iteration = None
        self.saved_status = None
        self.has_saved_state = False

    def discard_saved_state(self):
        """Discard saved state and return whether there was state to discard"""
        if self.has_saved_state:
            self.clear_saved_state()
            return True
        return False

class Interpreter:
    def __init__(self, enable_hot_reload=False, source_file=None):
        self.global_vars: Dict[str, Any] = {}
        self.functions: Dict[str, FuncDeclaration] = {}
        self.blocks: Dict[str, Block] = {}
        self.running_blocks: List[str] = []
        self.exit_requested = False
        self.modules: Dict[str, Any] = {}
        self.global_vars_lock = threading.Lock()
        self.parallel_threads: List[threading.Thread] = []
        self.hot_reloader = None
        self.enable_hot_reload = enable_hot_reload
        self.source_file = source_file

    def interpret(self, program: Program):
        # Process declarations
        for decl in program.declarations:
            if isinstance(decl, VarDeclaration):
                self.global_vars[decl.name] = self.eval_expression(decl.value)
            elif isinstance(decl, FuncDeclaration):
                self.functions[decl.name] = decl
            elif isinstance(decl, ImportDeclaration):
                self.handle_import(decl)
            elif isinstance(decl, FromImportDeclaration):
                self.handle_from_import(decl)

        # Register blocks (check specific types first!)
        for block in program.blocks:
            if isinstance(block, OSBlock):
                self.blocks[block.name] = Block(block.name, block.body, None, "os", False)
            elif isinstance(block, ParallelDEBlock):
                self.blocks[block.name] = Block(block.name, block.body, block.iterations, "de", True)
            elif isinstance(block, ParallelFOBlock):
                self.blocks[block.name] = Block(block.name, block.body, None, "fo", True)
            elif isinstance(block, DEBlock):
                self.blocks[block.name] = Block(block.name, block.body, block.iterations, "de", False)
            else:  # Regular FOBlock
                self.blocks[block.name] = Block(block.name, block.body, None, "fo", False)

        # Setup hot reload if enabled
        if self.enable_hot_reload and self.source_file:
            from hot_reload import HotReloader
            self.hot_reloader = HotReloader(self, self.source_file)
            self.hot_reloader.start_watching()

        # Execute main block
        try:
            self.execute_main(program.main)
        except ExitException:
            print("Program exited")
        finally:
            # Stop hot reload if active
            if self.hot_reloader:
                self.hot_reloader.stop_watching()
            # Clean up parallel threads
            self.cleanup_parallel_threads()

    def execute_main(self, main_block: MainBlock):
        while not self.exit_requested:
            try:
                # Execute main block body
                self.execute_statements(main_block.body)

                # Execute one iteration of each running block (cooperative scheduling)
                for block_name in list(self.running_blocks):
                    block = self.blocks[block_name]
                    if block.status == BlockStatus.RUNNING:
                        self.execute_block_iteration(block)

            except ContinueException:
                continue
            except BreakException:
                break
            except ExitException:
                raise

    def execute_block_iteration(self, block: Block):
        if block.status != BlockStatus.RUNNING:
            return

        # For DE blocks, check if we've already completed all iterations
        if block.iterations is not None and block.current_iteration >= block.iterations:
            block.status = BlockStatus.COMPLETED
            if block.name in self.running_blocks:
                self.running_blocks.remove(block.name)
            return

        try:
            # Execute one iteration
            self.execute_statements(block.body)

            # Increment iteration counter AFTER successful execution
            if block.iterations is not None:
                block.current_iteration += 1
                # Check if we've now completed all iterations
                if block.current_iteration >= block.iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)

        except ContinueException:
            # Continue still counts as an iteration
            if block.iterations is not None:
                block.current_iteration += 1
                if block.current_iteration >= block.iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)
        except BreakException:
            # Break stops the block regardless of remaining iterations
            block.status = BlockStatus.STOPPED
            if block.name in self.running_blocks:
                self.running_blocks.remove(block.name)

    def execute_statements(self, statements: List[Statement]):
        for stmt in statements:
            self.execute_statement(stmt)

    def execute_statement(self, stmt: Statement):
        if isinstance(stmt, ExpressionStatement):
            self.eval_expression(stmt.expr)
        elif isinstance(stmt, Assignment):
            value = self.eval_expression(stmt.value)
            with self.global_vars_lock:
                # Always assign to global scope for now (WHEN uses global scope)
                self.global_vars[stmt.name] = value
        elif isinstance(stmt, WhenStatement):
            condition_result = self.eval_expression(stmt.condition)
            if condition_result:
                self.execute_statements(stmt.body)
        elif isinstance(stmt, BreakStatement):
            raise BreakException()
        elif isinstance(stmt, ContinueStatement):
            raise ContinueException()
        elif isinstance(stmt, ExitStatement):
            self.exit_requested = True
            raise ExitException()
        elif isinstance(stmt, PassStatement):
            pass
        elif isinstance(stmt, ReturnStatement):
            if len(stmt.values) == 0:
                value = None
            elif len(stmt.values) == 1:
                value = self.eval_expression(stmt.values[0])
            else:
                # Multiple return values - return as tuple
                value = tuple(self.eval_expression(val) for val in stmt.values)
            raise ReturnException(value)
        elif isinstance(stmt, GlobalStatement):
            # Global statements mark variables as global in local scope
            # Store the global declaration for function context
            for name in stmt.names:
                if not hasattr(self, 'current_globals'):
                    self.current_globals = set()
                self.current_globals.add(name)

    def eval_expression(self, expr: Expression) -> Any:
        if isinstance(expr, NumberLiteral):
            return expr.value
        elif isinstance(expr, StringLiteral):
            return expr.value
        elif isinstance(expr, FStringLiteral):
            return self.eval_fstring(expr)
        elif isinstance(expr, BooleanLiteral):
            return expr.value
        elif isinstance(expr, NoneLiteral):
            return None
        elif isinstance(expr, ListLiteral):
            return [self.eval_expression(elem) for elem in expr.elements]
        elif isinstance(expr, TupleLiteral):
            return tuple(self.eval_expression(elem) for elem in expr.elements)
        elif isinstance(expr, IndexExpression):
            obj = self.eval_expression(expr.object)
            index = self.eval_expression(expr.index)
            return obj[index]
        elif isinstance(expr, UnaryOp):
            operand = self.eval_expression(expr.operand)
            if expr.operator == '-':
                return -operand
            elif expr.operator == 'not':
                return not operand
            else:
                raise NotImplementedError(f"Unary operator {expr.operator} not implemented")
        elif isinstance(expr, Identifier):
            with self.global_vars_lock:
                if expr.name in self.global_vars:
                    return self.global_vars[expr.name]
            # Check if it's a function name being referenced
            if expr.name in self.functions:
                # Return a callable wrapper for WHEN functions
                func = self.functions[expr.name]
                def when_function_wrapper(*args, **kwargs):
                    # Convert args to Expression objects if they're not already
                    arg_exprs = []
                    for arg in args:
                        if hasattr(arg, '__dict__') and hasattr(arg, 'type'):
                            # This is likely a tkinter event object - pass it through
                            # Create a special identifier that resolves to this object
                            from ast_nodes import Identifier
                            temp_var_name = f"_temp_arg_{id(arg)}"
                            self.global_vars[temp_var_name] = arg
                            arg_exprs.append(Identifier(temp_var_name))
                        else:
                            # Regular value - wrap in a literal expression
                            from ast_nodes import Number, String, BooleanLiteral
                            if isinstance(arg, (int, float)):
                                arg_exprs.append(Number(arg))
                            elif isinstance(arg, str):
                                arg_exprs.append(String(arg))
                            elif isinstance(arg, bool):
                                arg_exprs.append(BooleanLiteral(arg))
                            else:
                                # Store as temporary variable
                                temp_var_name = f"_temp_arg_{id(arg)}"
                                self.global_vars[temp_var_name] = arg
                                arg_exprs.append(Identifier(temp_var_name))

                    return self.call_function(expr.name, arg_exprs, [])
                return when_function_wrapper
            raise NameError(f"Variable '{expr.name}' not defined")
        elif isinstance(expr, BinaryOp):
            left = self.eval_expression(expr.left)
            right = self.eval_expression(expr.right)
            return self.apply_binary_op(left, expr.operator, right)
        elif isinstance(expr, CallExpression):
            return self.call_function(expr.name, expr.args, expr.kwargs)
        elif isinstance(expr, StartExpression):
            self.start_block(expr.block_name)
            return None
        elif isinstance(expr, StopExpression):
            self.stop_block(expr.block_name)
            return None
        elif isinstance(expr, SaveExpression):
            self.save_block(expr.block_name)
            return None
        elif isinstance(expr, SaveStopExpression):
            self.save_stop_block(expr.block_name)
            return None
        elif isinstance(expr, StartSaveExpression):
            self.start_save_block(expr.block_name)
            return None
        elif isinstance(expr, DiscardExpression):
            self.discard_block(expr.block_name)
            return None
        elif isinstance(expr, MemberAccess):
            # Special handling for block property access
            if isinstance(expr.object, Identifier) and expr.object.name in self.blocks:
                block = self.blocks[expr.object.name]
                if expr.member == "current_iteration":
                    return block.current_iteration
                elif expr.member == "status":
                    return block.status.name
                elif expr.member == "iterations":
                    return block.iterations
                elif expr.member == "has_saved_state":
                    return block.has_saved_state
                else:
                    raise AttributeError(f"Block '{expr.object.name}' has no attribute '{expr.member}'")
            else:
                obj = self.eval_expression(expr.object)
                return getattr(obj, expr.member)
        elif isinstance(expr, MethodCall):
            obj = self.eval_expression(expr.object)
            method = getattr(obj, expr.method)
            args = [self.eval_expression(arg) for arg in expr.args]

            # Handle keyword arguments
            kwargs = {}
            if expr.kwargs:
                for kw in expr.kwargs:
                    kwargs[kw.name] = self.eval_expression(kw.value)

            return method(*args, **kwargs)
        else:
            raise NotImplementedError(f"Expression type {type(expr)} not implemented")

    def eval_fstring(self, fstring: FStringLiteral) -> str:
        """Evaluate an f-string by processing its parts"""
        result = ""

        for part_type, part_value in fstring.parts:
            if part_type == 'str':
                result += part_value
            elif part_type == 'expr':
                # Parse and evaluate the expression
                try:
                    from lexer import Lexer
                    from parser import Parser

                    # Tokenize the expression
                    lexer = Lexer(part_value)
                    tokens = lexer.tokenize()

                    # Parse as expression
                    parser = Parser(tokens)
                    expr = parser.parse_expression()

                    # Evaluate and convert to string
                    value = self.eval_expression(expr)
                    result += str(value)

                except Exception as e:
                    # If evaluation fails, include the error in the string
                    result += f"{{ERROR: {e}}}"

        return result

    def apply_binary_op(self, left: Any, op: str, right: Any) -> Any:
        if op == '+':
            return left + right  # Works for numbers AND strings!
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            return left / right
        elif op == '%':
            return left % right
        elif op == '==' or op == 'eq':
            return left == right
        elif op == '!=' or op == 'ne':
            return left != right
        elif op == '<' or op == 'lt':
            return left < right
        elif op == '>' or op == 'gt':
            return left > right
        elif op == '<=' or op == 'le':
            return left <= right
        elif op == '>=' or op == 'ge':
            return left >= right
        elif op == 'and':
            return left and right
        elif op == 'or':
            return left or right
        elif op == 'in':
            return left in right
        elif op == 'not in':
            return left not in right
        else:
            raise NotImplementedError(f"Operator {op} not implemented")

    def call_function(self, name: str, args: List[Expression], kwargs: List = None) -> Any:
        # Built-in functions
        if name == 'print':
            values = [self.eval_expression(arg) for arg in args]
            print(*values)
            return None
        elif name == 'sleep':
            if args:
                time.sleep(self.eval_expression(args[0]))
            return None
        elif name == 'input':
            prompt = self.eval_expression(args[0]) if args else ""
            return input(prompt)
        elif name == 'int':
            return int(self.eval_expression(args[0]))
        elif name == 'str':
            return str(self.eval_expression(args[0]))
        elif name == 'len':
            return len(self.eval_expression(args[0]))
        elif name == 'rjust':
            if len(args) >= 2:
                string = str(self.eval_expression(args[0]))
                width = self.eval_expression(args[1])
                return string.rjust(width)
            return str(self.eval_expression(args[0]))
        elif name == 'globals':
            # Return reference to global namespace for direct manipulation
            return self.global_vars
        elif name == 'setattr':
            # Allow setting global variables from functions
            if len(args) >= 3:
                obj = self.eval_expression(args[0])
                attr = self.eval_expression(args[1])
                value = self.eval_expression(args[2])
                setattr(obj, attr, value)
            return None
        elif name == 'exit':
            self.exit_requested = True
            raise ExitException()

        # Graphics functions
        elif name == 'window':
            if len(args) == 0:
                graphics.window()
            elif len(args) == 2:
                width = self.eval_expression(args[0])
                height = self.eval_expression(args[1])
                graphics.window(width, height)
            elif len(args) == 3:
                width = self.eval_expression(args[0])
                height = self.eval_expression(args[1])
                title = self.eval_expression(args[2])
                graphics.window(width, height, title)
            return None
        elif name == 'close_window':
            graphics.close()
            return None
        elif name == 'is_window_open':
            return graphics.is_open()
        elif name == 'clear':
            if args:
                color = self.eval_expression(args[0])
                graphics.clear(color)
            else:
                graphics.clear()
            return None
        elif name == 'fill':
            color = self.eval_expression(args[0])
            graphics.fill(color)
            return None
        elif name == 'rect':
            if len(args) >= 4:
                x = self.eval_expression(args[0])
                y = self.eval_expression(args[1])
                width = self.eval_expression(args[2])
                height = self.eval_expression(args[3])
                color = self.eval_expression(args[4]) if len(args) > 4 else "black"
                graphics.rect(x, y, width, height, color)
            return None
        elif name == 'circle':
            if len(args) >= 3:
                x = self.eval_expression(args[0])
                y = self.eval_expression(args[1])
                radius = self.eval_expression(args[2])
                color = self.eval_expression(args[3]) if len(args) > 3 else "black"
                graphics.circle(x, y, radius, color)
            return None
        elif name == 'line':
            if len(args) >= 4:
                x1 = self.eval_expression(args[0])
                y1 = self.eval_expression(args[1])
                x2 = self.eval_expression(args[2])
                y2 = self.eval_expression(args[3])
                color = self.eval_expression(args[4]) if len(args) > 4 else "black"
                width = self.eval_expression(args[5]) if len(args) > 5 else 1
                graphics.line(x1, y1, x2, y2, color, width)
            return None
        elif name == 'text':
            if len(args) >= 3:
                x = self.eval_expression(args[0])
                y = self.eval_expression(args[1])
                message = self.eval_expression(args[2])
                color = self.eval_expression(args[3]) if len(args) > 3 else "black"
                size = self.eval_expression(args[4]) if len(args) > 4 else 12
                graphics.text(x, y, message, color, size)
            return None
        elif name == 'update':
            graphics.update()
            return None
        elif name == 'color':
            if args:
                color_name = self.eval_expression(args[0])
                return graphics.get_color(color_name)
            return None
        elif name == 'is_key_pressed':
            if args:
                key = self.eval_expression(args[0])
                return graphics.is_key_pressed(key)
            return False
        elif name == 'get_last_key':
            return graphics.get_last_key()
        elif name == 'clear_last_key':
            graphics.clear_last_key()
            return None
        # Check if it's a block to execute (OS blocks can be called as functions)
        elif name in self.blocks:
            block = self.blocks[name]
            self.execute_statements(block.body)
            return None
        # Check if it's a Python object/class being called
        elif name in self.global_vars:
            obj = self.global_vars[name]
            if callable(obj):
                # Evaluate arguments
                evaluated_args = [self.eval_expression(arg) for arg in args]

                # Evaluate keyword arguments
                evaluated_kwargs = {}
                if kwargs:
                    for kw in kwargs:
                        evaluated_kwargs[kw.name] = self.eval_expression(kw.value)

                return obj(*evaluated_args, **evaluated_kwargs)
        # User-defined functions
        elif name in self.functions:
            func = self.functions[name]
            if len(args) != len(func.params):
                raise ValueError(f"Function {name} expects {len(func.params)} arguments, got {len(args)}")

            # Create function execution context that can modify globals
            saved_params = {}

            # Save parameter values if they exist in globals
            for param in func.params:
                if param in self.global_vars:
                    saved_params[param] = self.global_vars[param]

            # Bind parameters
            for param, arg in zip(func.params, args):
                self.global_vars[param] = self.eval_expression(arg)

            # Execute function body with access to modify globals
            try:
                self.execute_statements(func.body)
                result = None
            except ReturnException as ret:
                result = ret.value
            finally:
                # Only restore original parameter values, keep all other global changes
                for param in func.params:
                    if param in saved_params:
                        self.global_vars[param] = saved_params[param]
                    else:
                        # Remove parameter if it wasn't originally a global
                        if param in self.global_vars:
                            del self.global_vars[param]

            return result
        else:
            raise NameError(f"Function '{name}' not defined")

    def start_block(self, block_name: str):
        if block_name not in self.blocks:
            raise NameError(f"Block '{block_name}' not defined")

        block = self.blocks[block_name]

        # OS blocks execute immediately once and don't get added to running blocks
        if block.block_type == "os":
            self.execute_statements(block.body)
            return

        # Reset and start the block
        block.reset()
        block.status = BlockStatus.RUNNING

        # Handle parallel vs cooperative execution
        if block.is_parallel:
            # Start in its own thread
            block.thread = threading.Thread(
                target=self.run_parallel_block,
                args=(block,),
                name=f"when-{block_name}",
                daemon=False  # Don't make daemon so we can properly wait for them
            )
            block.thread.start()
            self.parallel_threads.append(block.thread)
            # print(f"[PARALLEL] Started {block_name} in thread {block.thread.name}")
        else:
            # Add to cooperative scheduling
            if block_name not in self.running_blocks:
                self.running_blocks.append(block_name)

    def stop_block(self, block_name: str):
        if block_name not in self.blocks:
            return

        block = self.blocks[block_name]

        if block.is_parallel:
            # Stop parallel thread
            block.should_stop.set()
            block.status = BlockStatus.STOPPED
            if block.thread and block.thread.is_alive():
                # print(f"[PARALLEL] Stopping {block_name} thread...")
                block.thread.join(timeout=2.0)
                if block.thread.is_alive():
                    pass  # Thread did not stop gracefully
        else:
            # Stop cooperative block
            if block_name in self.running_blocks:
                block.status = BlockStatus.STOPPED
                self.running_blocks.remove(block_name)

    def save_block(self, block_name: str):
        """Save the current state of a block"""
        if block_name not in self.blocks:
            raise NameError(f"Block '{block_name}' not defined")
        block = self.blocks[block_name]
        block.save_state()
        print(f"[SAVE] Block '{block_name}' state saved (iteration: {block.current_iteration})")

    def save_stop_block(self, block_name: str):
        """Save the current state and stop a block"""
        if block_name not in self.blocks:
            raise NameError(f"Block '{block_name}' not defined")
        block = self.blocks[block_name]
        block.save_state()
        print(f"[SAVESTOP] Block '{block_name}' state saved and stopped (iteration: {block.current_iteration})")
        self.stop_block(block_name)

    def start_save_block(self, block_name: str):
        """Start a block from its saved state, or from beginning if no saved state"""
        if block_name not in self.blocks:
            raise NameError(f"Block '{block_name}' not defined")
        block = self.blocks[block_name]

        # OS blocks can't use saved state - they always execute immediately once
        if block.block_type == "os":
            print(f"[STARTSAVE] OS block '{block_name}' executed (OS blocks don't support saved state)")
            self.execute_statements(block.body)
            return

        # Try to restore saved state
        if block.restore_state():
            print(f"[STARTSAVE] Block '{block_name}' started from saved state (iteration: {block.current_iteration})")
        else:
            print(f"[STARTSAVE] Block '{block_name}' started from beginning (no saved state)")
            block.reset()

        # Start the block
        block.status = BlockStatus.RUNNING

        # Handle parallel vs cooperative execution
        if block.is_parallel:
            # Start in its own thread
            block.thread = threading.Thread(
                target=self.run_parallel_block,
                args=(block,),
                daemon=True
            )
            block.thread.start()
        else:
            # Add to cooperative execution list
            if block_name not in self.running_blocks:
                self.running_blocks.append(block_name)

    def discard_block(self, block_name: str):
        """Discard saved state for a block"""
        if block_name not in self.blocks:
            raise NameError(f"Block '{block_name}' not defined")
        block = self.blocks[block_name]

        if block.discard_saved_state():
            print(f"[DISCARD] Block '{block_name}' saved state discarded")
        else:
            print(f"[DISCARD] ERROR: Discard called for no save! Did you forget to WHEN your block '{block_name}'?")

    def handle_import(self, decl: ImportDeclaration):
        try:
            module = __import__(decl.module)
            name = decl.alias if decl.alias else decl.module
            self.global_vars[name] = module
            self.modules[name] = module
        except ImportError as e:
            raise ImportError(f"Cannot import module '{decl.module}': {e}")

    def handle_from_import(self, decl: FromImportDeclaration):
        try:
            module = __import__(decl.module, fromlist=decl.names)
            for name, alias in zip(decl.names, decl.aliases):
                if hasattr(module, name):
                    attr = getattr(module, name)
                    var_name = alias if alias else name
                    self.global_vars[var_name] = attr
                else:
                    raise ImportError(f"Cannot import '{name}' from '{decl.module}'")
        except ImportError as e:
            raise ImportError(f"Cannot import from module '{decl.module}': {e}")

    def run_parallel_block(self, block: Block):
        """Run a block in its own thread"""
        try:
            # print(f"[PARALLEL] {block.name} thread started")

            if block.block_type == "de":
                # Declarative block - run exactly N times
                while (block.current_iteration < block.iterations and
                       not block.should_stop.is_set() and
                       not self.exit_requested):

                    try:
                        self.execute_statements(block.body)
                        block.current_iteration += 1

                        # Small delay to allow cooperative behavior
                        time.sleep(0.01)

                    except BreakException:
                        break
                    except ContinueException:
                        # Continue still counts as an iteration
                        block.current_iteration += 1
                        continue

                # print(f"[PARALLEL] {block.name} completed {block.current_iteration} iterations")

            elif block.block_type == "fo":
                # Forever block - run until stopped
                while (not block.should_stop.is_set() and
                       not self.exit_requested):

                    try:
                        self.execute_statements(block.body)

                        # Small delay to prevent tight loops
                        time.sleep(0.01)

                    except BreakException:
                        break
                    except ContinueException:
                        continue

        except Exception as e:
            print(f"[PARALLEL] Error in {block.name}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            block.status = BlockStatus.COMPLETED
            # print(f"[PARALLEL] {block.name} thread finished")

    def cleanup_parallel_threads(self):
        """Clean up all parallel threads"""
        # print("[PARALLEL] Cleaning up threads...")

        # Signal all parallel blocks to stop
        for block in self.blocks.values():
            if block.is_parallel and block.thread:
                block.should_stop.set()

        # Wait for threads to finish
        for thread in self.parallel_threads:
            if thread.is_alive():
                thread.join(timeout=3.0)
                if thread.is_alive():
                    pass  # Thread did not stop

        self.parallel_threads.clear()
        # print("[PARALLEL] Cleanup complete")