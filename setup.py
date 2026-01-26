"""
Setup configuration for Qubitcoin
Enables pip installation and binary compilation
"""

from setuptools import setup, find_packages
import os

# Read README
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read requirements
with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="qubitcoin",
    version="1.0.0",
    author="SUSY Labs",
    author_email="contact@susylabs.io",
    description="Quantum-secured cryptocurrency using supersymmetric principles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/susylabs/qubitcoin",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: System :: Distributed Computing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "qubitcoin-node=qubitcoin:main",
            "qbc-node=qubitcoin:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
