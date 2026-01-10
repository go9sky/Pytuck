"""
Pytuck - Lightweight Python Document Database

A pure Python document database with multi-engine support.
No SQL required - manage data through objects and methods.
"""

from setuptools import setup, find_packages
import os

# Read README for long description
def read_long_description():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

# Define optional dependencies
extras_require = {
    # Standard library engines (no extra install needed)
    'json': [],
    'csv': [],
    'sqlite': [],

    # Engines requiring external dependencies
    'excel': [
        'openpyxl>=3.0.0',
    ],
    'xml': [
        'lxml>=4.9.0',
    ],

    # Development dependencies
    'dev': [
        'mypy>=0.950',
        'build>=0.7.0',
        'twine>=4.0.0',
    ],
}

# All engines
extras_require['all'] = (
    extras_require['excel'] +
    extras_require['xml']
)

# Full development environment
extras_require['full'] = (
    extras_require['all'] +
    extras_require['dev']
)

setup(
    name="pytuck",
    version="0.1.0",
    author="go9sky",
    author_email="",
    description="Lightweight Python document database - No SQL, multi-engine, pluggable persistence",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/go9sky/pytuck",
    packages=find_packages(exclude=['examples', 'tests']),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Database :: Database Engines/Servers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Typing :: Typed",
    ],
    python_requires=">=3.7",

    # Core dependencies (zero external dependencies, pure Python)
    install_requires=[],

    # Optional dependencies
    extras_require=extras_require,

    # Project metadata
    keywords="database orm nosql document-database python lightweight pytuck embedded-database key-value-store",
    project_urls={
        "Homepage": "https://github.com/go9sky/pytuck",
        "Bug Reports": "https://github.com/go9sky/pytuck/issues",
        "Source": "https://github.com/go9sky/pytuck",
        "Documentation": "https://github.com/go9sky/pytuck#readme",
        "Changelog": "https://github.com/go9sky/pytuck/blob/main/CHANGELOG.md",
    },
)
