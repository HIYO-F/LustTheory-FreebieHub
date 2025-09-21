import time
import sys
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
    def __init__(self, name: str, body: List[Statement], iterations: Optional[int] = None, block_type: str = "fo"):
        self.name = name
        self.body = body
        self.iterations = iterations
        self.current_iteration = 0
        self.status = BlockStatus.STOPPED
        self.block_type = block_type  # "os", "de", "fo"

    def reset(self):
        self.current_iteration = 0
        self.status = BlockStatus.STOPPED

class Interpreter:
    def __init__(self):
        self.global_vars: Dict[str, Any] = {}
        self.functions: Dict[str, FuncDeclaration] = {}
        self.blocks: Dict[str, Block] = {}
        self.running_blocks: List[str] = []
        self.exit_requested = False
        self.modules: Dict[str, Any] = {}

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

        # Register blocks
        for block in program.blocks:
            if isinstance(block, OSBlock):
                self.blocks[block.name] = Block(block.name, block.body, None, "os")
            elif isinstance(block, DEBlock):
                self.blocks[block.name] = Block(block.name, block.body, block.iterations, "de")
            else:  # FOBlock or ParallelFOBlock
                self.blocks[block.name] = Block(block.name, block.body, None, "fo")

        # Execute main block
        try:
            self.execute_main(program.main)
        except ExitException:
            print("Program exited")

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

        try:
            # For DE blocks, check iteration limit BEFORE executing
            if block.iterations is not None:
                if block.current_iteration >= block.iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)
                    return

            # Execute one iteration
            self.execute_statements(block.body)

            # Increment iteration counter AFTER successful execution
            if block.iterations is not None:
                block.current_iteration += 1
                # Check if we've completed all iterations
                if block.current_iteration >= block.iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)

        except ContinueException:
            if block.iterations is not None:
                block.current_iteration += 1
                if block.current_iteration >= block.iterations:
                    block.status = BlockStatus.COMPLETED
                    if block.name in self.running_blocks:
                        self.running_blocks.remove(block.name)
        except BreakException:
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
            self.global_vars[stmt.name] = self.eval_expression(stmt.value)
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

        # FO and DE blocks are added to running blocks
        block.reset()
        block.status = BlockStatus.RUNNING
        if block_name not in self.running_blocks:
            self.running_blocks.append(block_name)

    def stop_block(self, block_name: str):
        if block_name in self.running_blocks:
            self.blocks[block_name].status = BlockStatus.STOPPED
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