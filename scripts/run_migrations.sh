#!/bin/bash
# run_migrations.sh - Attempts to stabilize Django CLI by explicitly sourcing virtualenv context

echo "Attempting to set up Django virtual environment..."
# Attempt 1: Using uv/pip standard best practices
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "--- Running makemigrations cora ---"
# Use the activated python interpreter for reliability
# We use 'python' instead of 'django' as it should be in path after source.
python manage.py makemigrations cora 
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "makemigrations successful. Now running migrate..."
    # This command only runs if the previous command succeeded (implicit &&)
    python manage.py migrate 
else
    echo "Error during makemigrations with exit code $EXIT_CODE."
fi

deactivate