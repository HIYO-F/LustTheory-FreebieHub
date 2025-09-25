import time
import sys
import os
import threading
import queue
from typing import Dict, Any, Optional, List, Union
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
    def __init__(self, name: str, body: List[Statement], iterations: Union[int, tuple, None] = None, block_type: str = "fo", is_parallel: bool = False):
        self.name = name
        self.body = body
        self.iterations = iterations  # Can be int, ('var', varname), or None
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
        self.classes: Dict[str, ClassDeclaration] = {}
        self.blocks: Dict[str, Block] = {}
        self.running_blocks: List[str] = []
        self.exit_requested = False
        self.modules: Dict[str, Any] = {}
        self.module_namespaces: Dict[str, Dict[str, Any]] = {}  # Store module namespaces
        self.function_modules: Dict[str, str] = {}  # Track which module a function belongs to
        self.current_module: Optional[str] = None  # Track current executing module
        self.global_vars_lock = threading.Lock()
        self.parallel_threads: List[threading.Thread] = []
        self.hot_reloader = None
        self.enable_hot_reload = enable_hot_reload
        self.source_file = source_file

        # Add built-in functions for error handling
        self.setup_builtins()

    def setup_builtins(self):
        """Set up built-in functions for error handling and utilities."""

        # safe_call: Safely call a function and return (success, result/error)
        def safe_call(func, *args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return {"success": True, "result": result, "error": None}
            except Exception as e:
                return {"success": False, "result": None, "error": str(e), "error_type": type(e).__name__}

        # get_error: Extract error from safe_call result
        def get_error(result):
            if isinstance(result, dict) and "error" in result:
                return result.get("error", None)
            return None

        # is_success: Check if safe_call succeeded
        def is_success(result):
            if isinstance(result, dict) and "success" in result:
                return result["success"]
            return False

        # get_result: Extract result from safe_call
        def get_result(result):
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return None

        # has_attr: Check if object has attribute (safe hasattr)
        def has_attr(obj, attr_name):
            try:
                return hasattr(obj, attr_name)
            except:
                return False

        # safe_getattr: Safely get attribute from object
        def safe_getattr(obj, attr_name, default=None):
            try:
                return getattr(obj, attr_name, default)
            except:
                return default

        # type_of: Get type name of object
        def type_of(obj):
            return type(obj).__name__

        # is_type: Check if object is of certain type
        def is_type(obj, type_name):
            return type(obj).__name__ == type_name

        # Add all built-ins to global vars
        self.global_vars["safe_call"] = safe_call
        self.global_vars["get_error"] = get_error
        self.global_vars["is_success"] = is_success
        self.global_vars["get_result"] = get_result
        self.global_vars["has_attr"] = has_attr
        self.global_vars["safe_getattr"] = safe_getattr
        self.global_vars["type_of"] = type_of
        self.global_vars["is_type"] = is_type
        self.global_vars["isinstance"] = isinstance  # Add Python's isinstance too
        self.global_vars["type"] = type  # Add Python's type too

    def interpret(self, program: Program):
        # Process declarations
        for decl in program.declarations:
            if isinstance(decl, VarDeclaration):
                self.global_vars[decl.name] = self.eval_expression(decl.value)
            elif isinstance(decl, FuncDeclaration):
                self.functions[decl.name] = decl
            elif isinstance(decl, ClassDeclaration):
                self.classes[decl.name] = decl
                # Create a class constructor function with proper closure
                def make_constructor(class_decl):
                    return lambda *args, **kwargs: self.instantiate_class(class_decl, args, kwargs)
                self.global_vars[decl.name] = make_constructor(decl)
            elif isinstance(decl, ImportDeclaration):
                self.handle_import(decl)
            elif isinstance(decl, FromImportDeclaration):
                self.handle_from_import(decl)

        # Register blocks (check specific types first!)
        for block in program.blocks:
            if isinstance(block, OSBlock):
                self.blocks[block.name] = Block(block.name, block.body, None, "os", False)
            elif isinstance(block, ParallelDEBlock):
                # Check if iterations is a variable name (stored as string from parser)
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                self.blocks[block.name] = Block(block.name, block.body, iterations, "de", True)
            elif isinstance(block, ParallelFOBlock):
                self.blocks[block.name] = Block(block.name, block.body, None, "fo", True)
            elif isinstance(block, DEBlock):
                # Check if iterations is a variable name (stored as string from parser)
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                self.blocks[block.name] = Block(block.name, block.body, iterations, "de", False)
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

    def resolve_block_iterations(self, block: Block) -> int:
        """Resolve the iteration count for a DE block"""
        if block.iterations is None:
            return None
        
        if isinstance(block.iterations, int):
            return block.iterations
        
        if isinstance(block.iterations, tuple) and block.iterations[0] == 'var':
            var_name = block.iterations[1]
            if var_name in self.global_vars:
                value = self.global_vars[var_name]
                try:
                    return int(value)
                except (TypeError, ValueError):
                    raise ValueError(f"Variable '{var_name}' cannot be converted to iteration count: {value}")
            else:
                raise NameError(f"Iteration variable '{var_name}' not defined")
        
        return block.iterations

    def execute_block_iteration(self, block: Block):
        if block.status != BlockStatus.RUNNING:
            return

        # Resolve iterations if needed
        iterations = self.resolve_block_iterations(block)

        # For DE blocks, check if we've already completed all iterations
        if iterations is not None and block.current_iteration >= iterations:
            block.status = BlockStatus.COMPLETED
            if block.name in self.running_blocks:
                self.running_blocks.remove(block.name)
            return

        try:
            # Set module context if this block is from a module
            saved_module = self.current_module
            if '.' in block.name:
                # Block name includes module prefix (e.g., "whGame.game_loop")
                module_name = block.name.split('.')[0]
                if module_name in self.module_namespaces:
                    self.current_module = module_name

            # Execute one iteration
            self.execute_statements(block.body)

            # Increment iteration counter AFTER successful execution
            if iterations is not None:
                block.current_iteration += 1
                # Check if we've now completed all iterations
                if block.current_iteration >= iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)

        except ContinueException:
            # Continue still counts as an iteration
            if iterations is not None:
                block.current_iteration += 1
                if block.current_iteration >= iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)
        except BreakException:
            # Break stops the block regardless of remaining iterations
            block.status = BlockStatus.STOPPED
            if block.name in self.running_blocks:
                self.running_blocks.remove(block.name)
        finally:
            # Restore module context
            if '.' in block.name:
                self.current_module = saved_module

    def execute_statements(self, statements: List[Statement]):
        for stmt in statements:
            self.execute_statement(stmt)

    def execute_statement(self, stmt: Statement):
        if isinstance(stmt, ExpressionStatement):
            self.eval_expression(stmt.expr)
        elif isinstance(stmt, Assignment):
            value = self.eval_expression(stmt.value)
            with self.global_vars_lock:
                # In module context, ALL assignments go to module namespace
                # (including those marked global - they're global TO THE MODULE)
                if self.current_module and self.current_module in self.module_namespaces:
                    # print(f"[DEBUG] Updating module '{self.current_module}' var '{stmt.name}' = {value}")
                    self.module_namespaces[self.current_module][stmt.name] = value
                    # Also update the module object if it exists
                    if self.current_module in self.modules:
                        setattr(self.modules[self.current_module], stmt.name, value)
                else:
                    # Otherwise use interpreter global scope
                    # print(f"[DEBUG] Updating global var '{stmt.name}' = {value} (module: {self.current_module})")
                    self.global_vars[stmt.name] = value
        elif isinstance(stmt, IndexAssignment):
            obj = self.eval_expression(stmt.object)
            index = self.eval_expression(stmt.index)
            value = self.eval_expression(stmt.value)
            obj[index] = value
        elif isinstance(stmt, AttributeAssignment):
            obj = self.eval_expression(stmt.object)
            value = self.eval_expression(stmt.value)
            # Set the attribute on the object
            setattr(obj, stmt.attribute, value)
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
        elif isinstance(expr, DictLiteral):
            return {self.eval_expression(k): self.eval_expression(v)
                    for k, v in zip(expr.keys, expr.values)}
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
        elif isinstance(expr, TernaryOp):
            condition = self.eval_expression(expr.condition)
            if condition:
                return self.eval_expression(expr.true_expr)
            else:
                return self.eval_expression(expr.false_expr)
        elif isinstance(expr, Identifier):
            with self.global_vars_lock:
                # If in module context, check module namespace first
                if self.current_module and self.current_module in self.module_namespaces:
                    if expr.name in self.module_namespaces[self.current_module]:
                        return self.module_namespaces[self.current_module][expr.name]
                # Then check global vars
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
                            from ast_nodes import NumberLiteral, StringLiteral, BooleanLiteral
                            if isinstance(arg, (int, float)):
                                arg_exprs.append(NumberLiteral(arg))
                            elif isinstance(arg, str):
                                arg_exprs.append(StringLiteral(arg))
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
                    return self.resolve_block_iterations(block)
                elif expr.member == "has_saved_state":
                    return block.has_saved_state
                else:
                    raise AttributeError(f"Block '{expr.object.name}' has no attribute '{expr.member}'")
            else:
                obj = self.eval_expression(expr.object)
                attr = getattr(obj, expr.member)
                # If it's a FuncDeclaration from a module, return a callable wrapper
                if isinstance(attr, FuncDeclaration):
                    # Store it in functions so it can be called
                    func_name = f"{expr.object.name if isinstance(expr.object, Identifier) else 'module'}.{expr.member}"
                    self.functions[func_name] = attr
                    # Return the function name so CallExpression can find it
                    return func_name
                return attr
        elif isinstance(expr, MethodCall):
            # DEBUG
            # if expr.method == "is_key_pressed":
            #     print(f"[DEBUG MethodCall] is_key_pressed args={expr.args}, first arg={expr.args[0] if expr.args else None}")
            # Check if this is a block method from a module
            if isinstance(expr.object, MemberAccess):
                # It might be module.block.start()
                module_obj = self.eval_expression(expr.object.object)
                attr = getattr(module_obj, expr.object.member)
                if isinstance(attr, Block):
                    # It's a block method call
                    if expr.method == "start":
                        self.start_block(attr.name)
                        return None
                    elif expr.method == "stop":
                        self.stop_block(attr.name)
                        return None
                    else:
                        raise AttributeError(f"Block has no method '{expr.method}'")

            obj = self.eval_expression(expr.object)

            # If obj is a Block, handle its methods
            if isinstance(obj, Block):
                if expr.method == "start":
                    self.start_block(obj.name)
                    return None
                elif expr.method == "stop":
                    self.stop_block(obj.name)
                    return None
                else:
                    raise AttributeError(f"Block has no method '{expr.method}'")

            method = getattr(obj, expr.method)

            # If the method is a FuncDeclaration from a module, call it properly
            if isinstance(method, FuncDeclaration):
                # Create a qualified name for the function
                if isinstance(expr.object, Identifier):
                    func_name = f"{expr.object.name}.{expr.method}"
                else:
                    func_name = expr.method

                # Register the function if needed
                if func_name not in self.functions:
                    self.functions[func_name] = method
                    # Track its module if the object is a module
                    if isinstance(expr.object, Identifier) and expr.object.name in self.modules:
                        self.function_modules[func_name] = expr.object.name

                # Call it through our function call mechanism
                # print(f"[DEBUG] Calling function '{func_name}' via MethodCall")
                return self.call_function(func_name, expr.args, expr.kwargs)

            # Regular method call
            args = []
            for arg in expr.args:
                arg_value = self.eval_expression(arg)
                # Wrap FuncDeclaration objects in Python callables for tkinter compatibility
                if isinstance(arg_value, FuncDeclaration):
                    # Create a wrapper that tkinter can call
                    def make_wrapper(func_decl, interpreter):
                        def wrapper(event=None):
                            # When functions expect an event parameter
                            # We need to pass it as a variable, not an argument
                            func_name = func_decl.name

                            # Save current event if exists
                            saved_event = None
                            for fname, mod in interpreter.function_modules.items():
                                if fname.endswith(f".{func_name}") or fname == func_name:
                                    # Function belongs to a module
                                    if mod in interpreter.module_namespaces:
                                        if 'event' in interpreter.module_namespaces[mod]:
                                            saved_event = interpreter.module_namespaces[mod]['event']
                                        # Set event in module namespace
                                        if event:
                                            interpreter.module_namespaces[mod]['event'] = event

                                    old_module = interpreter.current_module
                                    interpreter.current_module = mod
                                    try:
                                        # Call function - it will access event from module namespace
                                        from ast_nodes import Identifier, MemberAccess
                                        # Create an expression that represents the event parameter
                                        event_expr = Identifier('event') if event else None
                                        args = [event_expr] if event_expr and func_decl.params and len(func_decl.params) > 0 else []
                                        result = interpreter.call_function(fname, args)
                                    finally:
                                        interpreter.current_module = old_module
                                        # Restore saved event
                                        if mod in interpreter.module_namespaces:
                                            if saved_event is not None:
                                                interpreter.module_namespaces[mod]['event'] = saved_event
                                            elif 'event' in interpreter.module_namespaces[mod] and event:
                                                del interpreter.module_namespaces[mod]['event']
                                    return result

                            # If not found in modules, try global
                            if 'event' in interpreter.global_vars:
                                saved_event = interpreter.global_vars['event']
                            if event:
                                interpreter.global_vars['event'] = event
                            try:
                                from ast_nodes import Identifier
                                event_expr = Identifier('event') if event else None
                                args = [event_expr] if event_expr and func_decl.params and len(func_decl.params) > 0 else []
                                return interpreter.call_function(func_name, args)
                            finally:
                                if saved_event is not None:
                                    interpreter.global_vars['event'] = saved_event
                                elif 'event' in interpreter.global_vars and event:
                                    del interpreter.global_vars['event']
                        return wrapper
                    arg_value = make_wrapper(arg_value, self)
                args.append(arg_value)

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
        elif op == '//':
            return int(left // right)
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
        # print(f"[DEBUG] call_function called with name='{name}'")

        # Check module namespace first if we're in a module context
        if self.current_module and self.current_module in self.module_namespaces:
            if name in self.module_namespaces[self.current_module]:
                obj = self.module_namespaces[self.current_module][name]
                if callable(obj):
                    # It's a Python callable from the module
                    evaluated_args = [self.eval_expression(arg) for arg in args]
                    evaluated_kwargs = {}
                    if kwargs:
                        for kw in kwargs:
                            evaluated_kwargs[kw.name] = self.eval_expression(kw.value)
                    return obj(*evaluated_args, **evaluated_kwargs)
                elif isinstance(obj, FuncDeclaration):
                    # It's a When function in the same module
                    qualified_name = f"{self.current_module}.{name}"
                    if qualified_name not in self.functions:
                        self.functions[qualified_name] = obj
                        self.function_modules[qualified_name] = self.current_module
                    return self.call_function(qualified_name, args, kwargs)
                elif isinstance(obj, Block):
                    # It's a block in the same module - execute it directly
                    self.execute_statements(obj.body)
                    return None

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
        elif name == 'abs':
            return abs(self.eval_expression(args[0]))
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
            # print(f"[DEBUG] Found '{name}' in global_vars, type: {type(obj)}, callable: {callable(obj)}")
            if callable(obj):
                # Evaluate arguments
                evaluated_args = [self.eval_expression(arg) for arg in args]

                # Evaluate keyword arguments
                evaluated_kwargs = {}
                if kwargs:
                    for kw in kwargs:
                        evaluated_kwargs[kw.name] = self.eval_expression(kw.value)

                return obj(*evaluated_args, **evaluated_kwargs)
        # Check if it's returning early somewhere
        elif False:
            pass
        # User-defined functions
        elif name in self.functions:
            func = self.functions[name]
            # print(f"[DEBUG] Found function '{name}' in self.functions")

            # Count required and optional parameters
            required_params = [p for p in func.params if p.default is None]
            optional_params = [p for p in func.params if p.default is not None]

            if len(args) < len(required_params):
                raise ValueError(f"Function {name} expects at least {len(required_params)} arguments, got {len(args)}")
            if len(args) > len(func.params):
                raise ValueError(f"Function {name} expects at most {len(func.params)} arguments, got {len(args)}")

            # Create function execution context that can modify globals
            saved_params = {}

            # Save parameter values if they exist in globals or module namespace
            saved_module_params = {}
            for param in func.params:
                param_name = param.name if hasattr(param, 'name') else param
                if param_name in self.global_vars:
                    saved_params[param_name] = self.global_vars[param_name]
                # Also save module namespace parameters if this is a module function
                if name in self.function_modules:
                    module = self.function_modules[name]
                    if module in self.module_namespaces and param_name in self.module_namespaces[module]:
                        saved_module_params[param_name] = self.module_namespaces[module][param_name]

            # Bind parameters with provided arguments
            for i, arg in enumerate(args):
                param = func.params[i]
                param_name = param.name if hasattr(param, 'name') else param
                arg_value = self.eval_expression(arg)
                # DEBUG
                # if name == "whGame.is_key_pressed":
                #     print(f"[DEBUG] Binding param '{param_name}' = {arg_value} (from arg {arg})")
                self.global_vars[param_name] = arg_value

                # If this is a module function, also set the parameter in the module namespace
                if name in self.function_modules:
                    module = self.function_modules[name]
                    if module in self.module_namespaces:
                        self.module_namespaces[module][param_name] = arg_value

            # Bind remaining parameters with default values
            for i in range(len(args), len(func.params)):
                param = func.params[i]
                param_name = param.name if hasattr(param, 'name') else param
                if hasattr(param, 'default') and param.default is not None:
                    self.global_vars[param_name] = self.eval_expression(param.default)
                else:
                    raise ValueError(f"No value provided for required parameter {param_name}")

            # Set module context if this function belongs to a module
            saved_module = self.current_module
            if name in self.function_modules:
                self.current_module = self.function_modules[name]
                # print(f"[DEBUG] Executing function '{name}' in module '{self.current_module}'")

            # Execute function body with access to modify globals
            try:
                # print(f"[DEBUG] Executing {len(func.body)} statements in function '{name}'")
                self.execute_statements(func.body)
                result = None
            except ReturnException as ret:
                result = ret.value
            finally:
                # Restore module context
                self.current_module = saved_module
                # Only restore original parameter values, keep all other global changes
                for param in func.params:
                    param_name = param.name if hasattr(param, 'name') else param
                    if param_name in saved_params:
                        self.global_vars[param_name] = saved_params[param_name]
                    else:
                        # Remove parameter if it wasn't originally a global
                        if param_name in self.global_vars:
                            del self.global_vars[param_name]

                    # Also restore module namespace parameters
                    if name in self.function_modules:
                        module = self.function_modules[name]
                        if module in self.module_namespaces:
                            if param_name in saved_module_params:
                                self.module_namespaces[module][param_name] = saved_module_params[param_name]
                            else:
                                # Remove parameter if it wasn't originally in module namespace
                                if param_name in self.module_namespaces[module]:
                                    del self.module_namespaces[module][param_name]

            return result
        else:
            # print(f"[DEBUG] Function '{name}' not found in self.functions")
            # print(f"[DEBUG] Available functions: {list(self.functions.keys())[:10]}")
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
        
        # Resolve iterations for DE blocks if they're variable-based
        if block.block_type == "de":
            if isinstance(block.iterations, tuple) and block.iterations[0] == 'var':
                # Don't resolve yet - let it be resolved each time it's needed
                pass
        
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
        # Check if it's a When file import
        when_file = decl.module + '.when'
        if os.path.exists(when_file):
            # Import When package
            self.import_when_package(decl.module, decl.alias)
        else:
            # Try as Python module
            try:
                # For dotted imports like urllib.request, we need to handle differently
                if '.' in decl.module:
                    parts = decl.module.split('.')
                    # Import the top-level module
                    top_module = __import__(decl.module)

                    # Store the top-level module so we can access it
                    self.global_vars[parts[0]] = top_module
                    self.modules[parts[0]] = top_module

                    # Navigate to the actual submodule
                    module = top_module
                    for part in parts[1:]:
                        module = getattr(module, part)

                    # If there's an alias, use it for the full module
                    if decl.alias:
                        self.global_vars[decl.alias] = module
                        self.modules[decl.alias] = module
                else:
                    module = __import__(decl.module)
                    name = decl.alias if decl.alias else decl.module
                    self.global_vars[name] = module
                    self.modules[name] = module
            except ImportError as e:
                raise ImportError(f"Cannot import module '{decl.module}': {e}")

    def handle_from_import(self, decl: FromImportDeclaration):
        # Check if it's a When file import
        when_file = decl.module + '.when'
        if os.path.exists(when_file):
            # Import specific items from When package
            self.import_from_when_package(decl.module, decl.names, decl.aliases)
        else:
            # Try as Python module
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

    def import_when_package(self, module_name: str, alias: Optional[str] = None):
        """Import a When package, exposing its functions and blocks but not executing main"""
        when_file = module_name + '.when'

        # Read and parse the When file
        with open(when_file, 'r') as f:
            source = f.read()

        from lexer import Lexer
        from parser import Parser

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        # Determine the module name early
        name = alias if alias else module_name

        # Create a module namespace
        module_namespace = {}

        # Store the namespace for this module
        self.module_namespaces[name] = module_namespace

        # Process imports first - add them to module namespace
        for decl in program.declarations:
            if isinstance(decl, ImportDeclaration):
                # Import the Python module and add to namespace
                try:
                    # For dotted imports like urllib.request
                    if '.' in decl.module:
                        parts = decl.module.split('.')
                        # Import and store the top-level module
                        top_module = __import__(decl.module)
                        module_namespace[parts[0]] = top_module

                        # Navigate to the actual submodule
                        imported_module = top_module
                        for part in parts[1:]:
                            imported_module = getattr(imported_module, part)

                        # If there's an alias, use it
                        if decl.alias:
                            module_namespace[decl.alias] = imported_module
                    else:
                        imported_module = __import__(decl.module)
                        name_in_namespace = decl.alias if decl.alias else decl.module
                        module_namespace[name_in_namespace] = imported_module
                except ImportError as e:
                    raise ImportError(f"Cannot import module '{decl.module}': {e}")
            elif isinstance(decl, FromImportDeclaration):
                # Import specific items from Python module
                try:
                    imported_module = __import__(decl.module, fromlist=decl.names)
                    for import_name, alias in zip(decl.names, decl.aliases):
                        if hasattr(imported_module, import_name):
                            attr = getattr(imported_module, import_name)
                            var_name = alias if alias else import_name
                            module_namespace[var_name] = attr
                except ImportError as e:
                    raise ImportError(f"Cannot import from module '{decl.module}': {e}")

        # Process other declarations (variables, functions, and classes)
        for decl in program.declarations:
            if isinstance(decl, VarDeclaration):
                module_namespace[decl.name] = self.eval_expression(decl.value)
            elif isinstance(decl, FuncDeclaration):
                # Register the function with its module context
                qualified_func_name = f"{name}.{decl.name}"
                self.functions[qualified_func_name] = decl
                self.function_modules[qualified_func_name] = name
                # Don't register unqualified name to avoid conflicts
                # self.functions[decl.name] = decl
                # self.function_modules[decl.name] = name
                # Store the declaration for the module
                module_namespace[decl.name] = decl
            elif isinstance(decl, ClassDeclaration):
                # Register the class
                self.classes[decl.name] = decl
                # Create a class constructor
                def make_constructor(class_decl):
                    return lambda *args, **kwargs: self.instantiate_class(class_decl, args, kwargs)
                module_namespace[decl.name] = make_constructor(decl)

        # Process blocks (OS, DE, FO)
        for block in program.blocks:
            block_name = block.name
            qualified_name = f"{name}.{block_name}"
            if isinstance(block, OSBlock):
                block_obj = Block(qualified_name, block.body, None, "os", False)
                module_namespace[block_name] = block_obj
                self.blocks[qualified_name] = block_obj
            elif isinstance(block, ParallelDEBlock):
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                block_obj = Block(qualified_name, block.body, iterations, "de", True)
                module_namespace[block_name] = block_obj
                self.blocks[qualified_name] = block_obj
            elif isinstance(block, ParallelFOBlock):
                block_obj = Block(qualified_name, block.body, None, "fo", True)
                module_namespace[block_name] = block_obj
                self.blocks[qualified_name] = block_obj
            elif isinstance(block, DEBlock):
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                block_obj = Block(qualified_name, block.body, iterations, "de", False)
                module_namespace[block_name] = block_obj
                self.blocks[qualified_name] = block_obj
            else:  # Regular FOBlock
                block_obj = Block(qualified_name, block.body, None, "fo", False)
                module_namespace[block_name] = block_obj
                self.blocks[qualified_name] = block_obj

        # Create a custom module class that uses the namespace dictionary
        class WhenModule:
            def __init__(self, namespace):
                self._namespace = namespace

            def __getattr__(self, name):
                if name in self._namespace:
                    return self._namespace[name]
                raise AttributeError(f"module '{name}' has no attribute '{name}'")

            def __setattr__(self, name, value):
                if name == '_namespace':
                    object.__setattr__(self, name, value)
                else:
                    self._namespace[name] = value

        # Store the module
        self.modules[name] = WhenModule(module_namespace)
        self.global_vars[name] = self.modules[name]

        # Don't add FuncDeclarations to global namespace with module prefix
        # They should only be in self.functions
        for key, value in module_namespace.items():
            if not isinstance(value, FuncDeclaration):
                self.global_vars[f"{name}.{key}"] = value

    def import_from_when_package(self, module_name: str, names: List[str], aliases: List[Optional[str]]):
        """Import specific items from a When package"""
        when_file = module_name + '.when'

        # Read and parse the When file
        with open(when_file, 'r') as f:
            source = f.read()

        from lexer import Lexer
        from parser import Parser

        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()

        # Create a temporary namespace to collect items
        temp_namespace = {}

        # Process declarations
        for decl in program.declarations:
            if isinstance(decl, VarDeclaration):
                temp_namespace[decl.name] = self.eval_expression(decl.value)
            elif isinstance(decl, FuncDeclaration):
                temp_namespace[decl.name] = decl
            elif isinstance(decl, ClassDeclaration):
                # Create a class constructor
                def make_constructor(class_decl):
                    return lambda *args, **kwargs: self.instantiate_class(class_decl, args, kwargs)
                temp_namespace[decl.name] = make_constructor(decl)

        # Process blocks
        for block in program.blocks:
            block_name = block.name
            if isinstance(block, OSBlock):
                temp_namespace[block_name] = Block(block_name, block.body, None, "os", False)
            elif isinstance(block, ParallelDEBlock):
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                temp_namespace[block_name] = Block(block_name, block.body, iterations, "de", True)
            elif isinstance(block, ParallelFOBlock):
                temp_namespace[block_name] = Block(block_name, block.body, None, "fo", True)
            elif isinstance(block, DEBlock):
                if isinstance(block.iterations, str):
                    iterations = ('var', block.iterations)
                else:
                    iterations = block.iterations
                temp_namespace[block_name] = Block(block_name, block.body, iterations, "de", False)
            else:  # Regular FOBlock
                temp_namespace[block_name] = Block(block_name, block.body, None, "fo", False)

        # Import only requested items
        for name, alias in zip(names, aliases):
            if name in temp_namespace:
                var_name = alias if alias else name
                item = temp_namespace[name]

                # If it's a function or block, register it appropriately
                if isinstance(item, FuncDeclaration):
                    self.functions[var_name] = item
                elif isinstance(item, Block):
                    self.blocks[var_name] = item

                self.global_vars[var_name] = item
            else:
                raise ImportError(f"Cannot import '{name}' from When package '{module_name}'")

    def instantiate_class(self, class_decl: ClassDeclaration, args: tuple, kwargs: dict) -> Any:
        """Create an instance of a class"""
        # Create a new object as a dictionary
        instance = {}

        # Add class metadata
        instance['__class__'] = class_decl.name

        # Initialize attributes
        for attr in class_decl.attributes:
            instance[attr.name] = self.eval_expression(attr.value)

        # Create a wrapper that allows attribute access
        class InstanceWrapper:
            def __init__(self, data):
                self._data = data

            def __getattr__(self, name):
                if name in self._data:
                    return self._data[name]
                raise AttributeError(f"'{class_decl.name}' object has no attribute '{name}'")

            def __setattr__(self, name, value):
                if name == '_data':
                    object.__setattr__(self, name, value)
                else:
                    self._data[name] = value

            def __repr__(self):
                return f"<{class_decl.name} instance>"

        wrapped_instance = InstanceWrapper(instance)

        # Bind methods to the wrapped instance
        for method in class_decl.methods:
            # Create a bound method
            def make_bound_method(method_decl):
                def bound_method(*args, **kwargs):
                    # Don't add self to args - call_method will handle it
                    return self.call_method(wrapped_instance, method_decl, list(args), kwargs)
                return bound_method

            instance[method.name] = make_bound_method(method)

        # Call __init__ if it exists
        if '__init__' in [m.name for m in class_decl.methods]:
            init_method = next(m for m in class_decl.methods if m.name == '__init__')
            # Don't pass wrapped_instance twice - call_method will add it as self
            self.call_method(wrapped_instance, init_method, list(args), kwargs)

        return wrapped_instance

    def call_method(self, instance, method: FuncDeclaration, args: List, kwargs: dict) -> Any:
        """Call a method on an instance"""
        # Save parameter values
        saved_params = {}

        # The first parameter is 'self'
        params = method.params
        if len(params) > 0:
            self_param = params[0]
            self_param_name = self_param.name if hasattr(self_param, 'name') else self_param

            # Save and bind parameters
            for i, param in enumerate(params):
                param_name = param.name if hasattr(param, 'name') else param
                if param_name in self.global_vars:
                    saved_params[param_name] = self.global_vars[param_name]

                if i == 0:
                    # Bind 'self'
                    self.global_vars[param_name] = instance
                elif i - 1 < len(args):
                    # Bind provided arguments (offset by 1 since self is first)
                    self.global_vars[param_name] = args[i - 1]
                elif hasattr(param, 'default') and param.default is not None:
                    # Use default value
                    self.global_vars[param_name] = self.eval_expression(param.default)

        try:
            self.execute_statements(method.body)
            result = None
        except ReturnException as ret:
            result = ret.value
        finally:
            # Restore parameters
            for param in params:
                param_name = param.name if hasattr(param, 'name') else param
                if param_name in saved_params:
                    self.global_vars[param_name] = saved_params[param_name]
                elif param_name in self.global_vars:
                    del self.global_vars[param_name]

        return result

    def run_parallel_block(self, block: Block):
        """Run a block in its own thread"""
        try:
            # print(f"[PARALLEL] {block.name} thread started")

            if block.block_type == "de":
                # Resolve iterations at runtime
                iterations = self.resolve_block_iterations(block)
                
                # Declarative block - run exactly N times
                while (block.current_iteration < iterations and
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