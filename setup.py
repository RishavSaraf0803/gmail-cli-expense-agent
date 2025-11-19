"""
Setup script for FinCLI
"""
from setuptools import setup, find_packages
from pathlib import Path

# Read README
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read requirements
requirements = (this_directory / "requirements.txt").read_text().splitlines()
dev_requirements = (this_directory / "requirements-dev.txt").read_text().splitlines()

setup(
    name="fincli",
    version="1.0.0",
    author="FinCLI Contributors",
    description="A conversational Gmail expense tracker using Amazon Bedrock",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/fincli",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Office/Business :: Financial",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "fincli=cli:app",
        ],
    },
)
