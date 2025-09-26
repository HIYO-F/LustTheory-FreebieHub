#!/usr/bin/env python3
"""
Setup script for WHEN Language Interpreter
"""

from setuptools import setup, find_packages
import os

# Read the README file for long description
def read_readme():
    try:
        with open("README.md", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "WHEN Language Interpreter - A unique loop-based programming language"

setup(
    name="when-lang",
    version="0.4.0",
    description="WHEN Language Interpreter - A unique loop-based programming language",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="WHEN Language Team",
    url="https://github.com/when-lang/when",
    packages=find_packages(),
    py_modules=[
        "when",
        "lexer",
        "parser",
        "interpreter",
        "ast_nodes",
        "whenloop"
    ],
    entry_points={
        "console_scripts": [
            "when=when:main",
        ],
    },
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Interpreters",
        "Topic :: Software Development :: Compilers",
    ],
    keywords="programming-language interpreter when-loop reactive",
    install_requires=[
        # No external dependencies for now
    ],
    extras_require={
        "dev": [
            "pytest",
            "black",
            "flake8",
        ],
    },
)