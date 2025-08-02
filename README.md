# Todo App with React and Python Backend

This is a full-stack Todo application with a React frontend and Python backend.

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
   # Navigate back to server directory and start the server
   cd ${SERVER_DIR} && \
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
