#!/bin/bash
# setup.sh

echo "🚀 Setting up project..."
echo ""

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please create it by copying from the example:"
    echo "  cp .env.example .env"
    echo "Then edit .env with your configuration."
    exit 1
fi
echo "✓ .env file found"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please create it first with: python -m venv .venv"
    exit 1
fi

# Activate the virtual environment
echo "Activating virtual environment..."
. .venv/bin/activate

# Check if activation was successful
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Failed to activate virtual environment"
    exit 1
fi
echo "✓ Virtual environment activated: $VIRTUAL_ENV"

# Check if Poetry is installed
echo "Checking Poetry installation..."
if ! command -v poetry &> /dev/null; then
    echo "❌ Poetry is not installed. Please install it first."
    echo "Visit: https://python-poetry.org/docs/#installation"
    exit 1
fi
echo "✓ Poetry found"

# Update lock file
echo "Updating lock file..."
if ! poetry lock --no-update; then
    echo "❌ Failed to update lock file"
    exit 1
fi
echo "✓ Lock file updated"

# Install dependencies using poetry
echo "Installing dependencies..."
if ! poetry install --all-extras; then
    echo "❌ Failed to install dependencies"
    exit 1
fi
echo "✓ Dependencies installed"

# Generate config for frontend
echo "Generating frontend config..."
echo "Because js can not read .env files, we need to generate a config file..."
echo "Hence if you change the .env file, you need to regenerate the config file running either"
echo " - this script again."
echo " - Or directly run 'python frontend/generate_config.py'."
if ! python frontend/generate_config.py; then
    echo "❌ Failed to generate frontend config"
    exit 1
fi
echo "✓ Frontend config generated"

echo ""
echo "🎉 Setup complete! You can now run the application."
echo ""
echo "📝 Next steps:"
echo "  1. Start API server:"
echo "     python -m uvicorn aila.api.main:app --reload"
echo "     and go to http://localhost:8000/docs for API documentation"
echo ""
echo "  2. Open aila.html in your browser"
echo ""
echo "  3. Check scripts/ directory for usage examples of the core python package"
echo ""
