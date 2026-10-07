#include <Wire.h>
#include <Adafruit_PN532.h>

// --- MODE SWITCH ---
// 1 = scan over USB serial only (this PC reads the port, no Wi-Fi needed).
// 0 = original Wi-Fi + HTTP mode (ESP32 posts straight to /api/access/scan/).
// Flip to 0 and re-flash to go back to the Wi-Fi flow below.
#define USB_SERIAL_MODE 1

#if !USB_SERIAL_MODE
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>
#include "mbedtls/md.h"
#endif

// --- PINS ---
#define I2C_SDA 8
#define I2C_SCL 9
#define LED_PIN 10
#define BUZZ_PIN 7

#if !USB_SERIAL_MODE
// --- WIFI NETWORKS ---
struct WifiNetwork {
  const char* ssid;
  const char* password;
};

WifiNetwork networks[] = {
  {"YOUR_SSID_1", "YOUR_PASSWORD_1"},
  {"YOUR_SSID_2", "YOUR_PASSWORD_2"},
};
const int networkCount = sizeof(networks) / sizeof(networks[0]);

// --- SERVER ---
// Local testing: plain HTTP to your machine's LAN IP (Django runserver
// listening on 0.0.0.0:8000). Switch back to HTTPS + WiFiClientSecure for
// any real/public deployment.
const char* SERVER_HOST = "192.168.0.109";
const int   SERVER_PORT = 8000;
const char* ENDPOINT    = "/api/access/scan/";

// --- Identifies this physical reader; must match an rfid_readers.code row ---
const char* READER_CODE = "VESTIBULE_ENTRY_1";

// --- SECURITY: HMAC-SHA256 key, must match CARD_SCAN_API_KEY in .env ---
const char* HMAC_SECRET = "8e467ebe06fafe808b4bfb1ab10b846ec6e561869dbd20d313ec507bf350865f";

// --- Consecutive HTTP failure counter ---
int consecutiveFailures = 0;
const int MAX_FAILURES  = 3;
#endif // !USB_SERIAL_MODE

// -------------------------------------------------------

Adafruit_PN532 nfc(I2C_SDA, I2C_SCL);

// --- LED helpers ---
inline void ledOn()  { digitalWrite(LED_PIN, HIGH); }
inline void ledOff() { digitalWrite(LED_PIN, LOW);  }

// --- Sound/light signals ---

// Instant feedback on card read
void beepScan() {
  ledOn(); digitalWrite(BUZZ_PIN, HIGH);
  delay(80);
  ledOff(); digitalWrite(BUZZ_PIN, LOW);
}

// Wifi connected: 3x (LED off -> beep+flash)
void beepConnected() {
  for (int i = 0; i < 3; i++) {
    ledOff();
    delay(350);
    ledOn(); digitalWrite(BUZZ_PIN, HIGH);
    delay(200);
    ledOff(); digitalWrite(BUZZ_PIN, LOW);
    delay(100);
  }
}

// N short beeps
void beepDirection(int count) {
  for (int i = 0; i < count; i++) {
    ledOn(); digitalWrite(BUZZ_PIN, HIGH);
    delay(120);
    ledOff(); digitalWrite(BUZZ_PIN, LOW);
    if (i < count - 1) delay(120);
  }
}

// One long beep — error / rejected card
void beepError() {
  ledOn(); digitalWrite(BUZZ_PIN, HIGH);
  delay(1000);
  ledOff(); digitalWrite(BUZZ_PIN, LOW);
}

#if !USB_SERIAL_MODE
// --- NTP sync (required: signatures are time-windowed) ---
void syncTime() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Syncing NTP...");
  time_t now = 0;
  int attempts = 0;
  while (now < 1000000000UL && attempts < 20) {
    delay(500);
    time(&now);
    Serial.print(".");
    attempts++;
  }
  if (now > 1000000000UL) {
    Serial.printf("\nTime synced: %lu\n", (unsigned long)now);
  } else {
    Serial.println("\n[WARNING] NTP not synced -- server will reject requests!");
  }
}

// --- HMAC-SHA256 signature ---
String computeHMAC(const String& message, const String& key) {
  unsigned char hmacResult[32];
  mbedtls_md_context_t ctx;
  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 1);
  mbedtls_md_hmac_starts(&ctx,
    (const unsigned char*)key.c_str(), key.length());
  mbedtls_md_hmac_update(&ctx,
    (const unsigned char*)message.c_str(), message.length());
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);

  String result = "";
  for (int i = 0; i < 32; i++) {
    if (hmacResult[i] < 0x10) result += "0";
    result += String(hmacResult[i], HEX);
  }
  return result;
}

// --- WiFi connect (cascades through the configured networks) ---
void connectWiFi() {
  WiFi.mode(WIFI_STA);
  ledOn();

  for (int i = 0; i < networkCount; i++) {
    Serial.printf("\nConnecting to network %d: %s", i + 1, networks[i].ssid);
    WiFi.disconnect(true);
    delay(500);
    WiFi.begin(networks[i].ssid, networks[i].password);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
      delay(500);
      Serial.print(".");
      attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.printf("\nWiFi OK -- IP: %s (network: %s)\n",
        WiFi.localIP().toString().c_str(), networks[i].ssid);
      beepConnected();
      syncTime();
      ledOff();
      return;
    }

    Serial.printf("\n[!] %s unavailable, trying next...", networks[i].ssid);
  }

  Serial.println("\n[ERROR] No network available. Restarting...");
  beepError();
  delay(3000);
  ESP.restart();
}
#endif // !USB_SERIAL_MODE

// -------------------------------------------------------

#if USB_SERIAL_MODE
// --- USB-SERIAL MODE ---
// No Wi-Fi/HTTP/HMAC here: the ESP32 just prints "UID:<hex>" over USB
// whenever a card is scanned. A PC-side bridge (firmware/serial_bridge.py)
// reads this port, signs the UID (using the PC's own clock -- there's no
// NTP time here without Wi-Fi) and POSTs it to /api/access/scan/, so the
// server-side logic (dedup, event_status, assign-mode) is unchanged.
//
// Entry/exit feedback: after printing the UID, we wait briefly for the
// bridge to write back "ENTRY" or "EXIT" (its read of the server's
// response). One beep already fired on scan; an "EXIT" reply adds a
// second beep, so staff hear 1 beep = entry, 2 beeps = exit. If the bridge
// is offline or slow, the wait just times out and the single beep stands
// -- scanning never blocks on the PC being reachable.

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(1500);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  ledOn();
  nfc.begin();
  if (!nfc.getFirmwareVersion()) {
    Serial.println("PN532 not found! Check wiring.");
    while (1) beepError();
  }
  nfc.SAMConfig();
  ledOff();
  Serial.println("--- READY (USB serial mode) ---");
}

void loop() {
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat > 5000) {
    Serial.println("HEARTBEAT");
    lastHeartbeat = millis();
  }

  uint8_t uid[7] = {0};
  uint8_t uidLength;

  if (!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 500)) return;

  String uidStr = "";
  for (uint8_t i = 0; i < uidLength; i++) {
    if (i > 0) uidStr += ":";
    if (uid[i] < 0x10) uidStr += "0";
    uidStr += String(uid[i], HEX);
  }
  uidStr.toUpperCase();

  beepScan();
  Serial.println("UID:" + uidStr);

  String direction = Serial.readStringUntil('\n');
  direction.trim();
  if (direction == "EXIT") {
    delay(120);
    beepDirection(1);
  }

  delay(500);  // remaining debounce between cards
}

#else // !USB_SERIAL_MODE -- original Wi-Fi mode

void setup() {
  Serial.begin(115200);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZ_PIN, OUTPUT);

  ledOn();

  connectWiFi();

  nfc.begin();
  if (!nfc.getFirmwareVersion()) {
    Serial.println("PN532 not found! Check wiring.");
    while (1) beepError();
  }

  nfc.SAMConfig();
  Serial.println("--- READY ---");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Connection lost, reconnecting...");
    connectWiFi();
    return;
  }

  uint8_t uid[7] = {0};
  uint8_t uidLength;

  if (!nfc.readPassiveTargetID(PN532_MIFARE_ISO14443A, uid, &uidLength, 500)) return;

  String uidStr = "";
  for (uint8_t i = 0; i < uidLength; i++) {
    if (i > 0) uidStr += ":";
    if (uid[i] < 0x10) uidStr += "0";
    uidStr += String(uid[i], HEX);
  }
  uidStr.toUpperCase();
  Serial.printf("\nUID read: %s\n", uidStr.c_str());

  beepScan();

  time_t now;
  time(&now);
  String timestamp = String((unsigned long)now);
  String message   = uidStr + ":" + timestamp;
  String signature = computeHMAC(message, String(HMAC_SECRET));

  Serial.printf("Timestamp: %s | Signature: %s\n",
    timestamp.c_str(), signature.c_str());

  HTTPClient http;
  String url = String("http://") + SERVER_HOST + ":" + SERVER_PORT + ENDPOINT;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Timestamp",  timestamp);
  http.addHeader("X-Signature",  signature);

  String jsonBody = "{\"uid\":\"" + uidStr + "\",\"reader_code\":\"" + READER_CODE + "\"}";
  int httpCode = http.POST(jsonBody);

  if (httpCode > 0) {
    consecutiveFailures = 0;
    String response = http.getString();
    Serial.printf("HTTP %d: %s\n", httpCode, response.c_str());

    if (httpCode == 403) {
      Serial.println("[SECURITY] Signature rejected by server.");
      beepError();
    } else {
      StaticJsonDocument<256> doc;
      if (!deserializeJson(doc, response)) {
        String mode = doc["mode"] | "";
        String eventStatus = doc["event_status"] | "";
        if (mode == "attendance" && eventStatus == "VALID") {
          delay(100);
          beepDirection(1);
        } else if (mode == "duplicate") {
          // already recorded moments ago -- no signal needed
        } else if (mode == "assign") {
          beepDirection(1);
        } else {
          // UNKNOWN_CARD / INACTIVE_CARD / NO_ACTIVE_ASSIGNMENT
          beepError();
        }
      } else {
        beepDirection(1);
      }
    }
  } else {
    Serial.printf("[ERROR] Request failed: %s\n",
      http.errorToString(httpCode).c_str());
    beepError();

    consecutiveFailures++;
    Serial.printf("[ERROR] Consecutive failures: %d / %d\n", consecutiveFailures, MAX_FAILURES);

    if (consecutiveFailures >= MAX_FAILURES) {
      Serial.println("[RESTART] Too many failures -- restarting...");
      delay(1500);
      ESP.restart();
    }
  }

  http.end();
  delay(2000);  // debounce between cards
}

#endif // USB_SERIAL_MODE
