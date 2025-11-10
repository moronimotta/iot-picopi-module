from picozero import pico_led
import machine
import time
import json
import network
import usocket as socket
import ubinascii
import os
# TLS is optional on some MicroPython builds; guard import
try:
    import ussl as ssl_mod  # TLS for wss
    HAVE_USSL = True
except Exception:
    ssl_mod = None
    HAVE_USSL = False

# Optional HTTP fallback (keep imported lazily when used)
# import urequests

# Initialize:
# Your WiFi network credentials
ssid = "moronimotta"
password = "moroni31"

# WebSocket server settings (Render)
# For Render-hosted server, use secure WebSocket (wss) on port 443
WS_HOST = "iot-test-ae58.onrender.com"
WS_PORT = 443
WS_PATH = "/ws"
WS_TLS = True  # use TLS (wss)
USE_HTTP_FALLBACK = False  # set True to use REST POST instead of WebSocket

# Optional HTTP API (fallback)
BASE_URL = "https://iot-test-ae58.onrender.com/api/v1"
DEVICE_DATA_URL = f"{BASE_URL}/device-data"
COMMAND_POLL_URL = f"{BASE_URL}/commands/poll"
COMMAND_ACK_URL = f"{BASE_URL}/command-responses"

# Device ID - Make sure this device exists in your database first!
DEVICE_ID = "05e9bf1f-479f-4e27-b5bd-7cb80142d417"

#Pin for reading temperature
adcpin = 4
sensor = machine.ADC(adcpin)

# Functions
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


def ExecuteCommand(command, params):
    """Execute LED commands and return (status, message)."""
    try:
        if command == "LED_ON":
            pico_led.on()
            return "executed", "LED turned ON"
        elif command == "LED_OFF":
            pico_led.off()
            return "executed", "LED turned OFF"
        elif command == "BLINK":
            n = int((params or {}).get("n", 3))
            on_t = float((params or {}).get("on_time", 0.2))
            off_t = float((params or {}).get("off_time", 0.2))
            for _ in range(n):
                pico_led.on(); time.sleep(on_t); pico_led.off(); time.sleep(off_t)
            return "executed", "LED blinked %d times" % n
        else:
            return "unknown_command", "Unknown command: %s" % command
    except Exception as e:
        return "failed", "Error: %s" % (str(e))




# Main execution
def main():
    if not ConnectToInternet(ssid, password):
        print("Failed to connect to WiFi")
        for _ in range(10):
            pico_led.on(); time.sleep(0.1); pico_led.off(); time.sleep(0.1)
        return

    pico_led.on()
    print("Device ID:", DEVICE_ID)

    # If TLS is required but not available, force HTTP mode
    if WS_TLS and not HAVE_USSL:
        print("Warning: TLS (ussl) not available. Switching to HTTP mode.")
        global USE_HTTP_FALLBACK
        USE_HTTP_FALLBACK = True

    if USE_HTTP_FALLBACK:
        print("HTTP mode ->", DEVICE_DATA_URL)
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
                cmds = PollCommands(DEVICE_ID, limit=5)
                for cmd in cmds:
                    cmd_id = cmd.get("id") or cmd.get("command_id")
                    cmd_name = cmd.get("command")
                    params = cmd.get("params") or {}
                    print("HTTP command:", cmd_name, params)
                    status, message = ExecuteCommand(cmd_name, params)
                    AckCommand(cmd_id, status, message)

                time.sleep(poll_interval)
            except KeyboardInterrupt:
                print("Stopping..."); break
            except Exception as e:
                print("HTTP loop error:", e)
                time.sleep(5)
        return

    # WebSocket mode
    ws = None
    while True:
        try:
            print("Connecting WS to {}:{}{}?id={}".format(WS_HOST, WS_PORT, WS_PATH, DEVICE_ID))
            ws = SimpleWebSocket(WS_HOST, WS_PORT, WS_PATH, query="id=" + DEVICE_ID, tls=WS_TLS)
            ws.connect()
            print("WS connected")

            last_heartbeat = time.time()
            while True:
                # Send sensor data
                try:
                    temp = ReadTemperature()
                    humidity = 50.0
                    payload = {
                        "type": "sensor_data",
                        "device_id": DEVICE_ID,
                        "timestamp": GetISO8601Timestamp(),
                        "temperature": float(temp),
                        "humidity": float(humidity),
                    }
                    ws.send_text(json.dumps(payload))
                    print("WS sent sensor_data:", payload)
                except Exception as e:
                    print("send error:", e)
                    raise e

                # Heartbeat every ~30s
                now = time.time()
                if now - last_heartbeat > 30:
                    try:
                        hb = {"type": "heartbeat", "device_id": DEVICE_ID, "timestamp": GetISO8601Timestamp()}
                        ws.send_text(json.dumps(hb))
                        last_heartbeat = now
                    except Exception as e:
                        print("heartbeat error:", e)

                # Read any incoming command (socket has 1s timeout)
                try:
                    msg = ws.recv_text()
                    if msg:
                        print("WS recv:", msg)
                        try:
                            obj = json.loads(msg)
                            if obj.get("type") == "command":
                                cmd = obj.get("command")
                                params = obj.get("params") or {}
                                status, message = ExecuteCommand(cmd, params)
                                # Respond
                                resp = {
                                    "type": "command_response",
                                    "device_id": DEVICE_ID,
                                    "command_id": obj.get("command_id"),
                                    "status": status,
                                    "message": message,
                                    "timestamp": GetISO8601Timestamp(),
                                }
                                ws.send_text(json.dumps(resp))
                        except Exception as e:
                            print("parse/handle error:", e)
                except OSError as to:
                    # ignore timeout to keep loop periodic
                    pass

                time.sleep(10)

        except KeyboardInterrupt:
            print("Stopping...")
            break
        except Exception as e:
            print("WS error, reconnecting in 5s:", e)
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