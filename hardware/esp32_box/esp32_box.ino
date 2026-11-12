// Fergana Bus GPS box — ESP32 + GPS module (NEO-6M or similar) over Wi-Fi.
// Every 5 seconds: read GPS -> send {bus_id, device_key, lat, lng, passengers}
// to Supabase. Same request as tools/fake_box.py.
//
// Arduino IDE libraries: "TinyGPSPlus" (by Mikal Hart). ESP32 board package.
// Wiring (GPS -> ESP32): VCC->3V3, GND->GND, TX->GPIO16, RX->GPIO17
//
// IMPORTANT: this needs Wi-Fi (phone hotspot works). A SIM800L GSM module
// can NOT do modern HTTPS — if your box uses SIM800, tell Shokh, it needs
// a different approach (SIM7600 / A7670 modules can).

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <TinyGPSPlus.h>

// ---- change these ----
const char* WIFI_NAME  = "your-hotspot";
const char* WIFI_PASS  = "your-password";
const char* SUPA_URL   = "https://YOUR-PROJECT.supabase.co/rest/v1/rpc/report_position";
const char* SUPA_KEY   = "YOUR-ANON-OR-PUBLISHABLE-KEY";   // same as config.js
const char* BUS_ID     = "1-1";                             // row in devices table
const char* DEVICE_KEY = "change-me-box-1";                 // same row's device_key
// -----------------------

TinyGPSPlus gps;
HardwareSerial GPSSerial(2);
int passengers = 0;          // <- your passenger counter (IR sensors etc.) updates this
unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  GPSSerial.begin(9600, SERIAL_8N1, 16, 17);
  WiFi.begin(WIFI_NAME, WIFI_PASS);
  Serial.print("Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println(" connected");
}

void sendPosition(double lat, double lng) {
  WiFiClientSecure client;
  client.setInsecure();      // skip certificate check (fine for hackathon demo)
  HTTPClient http;
  http.begin(client, SUPA_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("apikey", SUPA_KEY);

  String body = String("{\"bus_id\":\"") + BUS_ID +
                "\",\"device_key\":\"" + DEVICE_KEY +
                "\",\"lat\":" + String(lat, 6) +
                ",\"lng\":" + String(lng, 6) +
                ",\"passengers\":" + passengers + "}";
  int code = http.POST(body);
  Serial.printf("POST %d %s\n", code, http.getString().c_str());   // 200 "ok" = good
  http.end();
}

void loop() {
  while (GPSSerial.available()) gps.encode(GPSSerial.read());   // feed GPS bytes

  if (millis() - lastSend > 5000) {
    lastSend = millis();
    if (gps.location.isValid() && gps.location.age() < 10000) {
      sendPosition(gps.location.lat(), gps.location.lng());
    } else {
      Serial.printf("No GPS fix yet (satellites: %d). Go near a window/outside.\n",
                    gps.satellites.value());
    }
  }
}
