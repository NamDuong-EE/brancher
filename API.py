#!/usr/bin/env python3

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import configparser
import subprocess
import os
import threading
import pty
import select
import termios
import struct
import fcntl
import json

CONFIG_PATH = "/home/nam/Desktop/config.ini"
API_TOKEN = "admin"

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config['SECRET_KEY'] = 'your-secret-key-brancher-2025'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Global MQTT client
mqtt_client = None
mqtt_connected = False
current_config = {}

# SSH Terminal sessions
ssh_sessions = {}

# ============= Config Management (Your Original Code) =============
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
        if key not in ['sensors', 'number_of_sensor']:
            config['DEFAULT'][key] = str(value)
    
    with open(CONFIG_PATH, "w") as config_file:
        config.write(config_file)
    
    # Reload MQTT with new config
    global current_config
    current_config = cfg
    reconnect_mqtt()

def check_auth():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1]
    return token == API_TOKEN

# ============= MQTT Functions =============
def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"Connected to MQTT Broker: {current_config.get('mqtt_broker', 'unknown')}")
        # Subscribe to all sensor topics
        sensors = current_config.get('sensors', [])
        for sensor in sensors:
            topic = sensor.get('mqtt_topic', '')
            if topic:
                client.subscribe(topic)
                print(f"  Subscribed to: {topic}")
        socketio.emit('mqtt_status', {'status': 'connected', 'broker': current_config.get('mqtt_broker', '')})
    else:
        mqtt_connected = False
        print(f"Failed to connect to MQTT. RC: {rc}")
        socketio.emit('mqtt_status', {'status': 'disconnected', 'error': rc})

def on_mqtt_message(client, userdata, msg):
    try:
        # Try to parse as JSON
        try:
            payload = json.loads(msg.payload.decode())
        except:
            # If not JSON, send as plain text
            payload = {'raw': msg.payload.decode(), 'topic': msg.topic}
        
        # Broadcast to all connected web clients
        socketio.emit('sensor_data', {
            'topic': msg.topic,
            'data': payload,
            'timestamp': payload.get('timestamp', '')
        })
        print(f"MQTT: {msg.topic} ? {payload}")
    except Exception as e:
        print(f"Error processing MQTT message: {e}")

def connect_mqtt():
    global mqtt_client, mqtt_connected, current_config
    
    broker = current_config.get('mqtt_broker', '')
    port = int(current_config.get('mqtt_port', 1883))
    username = current_config.get('mqtt_username', '')
    password = current_config.get('mqtt_password', '')
    client_id = current_config.get('mqtt_client_id', 'brancher_web_ui')
    
    if not broker:
        print("No MQTT broker configured")
        return False
    
    try:
        mqtt_client = mqtt.Client(client_id=client_id)
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message
        
        if username and password:
            mqtt_client.username_pw_set(username, password)
        
        print(f"Connecting to MQTT: {broker}:{port}")
        mqtt_client.connect(broker, port, 60)
        mqtt_client.loop_start()
        return True
    except Exception as e:
        print(f"MQTT connection failed: {e}")
        mqtt_connected = False
        return False

def reconnect_mqtt():
    """Reconnect MQTT with updated config"""
    global mqtt_client
    if mqtt_client:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except:
            pass
    connect_mqtt()

# ============= SSH Terminal Functions =============
def set_winsize(fd, row, col, xpix=0, ypix=0):
    winsize = struct.pack("HHHH", row, col, xpix, ypix)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

def read_and_forward_pty_output(fd, sid):
    """Read from PTY and forward to web client"""
    max_read_bytes = 1024 * 20
    while True:
        try:
            socketio.sleep(0.01)
            timeout = 0.1
            if fd in select.select([fd], [], [], timeout)[0]:
                try:
                    output = os.read(fd, max_read_bytes).decode('utf-8', errors='ignore')
                    if output:
                        socketio.emit('ssh_output', {'data': output}, room=sid)
                except OSError:
                    break
        except Exception as e:
            print(f"SSH read error: {e}")
            break

# ============= Flask Routes (Your Original + New) =============
@app.route("/")
def index():
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

# ============= WebSocket Events =============
@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    emit('mqtt_status', {
        'status': 'connected' if mqtt_connected else 'disconnected',
        'broker': current_config.get('mqtt_broker', '')
    })

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f"Client disconnected: {sid}")
    # Clean up SSH session if exists
    if sid in ssh_sessions:
        try:
            os.close(ssh_sessions[sid]['fd'])
            os.kill(ssh_sessions[sid]['pid'], 9)
            del ssh_sessions[sid]
        except:
            pass

@socketio.on('request_config')
def handle_request_config(data):
    """Send current config to client (for initial load)"""
    token = data.get('token', '')
    if token != API_TOKEN:
        emit('config_error', {'error': 'unauthorized'})
        return
    config = load_config()
    emit('config_data', config)

@socketio.on('start_ssh')
def handle_start_ssh(data):
    """Initialize SSH terminal session"""
    sid = request.sid
    
    # Check if already has session
    if sid in ssh_sessions:
        emit('ssh_error', {'error': 'Session already exists'})
        return
    
    try:
        # Create pseudo-terminal
        (child_pid, fd) = pty.fork()
        
        if child_pid == 0:
            # Child process - start bash
            subprocess.run(['/bin/bash', '-i'])
        else:
            # Parent process - store session
            ssh_sessions[sid] = {'pid': child_pid, 'fd': fd}
            set_winsize(fd, 24, 80)
            
            # Start thread to read PTY output
            thread = threading.Thread(target=read_and_forward_pty_output, args=(fd, sid))
            thread.daemon = True
            thread.start()
            
            emit('ssh_ready', {'status': 'ready'})
            print(f"SSH session started for {sid}")
    except Exception as e:
        print(f"SSH start error: {e}")
        emit('ssh_error', {'error': str(e)})

@socketio.on('ssh_input')
def handle_ssh_input(data):
    """Receive input from web client and write to PTY"""
    sid = request.sid
    if sid not in ssh_sessions:
        emit('ssh_error', {'error': 'No active session'})
        return
    
    try:
        fd = ssh_sessions[sid]['fd']
        input_data = data.get('data', '')
        os.write(fd, input_data.encode())
    except Exception as e:
        print(f"SSH input error: {e}")
        emit('ssh_error', {'error': str(e)})

@socketio.on('ssh_resize')
def handle_ssh_resize(data):
    """Handle terminal resize"""
    sid = request.sid
    if sid not in ssh_sessions:
        return
    
    try:
        fd = ssh_sessions[sid]['fd']
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        set_winsize(fd, rows, cols)
    except Exception as e:
        print(f"SSH resize error: {e}")

@socketio.on('close_ssh')
def handle_close_ssh():
    """Close SSH session"""
    sid = request.sid
    if sid in ssh_sessions:
        try:
            os.close(ssh_sessions[sid]['fd'])
            os.kill(ssh_sessions[sid]['pid'], 9)
            del ssh_sessions[sid]
            emit('ssh_closed', {'status': 'closed'})
            print(f"SSH session closed for {sid}")
        except Exception as e:
            print(f"SSH close error: {e}")

# ============= Main =============
if __name__ == "__main__":
    print("=" * 60)
    print("Brancher IoT Dashboard Starting...")
    print("=" * 60)
    
    # Load initial config
    current_config = load_config()
    print(f"Config loaded: {current_config.get('number_of_sensor', 0)} sensors")
    
    # Connect to MQTT
    connect_mqtt()
    
    print("=" * 60)
    print("Server ready on http://127.0.0.1:5000")
    print("Use zrok to expose: zrok share public 127.0.0.1:5000")
    print("=" * 60)
    
    # Run Flask-SocketIO
    socketio.run(app, host="127.0.0.1", port=5000, debug=False, allow_unsafe_werkzeug=True)
