#!/bin/bash
# init.sh

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

# Ensure Poetry installs into the active venv (no Poetry-managed venv)
echo "Configuring Poetry to use current virtualenv..."
if ! poetry config virtualenvs.create false --local; then
    echo "❌ Failed to configure Poetry to avoid creating its own virtualenv"
    exit 1
fi
echo "✓ Poetry will install into the current environment"

# Install dependencies using Poetry
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
echo "📝 Next:"
echo "  Start API server which loads website:"
echo "  uvicorn frontend.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
