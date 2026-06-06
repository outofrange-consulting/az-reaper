#!/usr/bin/env python
"""Setup for the ``reaper`` Azure CLI extension.

Build a wheel with ``python setup.py bdist_wheel`` and install it with
``az extension add --source dist/reaper-<version>-py3-none-any.whl``.
"""

from setuptools import setup, find_packages

VERSION = "0.1.0"

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Intended Audience :: System Administrators",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "License :: OSI Approved :: Apache Software License",
]

try:
    with open("azext_reaper/README.md", "r", encoding="utf-8") as fh:
        LONG_DESCRIPTION = fh.read()
except OSError:
    LONG_DESCRIPTION = ""

setup(
    name="reaper",
    version=VERSION,
    description="Harvest stale git worktrees, with Azure DevOps PR awareness.",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    license="Apache-2.0",
    author="OutOfRange Consulting",
    url="https://github.com/outofrange-consulting/az-reaper",
    classifiers=CLASSIFIERS,
    packages=find_packages(exclude=["azext_reaper.tests*"]),
    package_data={"azext_reaper": ["azext_metadata.json"]},
    install_requires=[],
)
