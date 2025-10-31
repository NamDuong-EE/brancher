#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template, abort
import configparser
import subprocess, os


CONFIG_PATH = "/home/nam/Desktop/config.ini" 


API_TOKEN = "admin"

app = Flask(__name__, template_folder="templates", static_folder="static")

def load_config():
    """Reads the flat .ini file and converts it to a structured dictionary."""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    if 'DEFAULT' not in config:
        return {}
        
    flat_config = config['DEFAULT']
    
    structured_config = {
        "sensors": []
    }
    
    try:
        num_sensors = int(flat_config.get('number_of_sensor', 0))
        structured_config['number_of_sensor'] = num_sensors
    except (ValueError, TypeError):
        num_sensors = 0

    for i in range(1, num_sensors + 1):
        sensor_data = {'id': i}
        suffix = f"_{i}"
        
        for key, value in flat_config.items():
            if key.endswith(suffix):
                clean_key = key[:-len(suffix)]
                sensor_data[clean_key] = value
                
        structured_config['sensors'].append(sensor_data)

    for key, value in flat_config.items():
        is_sensor_key = any(key.endswith(f"_{i}") for i in range(1, num_sensors + 1))
        if not is_sensor_key and key not in structured_config:
            structured_config[key] = value

    return structured_config

def save_config(cfg):
    """Takes a structured dictionary, flattens it, and saves to the .ini file."""
    config = configparser.ConfigParser()
    config['DEFAULT'] = {}
    
    sensors_list = cfg.get('sensors', [])
    
    config['DEFAULT']['number_of_sensor'] = str(cfg.get('number_of_sensor', len(sensors_list)))

    for sensor_data in sensors_list:
        sensor_id = sensor_data.get('id')
        if sensor_id is None:
            continue 
            
        suffix = f"_{sensor_id}"
        for key, value in sensor_data.items():
            if key != 'id': 
                ini_key = f"{key}{suffix}"
                config['DEFAULT'][ini_key] = str(value)

    for key, value in cfg.items():
        if key != 'sensors':
            config['DEFAULT'][key] = str(value)
            
    with open(CONFIG_PATH, "w") as config_file:
        config.write(config_file)

    # subprocess.run(["sudo", "systemctl", "restart", "datalogger.service"])

def check_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1]
    return token == API_TOKEN

@app.route("/")
def index():
    # serve web UI (frontend)
    return render_template("index.html")

@app.route("/config", methods=["GET"])
def get_config():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    return jsonify(load_config())

@app.route("/config", methods=["POST"])
def post_config():
    if not check_auth():
        return jsonify({"error": "unauthorized"}), 401
    if not request.is_json:
        return jsonify({"error": "Content-Type must be application/json"}), 415
    new_cfg = request.get_json()
    save_config(new_cfg)
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
