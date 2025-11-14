
import sys
import json

# Environment-aware requests import
try:
    import urequests as requests  # MicroPython
    MPY = True
    import network
    import time
except ImportError:
    import requests  # Desktop Python
    MPY = False

# Simple helper to POST JSON across environments
def http_post_json(url, payload):
    if MPY:
        # Some urequests variants don't accept headers/json kwargs
        return requests.post(url, data=json.dumps(payload))
    else:
        return requests.post(url, json=payload, headers={'Content-Type': 'application/json'})

# MicroPython Wi-Fi connection helper
def connect_wifi(ssid, password, timeout=15):
    if not MPY:
        return True
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        if not wlan.isconnected():
            print("\nConnecting to Wi‑Fi...")
            wlan.connect(ssid, password)
            t = 0
            while not wlan.isconnected() and t < timeout:
                print("  waiting...", t)
                time.sleep(1)
                t += 1
        if wlan.isconnected():
            print("✓ Wi‑Fi connected:", wlan.ifconfig()[0])
            return True
        else:
            print("✗ Wi‑Fi connection failed")
            return False
    except Exception as e:
        print("✗ Wi‑Fi error:", e)
        return False

# Simulated configuration for testing
TEST_CONFIG = {
    "ssid": "moronimotta",
    "password": "moroni31",
    "user_id": "test_user_123",  # Replace with actual user_id from your system
    "device_id": None,  # Will be populated after registration
    "modules": {}  # Will be populated after module registration
}

# API Configuration (supports override via text file on device)
def read_base_url_default():
    return "https://iot-picopi-module.onrender.com/api/v1"

def read_base_url_override():
    try:
        with open('api_base_url.txt', 'r') as f:
            url = f.read().strip()
            if url:
                print(f"Using BASE_URL override from api_base_url.txt:\n  {url}")
                return url
    except Exception:
        pass
    return None

BASE_URL = read_base_url_override() or read_base_url_default()

def normalize_base_url_for_mpy(url):
    """On MicroPython, avoid TLS handshake issues by preferring http when possible."""
    if MPY and url.lower().startswith("https://"):
        http_url = "http://" + url[len("https://"):]
        print("\n⚠ TLS on MicroPython can fail with some hosts.")
        print("Trying non-TLS URL instead:")
        print("  ", http_url)
        return http_url
    return url

BASE_URL = normalize_base_url_for_mpy(BASE_URL)

def http_get(url):
    if MPY:
        return requests.get(url)
    else:
        return requests.get(url)

def probe_connectivity():
    """Lightweight probe to validate connectivity to BASE_URL host."""
    try:
        # Try a GET to the base (may be 404, that's fine; we only care about transport)
        resp = http_get(BASE_URL)
        try:
            code = getattr(resp, 'status_code', None)
            print(f"Probe status: {code}")
        finally:
            try:
                resp.close()
            except:
                pass
        return True
    except Exception as e:
        print("✗ Connectivity probe failed:", e)
        return False

def test_device_registration():
    """Test device registration endpoint"""
    
    device_name = "pico_test_device"
    payload = {
        "name": device_name,
        "type": "pico_pi",
        "user_id": TEST_CONFIG["user_id"]
    }
    
    print("\n" + "="*60)
    print("Testing Device Registration")
    print("="*60)
    print(f"Endpoint: {BASE_URL}/devices")
    
    try:
        response = http_post_json(f"{BASE_URL}/devices", payload)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            resp_data = response.json()
            # Handle nested response format: {"data": {"id": "..."}}
            data = resp_data.get("data", resp_data)
            device_id = data.get("id") or data.get("device_id")
            TEST_CONFIG["device_id"] = device_id
            print(f"\n✓ Device registered successfully!")
            print(f"  Device ID: {device_id}")
            response.close()
            return device_id
        else:
            print(f"\n✗ Registration failed")
            try:
                response.close()
            except:
                pass
            return None
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

def test_module_registration(device_id):
    """Test device module registration"""
    
    modules = ["THERMOSTAT", "WINDOW", "DOOR", "LED"]
    
    print("\n" + "="*60)
    print("Testing Module Registration")
    print("="*60)
    print(f"Device ID: {device_id}")
    print(f"Modules to register: {modules}")
    
    registered_modules = {}
    
    for module_name in modules:
        payload = {
            "name": module_name.lower(),
            "user_id": TEST_CONFIG["user_id"],
            "device_id": device_id
        }
        
        print(f"\n  Registering {module_name}...")
        print(f"  Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = http_post_json(f"{BASE_URL}/device-modules", payload)
            
            print(f"  Status Code: {response.status_code}")
            print(f"  Response: {response.text}")
            
            if response.status_code in [200, 201]:
                resp_data = response.json()
                # Handle nested response format: {"data": {"id": "..."}}
                data = resp_data.get("data", resp_data)
                module_id = data.get("id") or data.get("device_module_id")
                registered_modules[module_name] = module_id
                print(f"  ✓ {module_name} registered: {module_id}")
            else:
                print(f"  ✗ {module_name} registration failed")
            try:
                response.close()
            except:
                pass
                
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    TEST_CONFIG["modules"] = registered_modules
    print(f"\n✓ Registered {len(registered_modules)}/{len(modules)} modules")
    return registered_modules

def test_send_command(device_id, modules):
    """Test sending a command to a specific module"""
    
    if not modules.get("LED"):
        print("\n✗ LED module not registered, skipping command test")
        return
    
    print("\n" + "="*60)
    print("Testing Command Send")
    print("="*60)
    
    # Test LED BLINK command
    payload = {
        "device_id": device_id,
        "device_module_id": modules["LED"],
        "command": "BLINK",
        "params": {
            "n": 3,
            "on_time": 0.2,
            "off_time": 0.2
        }
    }
    
    print(f"Endpoint: {BASE_URL}/commands")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = http_post_json(f"{BASE_URL}/commands", payload)
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code in [200, 201]:
            print(f"\n✓ Command sent successfully!")
        else:
            print(f"\n✗ Command failed")
        try:
            response.close()
        except:
            pass
            
    except Exception as e:
        print(f"\n✗ Error: {e}")

def save_config_to_json():
    """Save test configuration to a text file for reference"""
    output_file = "test_device_config.txt"
    
    with open(output_file, 'w') as f:
        f.write("=" * 60 + "\n")
        f.write("PICO PI DEVICE CONFIGURATION\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"SSID: {TEST_CONFIG['ssid']}\n")
        f.write(f"Password: {TEST_CONFIG['password']}\n")
        f.write(f"User ID: {TEST_CONFIG['user_id']}\n")
        f.write(f"Device ID: {TEST_CONFIG['device_id']}\n\n")
        f.write("=" * 60 + "\n")
        f.write("DEVICE MODULES\n")
        f.write("=" * 60 + "\n")
        for module_name, module_id in TEST_CONFIG['modules'].items():
            f.write(f"{module_name}: {module_id}\n")
        f.write("\n" + "=" * 60 + "\n")
    
    print(f"\n✓ Configuration saved to {output_file}")
    print("\nConfiguration:")
    print(f"  Device ID: {TEST_CONFIG['device_id']}")
    print(f"  Modules: {TEST_CONFIG['modules']}")

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("PICO PI SETUP FLOW TEST SCRIPT")
    print("="*60)
    print(f"API Base URL: {BASE_URL}")
    print(f"Test User ID: {TEST_CONFIG['user_id']}")
    print("="*60)
    
    # Ensure Wi‑Fi on MicroPython
    if MPY:
        if not connect_wifi(TEST_CONFIG['ssid'], TEST_CONFIG['password']):
            print("\n✗ Cannot proceed without Wi‑Fi connectivity")
            return
        # Quick connectivity probe (may be 404; transport success is enough)
        print("\nProbing connectivity to:", BASE_URL)
        probe_connectivity()
    
    # Test 1: Register Device
    device_id = test_device_registration()
    print(device_id)
    if not device_id:
        print("\n✗ Setup failed at device registration")
        return
    
    # Test 2: Register Modules
    modules = test_module_registration(device_id)
    if not modules:
        print("\n✗ Setup failed at module registration")
        return
    
    # Test 3: Send Test Command
    test_send_command(device_id, modules)
    
    # Save configuration
    save_config_to_json()
    
    print("\n" + "="*60)
    print("✓ ALL TESTS COMPLETE")
    print("="*60)
    print("\nYou can now use this device_id and module_ids")
    print("to test commands with your Pico Pi device.")
    print("\nNext steps:")
    print("1. Upload main.py to your Pico Pi")
    print("2. Update TESTING_MODE = True in main.py")
    print("3. Update TEST_USER_ID with actual user_id")
    print("4. Run main.py on Pico Pi")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
