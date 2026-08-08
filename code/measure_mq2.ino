/*  SAFE-Fire - MQ-2 burn-in logger, then measurement
 *  ---------------------------------------------------------------
 *  AO -> 6.8k -> GPIO 34, and 10k from that junction to GND.
 *  Divider gain = (6.8 + 10) / 10 = 1.68
 *
 *  SET UP FOR 5 V. Move the MQ-2 VCC to the 5 V rail before uploading
 *  this. Use the 5 V / 3 A supply, not a laptop USB port: the heater
 *  draws about 150 mA continuously and this is meant to run for days.
 *
 *  WHAT IT DOES
 *      Checks the divider, then logs one line a minute and leaves the
 *      sensor to burn in. A new MQ sensor drifts for 24-48 hours; the
 *      only way to know it is finished is to watch the drift die out,
 *      which is what the d10m and d60m columns are for. Calibrating
 *      before that gives an R0 that is wrong by the time you use it.
 *
 *      Press m when the drift has settled to take the baseline and go
 *      to live measurement.
 *
 *  WHY THERE IS NO RL IN THIS SKETCH
 *      Rs = RL * (Vc - Vo) / Vo needs the module's load resistor, which
 *      is not printed on the board and differs between makers. Nothing
 *      here needs Rs in ohms - only the RATIO, and RL cancels out:
 *
 *          Rs/R0 = [(Vc - Vo) / Vo] * [Vo0 / (Vc - Vo0)]
 *
 *      So the unknown disappears instead of being guessed at, and the
 *      divider's loading of RL is absorbed with it, as long as the
 *      baseline is taken with the divider connected. It is.
 *
 *  Keys:  m go to measurement   s summary now   b re-take baseline
 */

#define PIN_MQ2         34
#define DIVIDER_GAIN  1.68f     // (6.8k + 10k) / 10k
#define SUPPLY_V       5.0f     // the MQ-2 VCC rail
#define AVG_N            64
#define LOG_INTERVAL_S   60
#define RING            120     // two hours of one-minute samples
#define STABLE_V      0.005f    // drift over an hour that counts as settled

static float    ring[RING];
static int      ringN = 0, ringHead = 0;
static float    vFirst = NAN, vo0 = NAN;
static uint32_t startMs, minutes = 0;
static bool     measuring = false, announced = false;

/* ------------------------------------------------------------------ helpers */

static void rule() {
  Serial.println(F("----------------------------------------------------------"));
}

static float readAo() {                 // AO volts, divider undone
  uint32_t acc = 0;
  for (int i = 0; i < AVG_N; i++) {
    acc += analogReadMilliVolts(PIN_MQ2);
    delayMicroseconds(300);
  }
  return (acc / (float)AVG_N) / 1000.0f * DIVIDER_GAIN;
}

static uint16_t readRaw() {
  uint32_t acc = 0;
  for (int i = 0; i < AVG_N; i++) { acc += analogRead(PIN_MQ2); delayMicroseconds(300); }
  return acc / AVG_N;
}

static void push(float v) {
  ring[ringHead] = v;
  ringHead = (ringHead + 1) % RING;
  if (ringN < RING) ringN++;
}

/* value from m minutes ago, or NAN if the log is not that old yet */
static float ago(int m) {
  if (m >= ringN) return NAN;
  return ring[(ringHead - 1 - m + RING) % RING];
}

static float ratio(float vo) {
  if (isnan(vo0) || vo <= 0.01f || vo >= SUPPLY_V - 0.01f) return NAN;
  return ((SUPPLY_V - vo) / vo) / ((SUPPLY_V - vo0) / vo0);
}

/* --------------------------------------------------------- 0. is it sane? */

static bool sanityCheck() {
  uint16_t raw = readRaw();
  float vo = readAo();

  rule();
  Serial.println(F("CHECK  the divider, before anything else"));
  Serial.print(F("   raw ADC        ")); Serial.println(raw);
  Serial.print(F("   at the pin     ")); Serial.print(vo / DIVIDER_GAIN, 3);
  Serial.println(F(" V"));
  Serial.print(F("   at MQ-2 AO     ")); Serial.print(vo, 3);
  Serial.println(F(" V   (pin x 1.68)"));
  Serial.print(F("   supply assumed ")); Serial.print(SUPPLY_V, 1);
  Serial.println(F(" V"));
  Serial.println();

  if (raw >= 4090) {
    Serial.println(F("   FAIL: pinned at the ceiling. The divider is not built,"));
    Serial.println(F("   or GPIO 34 is on AO directly, or it is on VCC."));
    Serial.println(F("   DISCONNECT GPIO 34 NOW - on 5 V the pin is exposed."));
    return false;
  }
  if (raw <= 20) {
    Serial.println(F("   FAIL: near zero. AO is not connected, the module has no"));
    Serial.println(F("   power, or the junction is shorted to GND."));
    return false;
  }
  if (vo > SUPPLY_V + 0.2f) {
    Serial.println(F("   ODD: computed AO voltage is above the supply. Either"));
    Serial.println(F("   SUPPLY_V is wrong or the resistors are not 6.8k / 10k."));
    return false;
  }

  float vpin = vo / DIVIDER_GAIN;
  Serial.println(F("   PASS: a plausible voltage. The divider is doing its job."));
  if (vpin < 0.20f) {
    Serial.print(F("   NOTE: only ")); Serial.print(vpin * 1000, 0);
    Serial.println(F(" mV at the pin. The ESP32 ADC is at its"));
    Serial.println(F("   least linear below ~150 mV, so trust the CHANGE more"));
    Serial.println(F("   than the absolute level."));
  }
  return true;
}

/* --------------------------------------------------------------- summary */

static void summary(float now) {
  Serial.println();
  Serial.print(F("   --- "));
  Serial.print(minutes / 60);
  Serial.print(F(" h "));
  Serial.print(minutes % 60);
  Serial.print(F(" min ---   Vo "));
  Serial.print(now, 4);
  Serial.print(F(" V   since start "));
  Serial.print(now - vFirst, 4);
  Serial.print(F(" V ("));
  Serial.print(vFirst > 0 ? 100.0f * (now - vFirst) / vFirst : 0, 1);
  Serial.println(F(" %)"));
  Serial.println();
}

/* ------------------------------------------------------ clean-air baseline */

static void baseline() {
  rule();
  Serial.println(F("BASELINE  clean air. Nothing burning, no cooking, window shut."));
  double acc = 0;
  for (int i = 0; i < 30; i++) { acc += readAo(); delay(200); }
  vo0 = acc / 30.0;
  Serial.print(F("   Vo0 = ")); Serial.print(vo0, 4);
  Serial.print(F(" V   at ")); Serial.print(SUPPLY_V, 1);
  Serial.print(F(" V supply, after "));
  Serial.print(minutes / 60.0f, 1);
  Serial.println(F(" h powered"));

  if (SUPPLY_V < 4.5f) {
    Serial.println(F("   ****************************************************"));
    Serial.println(F("   DO NOT RECORD THIS - the supply is not 5 V. The heater"));
    Serial.println(F("   is at about 44% of rated power and the element is"));
    Serial.println(F("   cooler than designed. Wiring proof only."));
    Serial.println(F("   ****************************************************"));
  } else if (minutes < 24 * 60) {
    Serial.print(F("   CAUTION: only ")); Serial.print(minutes / 60.0f, 1);
    Serial.println(F(" h of burn-in. The datasheet asks for"));
    Serial.println(F("   24-48 h. Usable for a smoke test, not for a number you"));
    Serial.println(F("   intend to publish."));
  } else {
    Serial.println(F("   WRITE THIS DOWN with the date, the supply voltage and"));
    Serial.println(F("   the hours of burn-in. Every Rs/R0 is relative to it."));
  }
  rule();
  Serial.println(F("LIVE.  Rs/R0 near 1.0 = clean air, and it FALLS with gas."));
  Serial.println(F("       Real test: light a match, blow it out, hold it near."));
  Serial.println();
  Serial.println(F("    time |   raw |   AO V  |  Rs/R0  | note"));
  Serial.println(F("---------+-------+---------+---------+---------------------"));
}

/* ---------------------------------------------------------------------------- */

void setup() {
  Serial.begin(115200);
  delay(600);
  Serial.println();
  Serial.println(F("=========================================================="));
  Serial.println(F("  SAFE-Fire  -  MQ-2 burn-in"));
  Serial.print  (F("  AO via 6.8k/10k on GPIO ")); Serial.println(PIN_MQ2);
  Serial.println(F("=========================================================="));

  if (!sanityCheck()) {
    Serial.println();
    Serial.println(F("  Stopping on purpose. Fix the wiring, then reset."));
    while (true) delay(1000);
  }

  vFirst = readAo();
  startMs = millis();

  rule();
  Serial.println(F("BURN-IN  one line a minute. Leave it powered and walk away."));
  Serial.println(F("         Watch d60m: when it stops moving, the sensor has"));
  Serial.println(F("         settled and R0 is worth taking. Press m then."));
  Serial.println(F("         Closing the Serial Monitor does not stop anything."));
  Serial.println();
  Serial.println(F("   time   |   Vo V   |  raw |   d10m   |   d60m   | state"));
  Serial.println(F("----------+----------+------+----------+----------+---------"));
}

void loop() {
  /* keys work in both modes */
  if (Serial.available()) {
    char k = Serial.read();
    if (k == 'm' && !measuring) { measuring = true; baseline(); return; }
    if (k == 'b' && measuring)  { baseline(); return; }
    if (k == 's')               { summary(readAo()); return; }
  }

  if (measuring) {
    uint16_t raw = readRaw();
    float vo = readAo();
    float r = ratio(vo);
    char line[110], rField[12];
    if (isnan(r)) snprintf(rField, sizeof(rField), "    -  ");
    else          snprintf(rField, sizeof(rField), "%7.3f", r);
    snprintf(line, sizeof(line), " %6.1fs | %5u | %7.4f | %s |",
             (millis() - startMs) / 1000.0f, raw, vo, rField);
    Serial.print(line);
    if (!isnan(r)) {
      if (r < 0.35f)      Serial.print(F(" STRONG - smoke or gas"));
      else if (r < 0.65f) Serial.print(F(" clear rise"));
      else if (r < 0.85f) Serial.print(F(" slight rise"));
      else if (r > 1.20f) Serial.print(F(" cleaner than baseline (drift?)"));
    }
    Serial.println();
    delay(500);
    return;
  }

  /* ---- burn-in: one sample a minute ---- */
  float vo = readAo();
  uint16_t raw = readRaw();
  push(vo);
  minutes++;

  float d10 = ago(10), d60 = ago(60);
  char c10[12], c60[12];
  if (isnan(d10)) snprintf(c10, sizeof(c10), "    -   ");
  else            snprintf(c10, sizeof(c10), "%+8.4f", vo - d10);
  if (isnan(d60)) snprintf(c60, sizeof(c60), "    -   ");
  else            snprintf(c60, sizeof(c60), "%+8.4f", vo - d60);

  char line[120];
  snprintf(line, sizeof(line), " %3lu:%02lu    | %8.4f | %4u | %s | %s | ",
           (unsigned long)(minutes / 60), (unsigned long)(minutes % 60),
           vo, raw, c10, c60);
  Serial.print(line);

  if (isnan(d60)) {
    Serial.println(F("settling"));
  } else if (fabsf(vo - d60) < STABLE_V) {
    Serial.println(F("STABLE - press m"));
    if (!announced) {
      announced = true;
      Serial.println();
      Serial.print(F("   Drift over the last hour is under "));
      Serial.print(STABLE_V * 1000, 0);
      Serial.println(F(" mV. The sensor has settled."));
      Serial.print(F("   Total movement since power-on: "));
      Serial.print(vo - vFirst, 4);
      Serial.println(F(" V."));
      Serial.println(F("   Press m to take R0 and start measuring. If this is"));
      Serial.println(F("   still under 24 h, leaving it longer costs nothing."));
      Serial.println();
    }
  } else {
    announced = false;
    Serial.println(F("drifting"));
  }

  if (minutes % 60 == 0) summary(vo);

  delay(LOG_INTERVAL_S * 1000UL);
}
