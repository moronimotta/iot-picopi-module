# Example configuration for Pico Pi with updated format
# This shows the structure that the Pico should send

# IMPORTANT CONFIGURATION:
# Set these values for your device:
DEVICE_ID = "your-device-id-here"  # The device ID from your database
DEVICE_MODULE_ID = "your-device-module-id-here"  # The device module ID from your database
USER_ID = "your-user-id-here"  # The user ID who owns this device

# When sending sensor data via WebSocket, use this format:
"""
{
    "type": "sensor_data",
    "device_id": "your-device-id",
    "device_module_id": "your-device-module-id",  # NEW FIELD - Required!
    "timestamp": "2024-11-10T12:34:56Z",
    "temperature": 23.5,
    "humidity": 45.2
}
"""

# When creating a device via POST /api/v1/devices, include user_id:
"""
{
    "name": "Temperature Sensor 1",
    "type": "temperature_humidity",
    "user_id": "your-user-id",  # NEW FIELD - Required!
    "status": "active"
}
"""

# When creating a device module via POST /api/v1/device-modules:
"""
{
    "device_id": "your-device-id",
    "user_id": "your-user-id",
    "name": "Main Sensor Module"
}
"""

# WORKFLOW:
# 1. Create a device with POST /api/v1/devices (include user_id)
# 2. Get the device_id from the response
# 3. Create a device_module with POST /api/v1/device-modules (include device_id and user_id)
# 4. Get the device_module_id from the response
# 5. Configure your Pico with DEVICE_ID, DEVICE_MODULE_ID, and connect via WebSocket
# 6. Pico sends sensor data including device_module_id
# 7. Data is stored in cache and processed with threshold rules every 5 minutes
# 8. Only significant changes are saved to database (threshold: temp ≥0.5°C, humidity ≥2%)

# IMPORTANT NOTES:
# - Always include device_module_id when sending sensor data
# - The first and last readings for each device are always saved
# - Intermediate readings are only saved if they exceed the threshold
# - Docker compose will automatically call POST /api/v1/process-cache every 5 minutes
