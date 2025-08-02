#!/bin/bash

# Production run script for the Todo React-Py application

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Build the React frontend if not already built
if [ ! -d "dist" ]; then
    echo "Building React frontend..."
    WEB_DIR="web"
    USER_INTERFACE_REPO="git@github.com:dmaharana/todo_app_react_py_ui.git"
    
    # Clone UI if not already present
    if [ ! -d "../${WEB_DIR}" ]; then
        git clone ${USER_INTERFACE_REPO} ../${WEB_DIR}
    fi
    
    # Build the frontend
    cd ../${WEB_DIR}
    pnpm install && \
    pnpm build && \
    cp -r dist ../server/
    cd - > /dev/null
fi

# Set environment to production
export FLASK_ENV=production

# Run the application with Gunicorn
echo "Starting Gunicorn server..."
gunicorn -c gunicorn_config.py api:app

# For debugging (uncomment if needed)
# gunicorn --log-level=debug --log-file=- --error-logfile=- --access-logfile=- -c gunicorn_config.py api:app
