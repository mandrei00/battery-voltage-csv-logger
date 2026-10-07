#include <Wire.h>
#include <Adafruit_ADS1X15.h>

Adafruit_ADS1115 ads;

// --- Настройки ---
const uint32_t SAMPLE_PERIOD_MS = 100;  // 10 Гц

uint32_t next_sample_ms = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("CR1632 Battery Logger");

  if (!ads.begin()) {
    Serial.println("ERROR: ADS1115 not found!");
    while (1);
  }

  // GAIN_ONE = ±4.096V — покрывает всю CR1632 с запасом
  ads.setGain(GAIN_ONE);
  ads.setDataRate(RATE_ADS1115_128SPS);

  next_sample_ms = millis();
}

void loop() {
  uint32_t now = millis();

  // Неблокирующий таймер: период не «плывёт» из-за времени чтения АЦП
  if ((int32_t)(now - next_sample_ms) >= 0) {
    next_sample_ms += SAMPLE_PERIOD_MS;

    int16_t raw = ads.readADC_SingleEnded(0);
    float voltage = ads.computeVolts(raw);

    Serial.println(voltage, 5);
  }
}