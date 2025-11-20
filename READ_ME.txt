README – Startup Commands

Start MySQL (if not already running):
sudo systemctl start mysql

Start FastAPI (MES backend):
cd ~/mes_app
source venv/bin/activate
uvicorn mes_app.main:app --reload --host 0.0.0.0 --port 8000

Start Flask + Dash (RubirMES UI):
cd ~/mes_app/ui
source ../venv/bin/activate
python app.py

Start both services using the startup script:
cd ~/mes_app
./start_mes.sh

Run the MES sync script manually:
cd ~/mes_app
source venv/bin/activate
python sync/sync_events.py

Start Ignition Designer:
ignition-designer

Start Ignition Gateway (if needed):
sudo systemctl start ignition

Kill processes using port 5000 or 8000 if stuck:
sudo lsof -i :5000
sudo kill -9 <PID>

sudo lsof -i :8000
sudo kill -9 <PID>