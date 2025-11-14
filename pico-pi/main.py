from picozero import pico_led
import machine
import time
import json
import network
import usocket as socket
import ubinascii
import os

# TLS support detection for MicroPython (ussl or ssl)
try:
    import ussl as ssl_mod
    HAVE_USSL = True
except ImportError:
    try:
        import ssl as ssl_mod
        HAVE_USSL = True
    except ImportError:
        ssl_mod = None
        HAVE_USSL = False

# ==================== CONFIGURATION ====================
# Testing mode - Set to True to use hardcoded credentials
TESTING_MODE = True

# Test credentials (used only when TESTING_MODE = True)
TEST_SSID = "optix"
TEST_PASSWORD = "onmyhonor"
TEST_USER_ID = "test_user_123"  # Replace with actual user_id from your system

# Configuration file path
CONFIG_FILE = "device_config.json"

# WebSocket server settings
WS_HOST = "nonelectrically-jocund-scot.ngrok-free.dev"
WS_PORT = 443
WS_PATH = "/ws"
WS_TLS = True  # use TLS (wss)
USE_HTTP_FALLBACK = False  # set True to use REST POST instead of WebSocket

# API endpoints
BASE_URL = "https://nonelectrically-jocund-scot.ngrok-free.dev/api/v1"
DEVICE_REGISTER_URL = f"{BASE_URL}/devices"
DEVICE_MODULE_URL = f"{BASE_URL}/device-modules"
DEVICE_DATA_URL = f"{BASE_URL}/device-data"
COMMAND_POLL_URL = f"{BASE_URL}/commands/poll"
COMMAND_ACK_URL = f"{BASE_URL}/command-responses"

# Device modules to register
DEVICE_MODULES = {
    "THERMOSTAT": None,  # Will store device_module_id
    "WINDOW": None,
    "DOOR": None,
    "LED": None
}

#Pin for reading temperature
adcpin = 4
sensor = machine.ADC(adcpin)

# ==================== CONFIGURATION FILE MANAGEMENT ====================

def LoadConfig():
    """Load configuration from JSON file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            print("✓ Config loaded:", config.keys())
            return config
    except OSError:
        print("✗ Config file not found")
        return None
    except Exception as e:
        print("✗ Error loading config:", e)
        return None

def SaveConfig(config):
    """Save configuration to JSON file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        print("✓ Config saved")
        return True
    except Exception as e:
        print("✗ Error saving config:", e)
        return False

def GetMACAddress():
    """Get device MAC address as unique identifier"""
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    mac = ubinascii.hexlify(wlan.config('mac')).decode()
    return mac

# ==================== BLUETOOTH LISTENER ====================

def ListenForBluetoothConfig():
    """
    Placeholder: Listen for Bluetooth connection to receive SSID, password, and user_id
    In production, this would use Bluetooth Low Energy to receive credentials from mobile app
    """
    print("=" * 50)
    print("BLUETOOTH LISTENER MODE")
    print("=" * 50)
    print("Waiting for Bluetooth connection...")
    print("Expected data: {ssid, password, user_id}")
    print("")
    print("TODO: Implement BLE receiver")
    print("For now, using hardcoded test credentials")
    print("=" * 50)
    
    # In testing mode, return test credentials
    if TESTING_MODE:
        return {
            "ssid": TEST_SSID,
            "password": TEST_PASSWORD,
            "user_id": TEST_USER_ID
        }
    
    # In production, implement BLE receiver here
    # Example structure:
    # ble = bluetooth.BLE()
    # Wait for connection and receive JSON with credentials
    # return received_data
    
    return None

# ==================== DEVICE REGISTRATION ====================

def RegisterDevice(config):
    """Register device with API and get device_id"""
    try:
        import urequests
        
        mac_address = GetMACAddress()
        device_name = f"pico_{mac_address[-6:]}"  # Last 6 chars of MAC
        
        payload = {
            "name": device_name,
            "type": "pico_pi",
            "user_id": config["user_id"]
        }
        
        print(f"Registering device: {device_name}")
        headers = {'Content-Type': 'application/json'}
        response = urequests.post(
            DEVICE_REGISTER_URL, 
            data=json.dumps(payload), 
            headers=headers
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            device_id = data.get("id") or data.get("device_id")
            print(f"✓ Device registered: {device_id}")
            response.close()
            return device_id
        else:
            print(f"✗ Registration failed: {response.status_code}")
            try:
                print(f"  Response: {response.text}")
            except:
                pass
            response.close()
            return None
            
    except Exception as e:
        print(f"✗ Device registration error: {e}")
        return None

# ==================== MODULE REGISTRATION ====================

def RegisterDeviceModules(device_id, user_id):
    """Register all device modules and return updated DEVICE_MODULES dict"""
    try:
        import urequests
        
        modules = DEVICE_MODULES.copy()
        headers = {'Content-Type': 'application/json'}
        
        print("\nRegistering device modules...")
        for module_name in modules.keys():
            payload = {
                "name": module_name.lower(),
                "user_id": user_id,
                "device_id": device_id
            }
            
            print(f"  Registering {module_name}...", end=" ")
            response = urequests.post(
                DEVICE_MODULE_URL,
                data=json.dumps(payload),
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                data = response.json()
                module_id = data.get("id") or data.get("device_module_id")
                modules[module_name] = module_id
                print(f"✓ {module_id}")
            else:
                print(f"✗ Failed ({response.status_code})")
                try:
                    print(f"    Response: {response.text}")
                except:
                    pass
            
            response.close()
            time.sleep(0.5)  # Brief delay between requests
        
        print("✓ Module registration complete")
        return modules
        
    except Exception as e:
        print(f"✗ Module registration error: {e}")
        return None

# ==================== SENSOR FUNCTIONS ====================

def ReadTemperature():
    adc_value = sensor.read_u16()
    volt = (3.3/65535) * adc_value
    c_temperature = 27 - (volt - 0.706)/0.001721
    f_temperature = (c_temperature * 9 / 5) + 32
    return round(f_temperature, 1)

def GetISO8601Timestamp():
    """Generate ISO 8601 timestamp (RFC3339 format)"""
    # MicroPython doesn't have strftime, so we format manually
    current_time = time.localtime()
    return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
        current_time[0], current_time[1], current_time[2],
        current_time[3], current_time[4], current_time[5]
    )

def CreateDeviceDataJSON(temperature, humidity, device_id=None):
    """Create JSON payload matching the DeviceData entity structure"""
    if device_id is None:
        device_id = DEVICE_ID
    
    data = {
        "device_id": device_id,
        "temperature": float(temperature),
        "humidity": float(humidity),
        "timestamp": GetISO8601Timestamp()
    }
    
    json_packet = json.dumps(data)
    return json_packet

def ConnectToInternet(ssid, password):
    # Create a wireless interface object
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    # Connect to the network
    wlan.connect(ssid, password)
    
    # Wait for the connection to establish
    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('Waiting for connection...')
        time.sleep(1)
    
    # Check connection status
    if wlan.status() != 3:
        print('Network connection failed')
        return False
    else:
        print('Connected to WiFi')
        status = wlan.ifconfig()
        print('IP address:', status[0])
        return True

def SendDataHTTP(json_data):
    try:
        import urequests
        headers = {'Content-Type': 'application/json'}
        response = urequests.post(DEVICE_DATA_URL, data=json_data, headers=headers)
        print("HTTP status:", response.status_code)
        print("HTTP resp:", response.text)
        response.close()
        return True
    except Exception as e:
        print("HTTP error:", e)
        return False

def SendSensorData():
    """Read sensor and send actual data"""
    try:
        temperature = ReadTemperature()
        # You can add a humidity sensor reading here if you have one
        humidity = 50.0  # Default value, replace with actual sensor reading
        
        json_data = CreateDeviceDataJSON(temperature, humidity)
        print("HTTP sending sensor data:", json_data)
        return SendDataHTTP(json_data)
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return False

def SendDummyData():
    """Send dummy JSON data for testing"""
    temperature = 23.5
    humidity = 45.2
    
    json_data = CreateDeviceDataJSON(temperature, humidity)
    print("HTTP sending dummy data:", json_data)
    return SendDataHTTP(json_data)


# -------------------- Simple WebSocket Client --------------------

class SimpleWebSocket:
    def __init__(self, host, port, path, query="", tls=False):
        self.host = host
        self.port = port
        self.path = path
        self.query = query
        self.sock = None
        self.tls = tls

    def connect(self):
        addr_info = socket.getaddrinfo(self.host, self.port)[0][-1]
        s = socket.socket()
        s.settimeout(5)
        s.connect(addr_info)
        # Wrap with TLS if requested (for wss)
        if self.tls:
            if not HAVE_USSL:
                try:
                    s.close()
                except:
                    pass
                raise OSError("TLS not available on this firmware (ussl missing)")
            try:
                s = ssl_mod.wrap_socket(s, server_hostname=self.host)
            except Exception as e:
                try:
                    s.close()
                except:
                    pass
                raise e

        # Handshake
        key = ubinascii.b2a_base64(os.urandom(16)).strip().decode()
        path = self.path
        if self.query:
            path += "?" + self.query
        scheme = "https" if self.tls else "http"
        origin = "%s://%s" % (scheme, self.host)
        headers = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Origin: {}\r\n"
            "Sec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path, self.host, self.port, origin, key)
        s.send(headers.encode())

        # Read HTTP 101 response
        resp = b""
        try:
            while True:
                chunk = s.recv(64)
                if not chunk:
                    break
                resp += chunk
                if b"\r\n\r\n" in resp:
                    break
        except Exception as e:
            s.close()
            raise e

        if b" 101 " not in resp or b"Upgrade: websocket" not in resp:
            s.close()
            raise OSError("WebSocket handshake failed: " + resp.decode())

        s.settimeout(1)
        self.sock = s

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except:
            pass
        self.sock = None

    def _send_frame(self, opcode, data_bytes):
        if self.sock is None:
            raise OSError("WebSocket not connected")
        # FIN + opcode
        b1 = 0x80 | (opcode & 0x0F)
        # Client MUST mask payload
        mask_bit = 0x80
        n = len(data_bytes)
        if n < 126:
            header = bytes([b1, mask_bit | n])
        elif n < (1 << 16):
            header = bytes([b1, mask_bit | 126, (n >> 8) & 0xFF, n & 0xFF])
        else:
            # Very large frames not expected in our use; implement 64-bit length
            header = bytes([
                b1,
                mask_bit | 127,
                0, 0, 0, 0,  # high 32 bits zero
                (n >> 24) & 0xFF, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF,
            ])
        mask = os.urandom(4)
        masked = bytearray(n)
        for i in range(n):
            masked[i] = data_bytes[i] ^ mask[i % 4]
        self.sock.send(header + mask + masked)

    def send_text(self, text):
        if isinstance(text, str):
            data = text.encode()
        else:
            data = text
        self._send_frame(0x1, data)

    def _recv_exact(self, num):
        buf = b""
        while len(buf) < num:
            chunk = self.sock.recv(num - len(buf))
            if not chunk:
                raise OSError("socket closed")
            buf += chunk
        return buf

    def recv_text(self):
        # Parse one frame (text/ping). Timeout is handled by socket timeout.
        hdr = self.sock.recv(2)
        if not hdr or len(hdr) < 2:
            return None
        b1, b2 = hdr[0], hdr[1]
        fin = b1 & 0x80
        opcode = b1 & 0x0F
        masked = b2 & 0x80
        length = b2 & 0x7F
        if length == 126:
            ext = self._recv_exact(2)
            length = (ext[0] << 8) | ext[1]
        elif length == 127:
            ext = self._recv_exact(8)
            # handle lower 32-bits
            length = 0
            for b in ext[4:]:
                length = (length << 8) | b
        if masked:
            mkey = self._recv_exact(4)
        else:
            mkey = None
        payload = self._recv_exact(length) if length > 0 else b""
        if masked and mkey:
            unmasked = bytearray(length)
            for i in range(length):
                unmasked[i] = payload[i] ^ mkey[i % 4]
            payload = bytes(unmasked)

        # Handle opcodes
        if opcode == 0x9:  # ping
            # reply pong
            # minimal pong: opcode 0xA, empty
            try:
                self._send_frame(0xA, b"")
            except Exception as e:
                print("pong send error:", e)
            return None
        if opcode == 0x1:  # text
            try:
                return payload.decode()
            except:
                return None
        if opcode == 0x8:  # close
            raise OSError("websocket closed by server")
        # Ignore others
        return None


# -------------------- HTTP Command Polling Helpers --------------------

def PollCommands(device_id, limit=5):
    try:
        import urequests
        url = COMMAND_POLL_URL + "?device_id=" + device_id + "&limit=" + str(limit)
        resp = urequests.get(url)
        if resp.status_code != 200:
            try:
                txt = resp.text
            except:
                txt = ""
            print("poll http status:", resp.status_code, txt)
            resp.close()
            return []
        data = resp.json()
        resp.close()
        cmds = data.get("commands") or []
        return cmds
    except Exception as e:
        print("poll error:", e)
        return []


def AckCommand(command_id, status, message):
    try:
        import urequests
        headers = {'Content-Type': 'application/json'}
        payload = json.dumps({
            "command_id": command_id,
            "status": status,
            "message": message or ""
        })
        resp = urequests.post(COMMAND_ACK_URL, data=payload, headers=headers)
        ok = (resp.status_code == 200)
        try:
            print("ack status:", resp.status_code, resp.text)
        except:
            pass
        resp.close()
        return ok
    except Exception as e:
        print("ack error:", e)
        return False


# ==================== MODULE COMMAND HANDLERS ====================

def ExecuteThermostatCommand(command, params):
    """Handle THERMOSTAT module commands"""
    print(f"[THERMOSTAT] Command: {command}, Params: {params}")
    # TODO: Implement thermostat-specific commands
    # Examples: SET_TEMPERATURE, GET_TEMPERATURE, SET_MODE
    if command == "SET_TEMPERATURE":
        temp = params.get("temperature", 70)
        print(f"  → Setting thermostat to {temp}°F")
        return "executed", f"Thermostat set to {temp}°F"
    elif command == "GET_TEMPERATURE":
        current_temp = ReadTemperature()
        print(f"  → Current temperature: {current_temp}°F")
        return "executed", f"Temperature: {current_temp}°F"
    else:
        return "unknown_command", f"Unknown thermostat command: {command}"

def ExecuteWindowCommand(command, params):
    """Handle WINDOW module commands"""
    print(f"[WINDOW] Command: {command}, Params: {params}")
    # TODO: Implement window-specific commands
    # Examples: OPEN, CLOSE, GET_STATUS
    if command == "OPEN":
        print("  → Opening window")
        return "executed", "Window opened"
    elif command == "CLOSE":
        print("  → Closing window")
        return "executed", "Window closed"
    else:
        return "unknown_command", f"Unknown window command: {command}"

def ExecuteDoorCommand(command, params):
    """Handle DOOR module commands"""
    print(f"[DOOR] Command: {command}, Params: {params}")
    # TODO: Implement door-specific commands
    # Examples: LOCK, UNLOCK, GET_STATUS
    if command == "LOCK":
        print("  → Locking door")
        return "executed", "Door locked"
    elif command == "UNLOCK":
        print("  → Unlocking door")
        return "executed", "Door unlocked"
    else:
        return "unknown_command", f"Unknown door command: {command}"

def ExecuteLEDCommand(command, params):
    """Handle LED module commands"""
    print(f"[LED] Command: {command}, Params: {params}")
    try:
        if command == "LED_ON" or command == "ON":
            pico_led.on()
            print("  → LED turned ON")
            return "executed", "LED turned ON"
        elif command == "LED_OFF" or command == "OFF":
            pico_led.off()
            print("  → LED turned OFF")
            return "executed", "LED turned OFF"
        elif command == "BLINK":
            n = int((params or {}).get("n", 3))
            on_t = float((params or {}).get("on_time", 0.2))
            off_t = float((params or {}).get("off_time", 0.2))
            print(f"  → Blinking LED {n} times")
            for _ in range(n):
                pico_led.on(); time.sleep(on_t); pico_led.off(); time.sleep(off_t)
            return "executed", "LED blinked %d times" % n
        else:
            return "unknown_command", f"Unknown LED command: {command}"
    except Exception as e:
        return "failed", "Error: %s" % (str(e))

def RouteCommand(device_module_id, command, params, modules):
    """
    Route command to appropriate module handler based on device_module_id
    This is the switch/case logic that routes to the right function
    """
    print(f"\n🔀 Routing command: {command}")
    print(f"   Module ID: {device_module_id}")
    
    # Find which module this ID belongs to
    module_name = None
    for name, mod_id in modules.items():
        if mod_id == device_module_id:
            module_name = name
            break
    
    if not module_name:
        print(f"✗ Unknown module ID: {device_module_id}")
        return "failed", "Unknown device_module_id"
    
    print(f"   Module: {module_name}")
    
    # Switch case: route to appropriate handler
    if module_name == "THERMOSTAT":
        return ExecuteThermostatCommand(command, params)
    elif module_name == "WINDOW":
        return ExecuteWindowCommand(command, params)
    elif module_name == "DOOR":
        return ExecuteDoorCommand(command, params)
    elif module_name == "LED":
        return ExecuteLEDCommand(command, params)
    else:
        return "failed", f"No handler for module: {module_name}"

def ExecuteCommand(command, params, device_module_id=None, modules=None):
    """
    Execute commands - maintains backward compatibility
    If device_module_id is provided, routes to specific module
    Otherwise, treats as generic LED command for backward compatibility
    """
    if device_module_id and modules:
        return RouteCommand(device_module_id, command, params, modules)
    else:
        # Fallback to LED commands for backward compatibility
        return ExecuteLEDCommand(command, params)




# ==================== SETUP FLOW ====================

def SetupDevice():
    """
    Complete device setup flow:
    1. Check for config file
    2. If missing, listen for Bluetooth credentials
    3. Register device with API
    4. Register all device modules
    5. Save complete config
    """
    print("\n" + "=" * 50)
    print("DEVICE SETUP FLOW")
    print("=" * 50)
    
    # Step 1: Check for existing configuration
    config = LoadConfig()
    
    if config and config.get("device_id") and config.get("modules"):
        print("✓ Device already configured")
        print(f"  Device ID: {config['device_id']}")
        print(f"  Modules: {len(config['modules'])} registered")
        return config
    
    # Step 2: Get WiFi credentials and user_id
    print("\nStep 1: Getting credentials...")
    if not config:
        # Listen for Bluetooth or use test credentials
        credentials = ListenForBluetoothConfig()
        if not credentials:
            print("✗ Failed to get credentials")
            return None
        
        config = credentials
    
    # Verify we have required fields
    if not config.get("ssid") or not config.get("password") or not config.get("user_id"):
        print("✗ Missing required credentials (ssid, password, user_id)")
        return None
    
    # Step 3: Connect to WiFi
    print("\nStep 2: Connecting to WiFi...")
    if not ConnectToInternet(config["ssid"], config["password"]):
        print("✗ Failed to connect to WiFi")
        return None
    
    # Step 4: Register device
    print("\nStep 3: Registering device...")
    device_id = RegisterDevice(config)
    if not device_id:
        print("✗ Device registration failed")
        return None
    
    config["device_id"] = device_id
    
    # Step 5: Register device modules
    print("\nStep 4: Registering device modules...")
    modules = RegisterDeviceModules(device_id, config["user_id"])
    if not modules:
        print("✗ Module registration failed")
        return None
    
    config["modules"] = modules
    
    # Step 6: Save complete configuration
    print("\nStep 5: Saving configuration...")
    if not SaveConfig(config):
        print("✗ Failed to save config")
        return None
    
    print("\n" + "=" * 50)
    print("✓ SETUP COMPLETE")
    print("=" * 50)
    print(f"Device ID: {device_id}")
    print(f"Modules registered: {list(modules.keys())}")
    print("=" * 50 + "\n")
    
    return config

# ==================== MAIN EXECUTION ====================

def main():
    """Main execution loop with setup flow"""
    print("\n" + "=" * 50)
    print("PICO PI IoT DEVICE - STARTING")
    print("=" * 50)
    print(f"Testing Mode: {TESTING_MODE}")
    print("=" * 50 + "\n")
    
    # Run setup flow
    config = SetupDevice()
    if not config:
        print("\n✗ Setup failed - cannot continue")
        # Blink LED rapidly to indicate error
        for _ in range(10):
            pico_led.on(); time.sleep(0.1); pico_led.off(); time.sleep(0.1)
        return
    
    # Extract config values
    device_id = config["device_id"]
    modules = config["modules"]
    
    # Ensure WiFi is connected
    if not ConnectToInternet(config["ssid"], config["password"]):
        print("✗ WiFi connection lost")
        return
    
    pico_led.on()
    print(f"\n✓ Device ready: {device_id}")
    print(f"✓ Modules: {list(modules.keys())}")

    # If TLS is required but not available, force HTTP mode
    if WS_TLS and not HAVE_USSL:
        print("Warning: TLS (ussl) not available. Switching to HTTP mode.")
        global USE_HTTP_FALLBACK
        USE_HTTP_FALLBACK = True

    if USE_HTTP_FALLBACK:
        print("\n📡 HTTP POLLING MODE")
        print("=" * 50)
        print(f"Data endpoint: {DEVICE_DATA_URL}")
        print(f"Poll endpoint: {COMMAND_POLL_URL}")
        print("=" * 50 + "\n")
        
        last_send = 0
        poll_interval = 5
        send_interval = 30
        while True:
            try:
                now = time.time()
                # Periodic sensor send
                if now - last_send >= send_interval:
                    if SendSensorData():
                        print("✓ HTTP data sent")
                    else:
                        print("✗ HTTP send failed")
                    last_send = now

                # Poll commands
                cmds = PollCommands(device_id, limit=5)
                for cmd in cmds:
                    cmd_id = cmd.get("id") or cmd.get("command_id")
                    cmd_name = cmd.get("command")
                    cmd_module_id = cmd.get("device_module_id")
                    params = cmd.get("params") or {}
                    
                    print(f"\n📥 HTTP command received: {cmd_name}")
                    
                    # Route command to appropriate module
                    status, message = ExecuteCommand(
                        cmd_name, 
                        params, 
                        device_module_id=cmd_module_id,
                        modules=modules
                    )
                    
                    print(f"📤 Acknowledging: {status} - {message}")
                    AckCommand(cmd_id, status, message)

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                print("\n⏹ Stopping..."); break
            except Exception as e:
                print(f"✗ HTTP loop error: {e}")
                time.sleep(5)
        return

    # WebSocket mode
    print("\n🔌 WEBSOCKET MODE")
    print("=" * 50)
    print(f"Host: {WS_HOST}:{WS_PORT}")
    print(f"Path: {WS_PATH}")
    print(f"Device ID: {device_id}")
    print("=" * 50 + "\n")
    
    ws = None
    while True:
        try:
            print(f"Connecting WS to {WS_HOST}:{WS_PORT}{WS_PATH}?id={device_id}")
            ws = SimpleWebSocket(WS_HOST, WS_PORT, WS_PATH, query="id=" + device_id, tls=WS_TLS)
            ws.connect()
            print("✓ WebSocket connected\n")

            last_heartbeat = time.time()
            while True:
                # Send sensor data
                try:
                    temp = ReadTemperature()
                    humidity = 50.0
                    payload = {
                        "type": "sensor_data",
                        "device_id": device_id,
                        "timestamp": GetISO8601Timestamp(),
                        "temperature": float(temp),
                        "humidity": float(humidity),
                    }
                    ws.send_text(json.dumps(payload))
                    print(f"📤 Sent sensor data: {temp}°F, {humidity}%")
                except Exception as e:
                    print(f"✗ Send error: {e}")
                    raise e

                # Heartbeat every ~30s
                now = time.time()
                if now - last_heartbeat > 30:
                    try:
                        hb = {
                            "type": "heartbeat", 
                            "device_id": device_id, 
                            "timestamp": GetISO8601Timestamp()
                        }
                        ws.send_text(json.dumps(hb))
                        print("💓 Heartbeat sent")
                        last_heartbeat = now
                    except Exception as e:
                        print(f"✗ Heartbeat error: {e}")

                # Read any incoming command (socket has 1s timeout)
                try:
                    msg = ws.recv_text()
                    if msg:
                        print(f"\n📥 WS received: {msg}")
                        try:
                            obj = json.loads(msg)
                            if obj.get("type") == "command":
                                cmd = obj.get("command")
                                cmd_module_id = obj.get("device_module_id")
                                params = obj.get("params") or {}
                                
                                # Route command to appropriate module
                                status, message = ExecuteCommand(
                                    cmd, 
                                    params,
                                    device_module_id=cmd_module_id,
                                    modules=modules
                                )
                                
                                # Send response back
                                resp = {
                                    "type": "command_response",
                                    "device_id": device_id,
                                    "command_id": obj.get("command_id"),
                                    "status": status,
                                    "message": message,
                                    "timestamp": GetISO8601Timestamp(),
                                }
                                ws.send_text(json.dumps(resp))
                                print(f"📤 Response sent: {status} - {message}\n")
                        except Exception as e:
                            print(f"✗ Parse/handle error: {e}")
                except OSError as to:
                    # ignore timeout to keep loop periodic
                    pass

                time.sleep(10)

        except KeyboardInterrupt:
            print("\n⏹ Stopping...")
            break
        except Exception as e:
            print(f"✗ WS error: {e}")
            print("Reconnecting in 5s...")
            try:
                if ws:
                    ws.close()
            except:
                pass
            time.sleep(5)
            continue



# Run the main function
if __name__ == "__main__":
    main()

