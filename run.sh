# In server
SERVER_DIR=${PWD##*/} 
WEB_DIR="web"
WEB_PORT=5000
USER_INTERFACE_REPO="git@github.com:dmaharana/todo_app_react_py_ui.git"

if [ ! -d "dist" ]; then
    # 1. Clone UI
    git clone ${USER_INTERFACE_REPO} ../${WEB_DIR}

    # 2. Build Userinterface
    cd ../${WEB_DIR}
    pnpm install && \
    pnpm build && \
    cp -r dist ../${SERVER_DIR}
fi

# 3. Run server in SERVER_DIR
cd ../${SERVER_DIR} && \
pip install -r requirements.txt && \
python api.py --port 5000 --build-dir dist
