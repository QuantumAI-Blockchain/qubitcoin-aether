"""
QVM - Qubitcoin Virtual Machine
EVM-compatible bytecode interpreter with quantum opcodes
"""
from .vm import QVM
from .opcodes import Opcode

__all__ = ['QVM', 'Opcode']
