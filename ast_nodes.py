from dataclasses import dataclass
from typing import List, Optional, Any

@dataclass
class ASTNode:
    pass

@dataclass
class Program(ASTNode):
    declarations: List['Declaration']
    blocks: List['Block']
    main: 'MainBlock'

@dataclass
class Declaration(ASTNode):
    pass

@dataclass
class VarDeclaration(Declaration):
    name: str
    value: 'Expression'

@dataclass
class Parameter(ASTNode):
    name: str
    default: Optional['Expression'] = None

@dataclass
class FuncDeclaration(Declaration):
    name: str
    params: List['Parameter']
    body: List['Statement']

@dataclass
class ImportDeclaration(Declaration):
    module: str
    alias: Optional[str] = None

@dataclass
class FromImportDeclaration(Declaration):
    module: str
    names: List[str]
    aliases: List[Optional[str]]

@dataclass
class ClassDeclaration(Declaration):
    name: str
    base_class: Optional[str]
    methods: List['FuncDeclaration']
    attributes: List['VarDeclaration']

@dataclass
class Block(ASTNode):
    name: str
    body: List['Statement']

@dataclass
class OSBlock(Block):
    pass

@dataclass
class DEBlock(Block):
    iterations: int

@dataclass
class FOBlock(Block):
    pass

@dataclass
class ParallelFOBlock(FOBlock):
    pass

@dataclass
class ParallelDEBlock(DEBlock):
    pass

@dataclass
class MainBlock(Block):
    pass

@dataclass
class Statement(ASTNode):
    pass

@dataclass
class ExpressionStatement(Statement):
    expr: 'Expression'

@dataclass
class WhenStatement(Statement):
    condition: 'Expression'
    body: List[Statement]

@dataclass
class BreakStatement(Statement):
    pass

@dataclass
class ContinueStatement(Statement):
    pass

@dataclass
class ExitStatement(Statement):
    pass

@dataclass
class PassStatement(Statement):
    pass

@dataclass
class ReturnStatement(Statement):
    values: List['Expression']

@dataclass
class GlobalStatement(Statement):
    names: List[str]

@dataclass
class Assignment(Statement):
    name: str
    value: 'Expression'

@dataclass
class IndexAssignment(Statement):
    object: 'Expression'
    index: 'Expression'
    value: 'Expression'

@dataclass
class AttributeAssignment(Statement):
    object: 'Expression'
    attribute: str
    value: 'Expression'

@dataclass
class Expression(ASTNode):
    pass

@dataclass
class BinaryOp(Expression):
    left: Expression
    operator: str
    right: Expression

@dataclass
class UnaryOp(Expression):
    operator: str
    operand: Expression

@dataclass
class TernaryOp(Expression):
    true_expr: Expression
    condition: Expression
    false_expr: Expression

@dataclass
class CallExpression(Expression):
    name: str
    args: List[Expression]
    kwargs: List['KeywordArg'] = None

@dataclass
class KeywordArg(ASTNode):
    name: str
    value: Expression

@dataclass
class StartExpression(Expression):
    block_name: str

@dataclass
class StopExpression(Expression):
    block_name: str

@dataclass
class SaveExpression(Expression):
    block_name: str

@dataclass
class SaveStopExpression(Expression):
    block_name: str

@dataclass
class StartSaveExpression(Expression):
    block_name: str

@dataclass
class DiscardExpression(Expression):
    block_name: str

@dataclass
class Identifier(Expression):
    name: str

@dataclass
class NumberLiteral(Expression):
    value: float

@dataclass
class StringLiteral(Expression):
    value: str

@dataclass
class FStringLiteral(Expression):
    parts: List[tuple]  # List of ('str', value) or ('expr', expression_string)

@dataclass
class BooleanLiteral(Expression):
    value: bool

@dataclass
class NoneLiteral(Expression):
    pass

@dataclass
class ListLiteral(Expression):
    elements: List[Expression]

@dataclass
class TupleLiteral(Expression):
    elements: List[Expression]

@dataclass
class DictLiteral(Expression):
    keys: List[Expression]
    values: List[Expression]

@dataclass
class IndexExpression(Expression):
    object: Expression
    index: Expression

@dataclass
class MemberAccess(Expression):
    object: Expression
    member: str

@dataclass
class MethodCall(Expression):
    object: Expression
    method: str
    args: List[Expression]
    kwargs: List['KeywordArg'] = None