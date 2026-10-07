"""USB-serial bridge for the reader running in USB_SERIAL_MODE (see
school-rfid/school-rfid.ino). The ESP32 has no Wi-Fi/NTP in this mode, so it
just prints "UID:<hex>" over USB whenever a card is scanned; this script
reads that line, signs it the same way the Wi-Fi firmware would
(HMAC-SHA256 over "UID:timestamp", using CARD_SCAN_API_KEY from .env) and
POSTs it to /api/access/scan/ -- the server-side logic is unaffected.

The server's response carries "direction": "ENTRY" or "EXIT" (the toggle
decided server-side, based on the student's last scan today). This script
writes that word back over serial so the board can beep twice for an exit
(one beep already fired on the read itself).

Usage:
    python firmware/serial_bridge.py           # lists available ports
    python firmware/serial_bridge.py COM5
"""

import hashlib
import hmac
import sys
import time
from pathlib import Path

import requests
import serial
import serial.tools.list_ports
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(REPO_ROOT / ".env")
CARD_SCAN_API_KEY = ENV.get("CARD_SCAN_API_KEY", "")

SERVER_URL = "http://127.0.0.1:8000/api/access/scan/"
READER_CODE = "VESTIBULE_ENTRY_1"
BAUD_RATE = 115200


def sign(uid: str, timestamp: str) -> str:
    message = f"{uid}:{timestamp}".encode()
    return hmac.new(CARD_SCAN_API_KEY.encode(), message, hashlib.sha256).hexdigest()


def list_ports() -> None:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("No serial ports found.")
        return
    print("Available ports:")
    for p in ports:
        print(f"  {p.device}  ({p.description})")
    print("\nUsage: python firmware/serial_bridge.py <PORT>")


def main(port: str) -> None:
    if not CARD_SCAN_API_KEY:
        print("[ERROR] CARD_SCAN_API_KEY missing from .env")
        sys.exit(1)

    server_url = ENV.get("SERVER_URL", SERVER_URL)
    print(f"Watchdog Serial Bridge starting. Port: {port}, Server: {server_url}")

    while True:
        try:
            print(f"Connecting to {port}...")
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            print(f"Connected to {port} -- Listening for scans/heartbeats...")
            
            last_activity = time.time()
            
            while True:
                line = ser.readline().decode(errors="ignore").strip()
                current_time = time.time()
                
                if line:
                    last_activity = current_time
                    if line == "HEARTBEAT":
                        # Print heartbeat with local time to show health status
                        print(f"[{time.strftime('%H:%M:%S')}] [WATCHDOG] Heartbeat received.")
                        continue
                    
                    if not line.startswith("UID:"):
                        print(f"[device] {line}")
                        continue

                    uid = line[len("UID:"):]
                    timestamp = str(int(time.time()))
                    signature = sign(uid, timestamp)

                    try:
                        resp = requests.post(
                            server_url,
                            json={"uid": uid, "reader_code": READER_CODE},
                            headers={"X-Timestamp": timestamp, "X-Signature": signature},
                            timeout=5,
                        )
                        print(f"[{time.strftime('%H:%M:%S')}] UID {uid} -> HTTP {resp.status_code}: {resp.text}")

                        direction = None
                        if resp.ok:
                            direction = resp.json().get("direction")
                        if direction in ("ENTRY", "EXIT"):
                            ser.write(f"{direction}\n".encode())
                    except requests.RequestException as exc:
                        print(f"[ERROR] API request failed: {exc}")
                
                # Watchdog check: if no activity for 15 seconds, reset board
                if current_time - last_activity > 15:
                    print(f"\n[{time.strftime('%H:%M:%S')}] [WATCHDOG] No activity for 15 seconds. Resetting ESP32 board...")
                    # Toggle DTR/RTS to reset the board
                    ser.dtr = False
                    ser.rts = True
                    time.sleep(0.1)
                    ser.dtr = True
                    ser.rts = False
                    time.sleep(0.5)
                    last_activity = time.time()

        except (serial.SerialException, OSError) as exc:
            print(f"[CONNECTION ERROR] Serial error on {port}: {exc}")
            print("Retrying connection in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        list_ports()
        sys.exit(0)
    main(sys.argv[1])
