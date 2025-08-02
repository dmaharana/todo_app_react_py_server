# Todo App with React and Python Backend

This is a full-stack Todo application with a React frontend and Python backend.

## Development

For development, you can use the development server:

## Steps to be followed if server repository is cloned

1. **Clone the UI repository**
   ```bash
   SERVER_DIR=`pwd`
   WEB_DIR="web"
   WEB_PORT=5000
   USER_INTERFACE_REPO="git@github.com:dmaharana/todo_app_react_py_ui.git"
   
   # Clone UI
   git clone ${USER_INTERFACE_REPO} ../${WEB_DIR}
   ```

2. **Build the User Interface**
   ```bash
   # Navigate to web directory and build
   cd ../${WEB_DIR}
   pnpm install && \
   pnpm build && \
   cp -r dist ../${SERVER_DIR}
   ```

3. **Run the Server**
   ```bash
   # Navigate back to server directory and start the development server
   cd ${SERVER_DIR} && \
   pip install -r requirements.txt && \
   python api.py --port ${WEB_PORT} --build-dir dist

## Production Deployment

For production deployment, it's recommended to use Gunicorn as the WSGI server.

### Prerequisites

- Python 3.7+
- Node.js and pnpm (for building the frontend)
- Gunicorn (will be installed via requirements.txt)

### Setup

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Build the frontend** (if not already built)
   ```bash
   # In the server directory
   WEB_DIR="web"
   USER_INTERFACE_REPO="git@github.com:dmaharana/todo_app_react_py_ui.git"
   
   # Clone UI if needed
   if [ ! -d "../${WEB_DIR}" ]; then
       git clone ${USER_INTERFACE_REPO} ../${WEB_DIR}
   fi
   
   # Build the frontend
   cd ../${WEB_DIR}
   pnpm install && pnpm build && cp -r dist ../server/
   cd - > /dev/null
   ```

### Running in Production

1. **Using the production script**:
   ```bash
   chmod +x run_prod.sh
   ./run_prod.sh
   ```

   This will start the Gunicorn server with the following configuration:
   - Binds to `0.0.0.0:8000`
   - Uses multiple worker processes (based on CPU cores)
   - Includes proper timeouts and request limits
   - Logs to stdout/stderr

2. **Environment Variables**:
   - `FLASK_ENV=production` - Set by default in `run_prod.sh`
   - `DATABASE_URL` - If you need to use a different database

### Advanced Configuration

You can modify `gunicorn_config.py` to adjust:
- Number of workers
- Timeouts
- Logging levels
- Request limits
- And more

### Running with a Process Manager (Optional)

For production deployments, consider using a process manager like systemd or Supervisor to keep the application running. Here's an example systemd service file:

```ini
[Unit]
Description=Todo App Gunicorn Service
After=network.target

[Service]
User=your_username
Group=www-data
WorkingDirectory=/path/to/your/app
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -c gunicorn_config.py api:app
Restart=always

[Install]
WantedBy=multi-user.target
```
   pip install -r requirements.txt && \
   python api.py --port 5000 --build-dir dist
   ```

## Steps to be followed if user interface repository is cloned

1. **Clone the server and build the UI**
   ```bash
   WEB_DIR=`pwd`
   SERVER_DIR="server"
   WEB_PORT=5000
   SERVER_REPO="git@github.com:dmaharana/todo_app_react_py_server.git"
   
   # Clone server and build UI
   git clone ${SERVER_REPO} ../${SERVER_DIR} && \
   pnpm install && \
   pnpm build && \
   cp -r dist ../${SERVER_DIR}
   ```

2. **Run the server**
   ```bash
   # Navigate to server directory and start the server
   cd ${SERVER_DIR} && \
   pip install -r requirements.txt && \
   python api.py --port 5000 --build-dir dist
   ```

## Configuration

- **Port**: Default port is set to 5000
- **Build Directory**: The built frontend files are expected in the `dist` directory by default

## Dependencies

- Python 3.x
- Node.js and pnpm
- Python packages listed in `requirements.txt`
- Node.js dependencies in `package.json`
