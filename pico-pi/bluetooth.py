from machine import UART, Pin
import time

# Configure UART0 (pins GP0, GP1)
uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

print("📡 Waiting for Bluetooth data...")

while True:
    if uart.any():  # Check if data is available
        data = uart.readline()  # Read one line
        if data:
            try:
                decoded = data.decode('utf-8').strip()
                print("🔹 Received:", decoded)
            except UnicodeError:
                print("⚠️ Received undecodable bytes:", data)
    time.sleep(0.1)
