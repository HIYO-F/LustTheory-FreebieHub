#!/usr/bin/env python3
"""
Hot Reload Module for WHEN Language
Watches source files and reloads blocks dynamically
"""

import os
import time
import threading
from pathlib import Path
from typing import Dict, Optional, Set, Any
from dataclasses import dataclass
import hashlib

@dataclass
class FileState:
    """Tracks state of a source file"""
    path: str
    last_modified: float
    content_hash: str

    @staticmethod
    def from_file(path: str) -> 'FileState':
        stat = os.stat(path)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return FileState(
            path=path,
            last_modified=stat.st_mtime,
            content_hash=hashlib.md5(content.encode()).hexdigest()
        )

class HotReloader:
    """Manages hot reloading of WHEN blocks"""

    def __init__(self, interpreter, source_file: str):
        self.interpreter = interpreter
        self.source_file = source_file
        self.file_state: Optional[FileState] = None
        self.watching = False
        self.watch_thread: Optional[threading.Thread] = None
        self.watch_interval = 0.5  # Check every 500ms
        self.reload_lock = threading.Lock()
        self.preserved_state: Dict[str, Dict[str, Any]] = {}

    def start_watching(self):
        """Start watching the source file for changes"""
        if self.watching:
            return

        self.watching = True
        self.file_state = FileState.from_file(self.source_file)
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()
        print(f"[HOT RELOAD] Watching {self.source_file} for changes...")

    def stop_watching(self):
        """Stop watching the source file"""
        self.watching = False
        if self.watch_thread:
            self.watch_thread.join(timeout=1.0)

    def _watch_loop(self):
        """Main watch loop that checks for file changes"""
        while self.watching:
            try:
                current_state = FileState.from_file(self.source_file)

                # Check if file has changed
                if (current_state.last_modified != self.file_state.last_modified or
                    current_state.content_hash != self.file_state.content_hash):

                    print(f"[HOT RELOAD] Detected changes in {self.source_file}")
                    self._reload_blocks()
                    self.file_state = current_state

            except Exception as e:
                print(f"[HOT RELOAD] Error checking file: {e}")

            time.sleep(self.watch_interval)

    def _reload_blocks(self):
        """Reload blocks from the source file"""
        with self.reload_lock:
            try:
                # Save state of running blocks
                self._preserve_block_state()

                # Parse the updated source
                from lexer import Lexer
                from parser import Parser

                with open(self.source_file, 'r', encoding='utf-8') as f:
                    source = f.read()

                lexer = Lexer(source)
                tokens = lexer.tokenize()
                parser = Parser(tokens)
                program = parser.parse()

                # Update functions and non-block declarations
                self._update_declarations(program)

                # Reload blocks (but not main)
                self._update_blocks(program)

                # Restore state for blocks that were running
                self._restore_block_state()

                print("[HOT RELOAD] Successfully reloaded blocks!")

            except Exception as e:
                print(f"[HOT RELOAD] Error reloading: {e}")

    def _preserve_block_state(self):
        """Save the state of currently running blocks"""
        self.preserved_state.clear()

        for block_name, block in self.interpreter.blocks.items():
            if block.status.name == "RUNNING":
                self.preserved_state[block_name] = {
                    'current_iteration': block.current_iteration,
                    'status': block.status,
                    'was_running': True
                }

    def _restore_block_state(self):
        """Restore state to blocks that were running before reload"""
        for block_name, state in self.preserved_state.items():
            if block_name in self.interpreter.blocks:
                block = self.interpreter.blocks[block_name]

                # Restore iteration count
                block.current_iteration = state['current_iteration']

                # Restart block if it was running
                if state['was_running']:
                    block.status = state['status']
                    if block_name not in self.interpreter.running_blocks:
                        self.interpreter.running_blocks.append(block_name)

                print(f"[HOT RELOAD] Restored state for block '{block_name}'")

    def _update_declarations(self, program):
        """Update function declarations and imports"""
        from ast_nodes import (
            FuncDeclaration, ImportDeclaration,
            FromImportDeclaration, VarDeclaration
        )

        for decl in program.declarations:
            if isinstance(decl, FuncDeclaration):
                # Update function definition
                old_func = self.interpreter.functions.get(decl.name)
                self.interpreter.functions[decl.name] = decl
                if old_func:
                    print(f"[HOT RELOAD] Updated function '{decl.name}'")
                else:
                    print(f"[HOT RELOAD] Added new function '{decl.name}'")

            elif isinstance(decl, ImportDeclaration):
                # Re-handle imports (in case new imports were added)
                self.interpreter.handle_import(decl)

            elif isinstance(decl, FromImportDeclaration):
                self.interpreter.handle_from_import(decl)

            # Note: We don't reload variable declarations to preserve runtime state

    def _update_blocks(self, program):
        """Update block definitions while preserving state"""
        from ast_nodes import (
            OSBlock, DEBlock, FOBlock,
            ParallelDEBlock, ParallelFOBlock
        )
        from interpreter import Block

        # Track which blocks exist in the new source
        new_block_names = set()

        for block in program.blocks:
            new_block_names.add(block.name)

            # Determine block type and create new block instance
            if isinstance(block, OSBlock):
                new_block = Block(block.name, block.body, None, "os", False)
            elif isinstance(block, ParallelDEBlock):
                new_block = Block(block.name, block.body, block.iterations, "de", True)
            elif isinstance(block, ParallelFOBlock):
                new_block = Block(block.name, block.body, None, "fo", True)
            elif isinstance(block, DEBlock):
                new_block = Block(block.name, block.body, block.iterations, "de", False)
            else:  # Regular FOBlock
                new_block = Block(block.name, block.body, None, "fo", False)

            # Check if block already exists
            if block.name in self.interpreter.blocks:
                old_block = self.interpreter.blocks[block.name]

                # Preserve runtime state if block was running
                if old_block.status.name == "RUNNING":
                    new_block.current_iteration = old_block.current_iteration
                    new_block.status = old_block.status

                print(f"[HOT RELOAD] Updated block '{block.name}'")
            else:
                print(f"[HOT RELOAD] Added new block '{block.name}'")

            # Replace block definition
            self.interpreter.blocks[block.name] = new_block

        # Remove blocks that no longer exist in source
        blocks_to_remove = []
        for block_name in self.interpreter.blocks.keys():
            if block_name not in new_block_names:
                blocks_to_remove.append(block_name)

        for block_name in blocks_to_remove:
            # Stop block if it's running
            if block_name in self.interpreter.running_blocks:
                self.interpreter.running_blocks.remove(block_name)
            del self.interpreter.blocks[block_name]
            print(f"[HOT RELOAD] Removed block '{block_name}'")