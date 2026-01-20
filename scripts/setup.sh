#!/bin/bash
# FinCLI Setup Script

set -e

echo "🚀 Setting up FinCLI..."
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing production dependencies..."
pip install -r requirements.txt

echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Install package in editable mode
echo "Installing FinCLI in editable mode..."
pip install -e .

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest"
echo "  or"
echo "  ./run_tests.sh"
