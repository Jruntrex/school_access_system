"""Attendance checking client for the guard's computer.
Sends a signed request to the director's laptop (server) to fetch the list of
present and absent students.

Usage:
    python firmware/attendance_check.py
    python firmware/attendance_check.py http://192.168.0.109:8000
"""

import hashlib
import hmac
import sys
import time
from pathlib import Path
import requests
from dotenv import dotenv_values

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV = dotenv_values(REPO_ROOT / ".env")
CARD_SCAN_API_KEY = ENV.get("CARD_SCAN_API_KEY", "")

# Default fallback URL
DEFAULT_SERVER_URL = "http://127.0.0.1:8000"


def sign(payload: str, timestamp: str) -> str:
    message = f"{payload}:{timestamp}".encode()
    return hmac.new(CARD_SCAN_API_KEY.encode(), message, hashlib.sha256).hexdigest()


def main():
    if not CARD_SCAN_API_KEY:
        print("[ПОМИЛКА] CARD_SCAN_API_KEY відсутній у файлі .env")
        sys.exit(1)

    # Allow passing server URL as arguments, otherwise use env or default
    server_base = sys.argv[1] if len(sys.argv) > 1 else ENV.get("SERVER_URL")
    if not server_base:
        server_base = DEFAULT_SERVER_URL
        print(f"[УВАГА] Не вказано адресу сервера. Використовуємо значення за замовчуванням: {server_base}")
    
    # Ensure server URL is correctly formatted
    server_base = server_base.rstrip("/")
    if not server_base.endswith("/api/access/scan") and not server_base.endswith("/api/access"):
        # If it's just the host:port, build the endpoint
        endpoint = f"{server_base}/api/access/attendance-status/"
    else:
        # If it was defined as .../api/access/scan/ in env, rewrite it
        base = server_base.split("/api/access")[0]
        endpoint = f"{base}/api/access/attendance-status/"

    print(f"Запит відвідуваності з сервера: {endpoint}...")

    timestamp = str(int(time.time()))
    signature = sign("ATTENDANCE", timestamp)

    try:
        resp = requests.get(
            endpoint,
            headers={
                "X-Timestamp": timestamp,
                "X-Signature": signature
            },
            timeout=10
        )

        if resp.status_code == 403:
            print("[ПОМИЛКА] Помилка авторизації: підпис відхилено сервером. Перевірте CARD_SCAN_API_KEY.")
            sys.exit(1)
        elif not resp.ok:
            print(f"[ПОМИЛКА] Сервер повернув помилку {resp.status_code}: {resp.text}")
            sys.exit(1)

        data = resp.json()
        print_attendance_report(data)

    except requests.RequestException as exc:
        print(f"[ПОМИЛКА] Не вдалося з'єднатися з сервером: {exc}")
        sys.exit(1)


def print_attendance_report(data):
    date = data.get("date", "Сьогодні")
    total_present = data.get("total_present", 0)
    total_absent = data.get("total_absent", 0)
    class_rows = data.get("class_rows", [])

    print("=" * 60)
    print(f"ЗВІТ З ВІДВІДУВАНОСТІ НА: {date}")
    print(f"Присутні всього: {total_present} | Відсутні всього: {total_absent}")
    print("=" * 60)

    if not class_rows:
        print("Немає даних по класах.")
        return

    for c in class_rows:
        name = c.get("name", "Невідомий клас")
        p_count = c.get("present_count", 0)
        a_count = c.get("absent_count", 0)
        
        print(f"\nКлас: {name} (Присутні: {p_count}, Відсутні: {a_count})")
        print("-" * 50)
        
        present_list = c.get("present", [])
        if present_list:
            print("  Присутні:")
            for p in present_list:
                in_b = "У приміщенні" if p.get("in_building") else "Вийшов(-ла)"
                time_str = p.get("last_entry_time") or ""
                if time_str:
                    time_str = time_str.split(".")[0].split("T")[-1][:5]  # format HH:MM
                    time_info = f" (зайшов о {time_str}, {in_b})"
                else:
                    time_info = f" ({in_b})"
                print(f"    [+] {p['last_name']} {p['first_name']}{time_info}")
        
        absent_list = c.get("absent", [])
        if absent_list:
            print("  Відсутні:")
            for a in absent_list:
                print(f"    [-] {a['last_name']} {a['first_name']}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
