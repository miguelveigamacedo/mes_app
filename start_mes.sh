#!/bin/bash

# Absolute path to your project
PROJECT_DIR="$HOME/mes_app"
VENV_DIR="$PROJECT_DIR/venv"

echo "Starting RubirMES..."
echo ""

# --------------------------------------------------
# Start FASTAPI backend (port 8000)
# --------------------------------------------------

echo "Starting FastAPI (MES backend) on port 8000..."

# Run in its own terminal window
gnome-terminal -- bash -c "
    cd $PROJECT_DIR;
    source $VENV_DIR/bin/activate;
    uvicorn mes_app.main:app --host 0.0.0.0 --port 8000 --reload;
    exec bash
"
sleep 1

# --------------------------------------------------
# Start Flask + Dash UI (port 5000)
# --------------------------------------------------

echo "Starting Flask + Dash UI on port 5000..."

gnome-terminal -- bash -c "
    cd $PROJECT_DIR/ui;
    source $VENV_DIR/bin/activate;
    python app.py;
    exec bash
"

echo ""
echo "RubirMES is now running!"
echo "Backend: http://<VM-IP>:8000"
echo "Frontend: http://<VM-IP>:5000/"
echo ""
