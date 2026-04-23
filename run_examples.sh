python3 -m pip install -r requirements.txt

python3 src/turn_engine.py --demo
python3 src/turn_engine.py examples/demo_encounter.json
python3 src/turn_engine.py examples/demo_encounter.json --json
python3 src/turn_engine.py examples/demo_encounter.json --write-log combat_log.json
