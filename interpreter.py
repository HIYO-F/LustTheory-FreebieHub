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

    def reset(self):
        self.current_iteration = 0
        self.status = BlockStatus.STOPPED
        self.should_stop.clear()
        if self.thread and self.thread.is_alive():
            self.should_stop.set()
            self.thread.join(timeout=1.0)

class Interpreter:
    def __init__(self):
        self.global_vars: Dict[str, Any] = {}
        self.functions: Dict[str, FuncDeclaration] = {}
        self.blocks: Dict[str, Block] = {}
        self.running_blocks: List[str] = []
        self.exit_requested = False
        self.modules: Dict[str, Any] = {}
        self.global_vars_lock = threading.Lock()
        self.parallel_threads: List[threading.Thread] = []

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

        # Execute main block
        try:
            self.execute_main(program.main)
        except ExitException:
            print("Program exited")
        finally:
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
            value = None
            if stmt.value:
                value = self.eval_expression(stmt.value)
            raise ReturnException(value)

    def eval_expression(self, expr: Expression) -> Any:
        if isinstance(expr, NumberLiteral):
            return expr.value
        elif isinstance(expr, StringLiteral):
            return expr.value
        elif isinstance(expr, Identifier):
            with self.global_vars_lock:
                if expr.name in self.global_vars:
                    return self.global_vars[expr.name]
            raise NameError(f"Variable '{expr.name}' not defined")
        elif isinstance(expr, BinaryOp):
            left = self.eval_expression(expr.left)
            right = self.eval_expression(expr.right)
            return self.apply_binary_op(left, expr.operator, right)
        elif isinstance(expr, CallExpression):
            return self.call_function(expr.name, expr.args)
        elif isinstance(expr, StartExpression):
            self.start_block(expr.block_name)
            return None
        elif isinstance(expr, StopExpression):
            self.stop_block(expr.block_name)
            return None
        elif isinstance(expr, MemberAccess):
            obj = self.eval_expression(expr.object)
            return getattr(obj, expr.member)
        elif isinstance(expr, MethodCall):
            obj = self.eval_expression(expr.object)
            method = getattr(obj, expr.method)
            args = [self.eval_expression(arg) for arg in expr.args]
            return method(*args)
        else:
            raise NotImplementedError(f"Expression type {type(expr)} not implemented")

    def apply_binary_op(self, left: Any, op: str, right: Any) -> Any:
        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            return left / right
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
        else:
            raise NotImplementedError(f"Operator {op} not implemented")

    def call_function(self, name: str, args: List[Expression]) -> Any:
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
        elif name == 'exit':
            self.exit_requested = True
            raise ExitException()
        # Check if it's a block to execute (OS blocks can be called as functions)
        elif name in self.blocks:
            block = self.blocks[name]
            self.execute_statements(block.body)
            return None
        # User-defined functions
        elif name in self.functions:
            func = self.functions[name]
            if len(args) != len(func.params):
                raise ValueError(f"Function {name} expects {len(func.params)} arguments, got {len(args)}")

            # Save current vars and create local scope
            saved_vars = self.global_vars.copy()

            # Bind parameters
            for param, arg in zip(func.params, args):
                self.global_vars[param] = self.eval_expression(arg)

            # Execute function body
            try:
                self.execute_statements(func.body)
                result = None
            except ReturnException as ret:
                result = ret.value
            finally:
                # Restore global vars
                self.global_vars = saved_vars

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