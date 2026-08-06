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

    ser = serial.Serial(port, BAUD_RATE, timeout=1)
    print(f"Listening on {port} -- forwarding scans to {SERVER_URL}")

    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        if not line.startswith("UID:"):
            print(f"[device] {line}")
            continue

        uid = line[len("UID:"):]
        timestamp = str(int(time.time()))
        signature = sign(uid, timestamp)

        try:
            resp = requests.post(
                SERVER_URL,
                json={"uid": uid, "reader_code": READER_CODE},
                headers={"X-Timestamp": timestamp, "X-Signature": signature},
                timeout=5,
            )
            print(f"UID {uid} -> HTTP {resp.status_code}: {resp.text}")

            direction = None
            if resp.ok:
                direction = resp.json().get("direction")
            if direction in ("ENTRY", "EXIT"):
                ser.write(f"{direction}\n".encode())
        except requests.RequestException as exc:
            print(f"[ERROR] {exc}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        list_ports()
        sys.exit(0)
    main(sys.argv[1])
