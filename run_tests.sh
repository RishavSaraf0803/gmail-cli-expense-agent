#!/bin/bash
# FinCLI Test Runner Script

set -e

echo "🧪 FinCLI Test Suite"
echo "===================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}⚠️  Virtual environment not activated${NC}"
    echo "Run: source venv/bin/activate"
    exit 1
fi

# Parse arguments
MODE=${1:-all}

case $MODE in
    unit)
        echo -e "${BLUE}Running unit tests...${NC}"
        pytest tests/unit/ -v
        ;;
    integration)
        echo -e "${BLUE}Running integration tests...${NC}"
        pytest tests/integration/ -v
        ;;
    coverage)
        echo -e "${BLUE}Running tests with coverage...${NC}"
        pytest --cov=fincli --cov-report=term-missing --cov-report=html
        echo ""
        echo -e "${GREEN}✅ Coverage report generated: htmlcov/index.html${NC}"
        ;;
    fast)
        echo -e "${BLUE}Running fast tests (no coverage)...${NC}"
        pytest tests/unit/ -v --tb=short
        ;;
    watch)
        echo -e "${BLUE}Running tests in watch mode...${NC}"
        pytest-watch tests/
        ;;
    clean)
        echo -e "${BLUE}Cleaning test artifacts...${NC}"
        rm -rf .pytest_cache htmlcov .coverage
        find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
        echo -e "${GREEN}✅ Cleaned${NC}"
        ;;
    all)
        echo -e "${BLUE}Running all tests with coverage...${NC}"
        pytest -v --cov=fincli --cov-report=term-missing --cov-report=html
        echo ""
        echo -e "${GREEN}✅ All tests completed${NC}"
        echo -e "${GREEN}📊 Coverage report: htmlcov/index.html${NC}"
        ;;
    *)
        echo "Usage: ./run_tests.sh [mode]"
        echo ""
        echo "Modes:"
        echo "  all          - Run all tests with coverage (default)"
        echo "  unit         - Run only unit tests"
        echo "  integration  - Run only integration tests"
        echo "  coverage     - Run tests with detailed coverage report"
        echo "  fast         - Run unit tests quickly (no coverage)"
        echo "  watch        - Run tests in watch mode"
        echo "  clean        - Clean test artifacts"
        exit 1
        ;;
esac

exit 0
