/*  SAFE-Fire sensor node - all four channels on one ESP32
 *  =====================================================================
 *  Merges the four bring-up sketches into the thing that actually ships.
 *  Every pin, divider and threshold below was established by the
 *  individual sketches; nothing here is new wiring, only integration.
 *
 *      MQ-2       AO -> 6.8k -> GPIO 34, 10k to GND      5 V   <-- only 5 V part
 *      IR flame   AO -> GPIO 35                          3.3 V
 *      DS18B20    DQ -> GPIO 4, 4.7k to 3.3 V            3.3 V
 *      MLX90614   SDA GPIO 21, SCL GPIO 22               3.3 V
 *
 *  WHY THE LOOP NEVER BLOCKS
 *      A DS18B20 conversion takes 750 ms at 12 bits. Calling the blocking
 *      read would stall the whole node for three quarters of a second,
 *      during which a flame flicker is missed entirely. Conversion is
 *      requested, the loop keeps sampling everything else, and the result
 *      is collected when it is ready.
 *
 *  BASELINES SURVIVE A REBOOT
 *      MQ-2 needs Vo0 and MLX90614 needs its clean-scene object
 *      temperature. Re-taking them on every boot would silently rebaseline
 *      in whatever conditions happened to exist at power-up, including a
 *      room that is already smoky. They are stored in NVS and reused, with
 *      the age of the calibration reported so a stale one is visible.
 *
 *  OUTPUT
 *      One JSON line per second on the serial port, for the Jetson to read.
 *      Human-readable lines are prefixed with '#' so a parser can skip them
 *      without needing to be clever.
 *
 *  Keys:  b re-baseline (clean air, nothing hot in view)   s status
 *         c clear stored baselines                        h help
 */

#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <Preferences.h>

#define PIN_MQ2        34
#define PIN_FLAME      35
#define PIN_DS18B20     4
#define PIN_SDA        21
#define PIN_SCL        22

#define MQ2_GAIN     1.68f     // (6.8k + 10k) / 10k
#define MQ2_VCC      5.0f
#define MLX_ADDR     0x5A
#define I2C_HZ       100000L
#define AVG_N        32
#define EMIT_MS      1000
#define DS_CONV_MS   800       // 750 ms at 12 bit, plus margin

/* Alarm thresholds. The gas and thermal figures come from the measured
 * noise floors, not from round numbers: MQ-2 classifies a rise below 0.85
 * of baseline, and the MLX90614 noise floor was sigma = 0.163 C on this
 * rig, so 3 sigma is 0.49 C and a 2 C rise is a wide margin above it. */
#define GAS_RISE_ALARM   0.85f
#define SURF_RISE_ALARM  2.00f

/* The flame module's analogue output FALLS when it sees infrared. It rests near
 * the top of the range with no flame, which is why 2990 mV in a quiet room is
 * the correct idle reading and not a fault. Established in measure_flame.ino,
 * which reports the direction it measured rather than assuming one.
 *
 * Writing this threshold as a rise would leave the channel permanently silent:
 * the value can only go down, so a comparison against a rise never fires. */
#define FLAME_DROP_MV    150

OneWire oneWire(PIN_DS18B20);
DallasTemperature ds(&oneWire);
Preferences prefs;

static float    vo0 = NAN, objBase = NAN;
static uint32_t baseEpoch = 0;
static float    ambientC = NAN, surfaceC = NAN, mlxAmbC = NAN;
static float    gasRatio = NAN;
static uint16_t flameMv = 0, flameBaseMv = 0;
static bool     okDs = false, okMlx = false, okMq2 = false, okFlame = false;
static uint32_t dsAskedAt = 0;
static bool     dsPending = false;
static uint32_t lastEmit = 0;

/* ------------------------------------------------------------ MLX90614 */

static uint8_t crc8(const uint8_t *d, uint8_t n) {
  uint8_t c = 0;
  while (n--) {
    c ^= *d++;
    for (uint8_t i = 0; i < 8; i++)
      c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
  }
  return c;
}

/* Returns false on a bus fault OR a bad checksum. The checksum matters:
 * without it a loose wire is read as a temperature, which is how the
 * DS18B20 bring-up went wrong twice. */
static bool mlxRead(uint8_t reg, float *out) {
  Wire.beginTransmission(MLX_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MLX_ADDR, 3) != 3) return false;
  uint8_t lo = Wire.read(), hi = Wire.read(), pec = Wire.read();
  uint8_t buf[5] = { (uint8_t)(MLX_ADDR << 1), reg,
                     (uint8_t)((MLX_ADDR << 1) | 1), lo, hi };
  if (crc8(buf, 5) != pec) return false;
  uint16_t v = ((uint16_t)hi << 8) | lo;
  if (v & 0x8000) return false;
  *out = v * 0.02f - 273.15f;
  return true;
}

/* --------------------------------------------------------------- MQ-2 */

static float mq2Volts() {
  uint32_t acc = 0;
  for (int i = 0; i < AVG_N; i++) { acc += analogReadMilliVolts(PIN_MQ2); delayMicroseconds(200); }
  return (acc / (float)AVG_N) / 1000.0f * MQ2_GAIN;
}

/* Rs/R0 with the module's load resistor cancelled out. RL is not printed
 * on the board and differs between makers, so it is eliminated rather than
 * guessed:  Rs/R0 = [(Vc-Vo)/Vo] * [Vo0/(Vc-Vo0)] */
static float mq2Ratio(float vo) {
  if (isnan(vo0) || vo <= 0.01f || vo >= MQ2_VCC - 0.01f) return NAN;
  return ((MQ2_VCC - vo) / vo) / ((MQ2_VCC - vo0) / vo0);
}

static uint16_t flameMillivolts() {
  uint32_t acc = 0;
  for (int i = 0; i < AVG_N; i++) { acc += analogReadMilliVolts(PIN_FLAME); delayMicroseconds(200); }
  return acc / AVG_N;
}

/* ------------------------------------------------- flame windowing
 *
 * With a lighter held near the node, the one-second reading alternated between
 * 231 mV and 2740 mV and the level fell back to NORMAL while the flame was
 * still burning. The cause was observed at the bench and is physical: room
 * airflow pushes the flame out of this module's narrow field of view and back
 * in. 2740 mV is the full idle value, not an intermediate one, which is what
 * losing sight of the source looks like rather than a sampling artefact.
 *
 * The MLX90614 in the same window stayed elevated between +0.4 and +3.6 C
 * without ever returning to baseline. Two channels watching one flame, and only
 * the narrow-field one loses it. That difference is field of view, and it is
 * worth recording.
 *
 * So the window is sampled continuously and reduced two ways:
 *
 *   minimum  - the detector. Any dip inside the window counts, because a flame
 *              that was briefly blown out of view is still a flame.
 *   dips     - how many times the source ENTERED view during the window. It was
 *              intended as a flicker discriminator and it is not one: measured
 *              with a lighter, the drop is 2500 mV against a 150 mV threshold, so
 *              flicker never comes close to crossing back and dips reads 0 for a
 *              steadily held flame. Kept because entry and exit events are useful,
 *              but it does not separate a flame from a steady source.
 *   p2p      - the actual flicker measure: peak to peak inside the window. A
 *              steady infrared source, sunlight on a wall or a hot lamp, holds the
 *              output at a level and gives a small p2p. A flame moves.
 */
static uint16_t winMin = 0xFFFF;
static uint16_t winMax = 0;
static uint16_t winDips = 0;
static bool     winBelow = false;
static uint16_t flameMinMv = 0;
static uint16_t flameDips = 0;
static uint16_t flameP2p = 0;

static void flameSample() {
  uint32_t acc = 0;
  for (int i = 0; i < 8; i++) { acc += analogReadMilliVolts(PIN_FLAME); delayMicroseconds(100); }
  uint16_t mv = acc / 8;
  flameMv = mv;
  if (mv < winMin) winMin = mv;
  if (mv > winMax) winMax = mv;
  if (flameBaseMv) {
    bool below = ((int)flameBaseMv - (int)mv) > FLAME_DROP_MV;
    if (below && !winBelow) winDips++;      // count crossings, not samples
    winBelow = below;
  }
}

static void flameCloseWindow() {
  flameMinMv = (winMin == 0xFFFF) ? flameMv : winMin;
  flameP2p = (winMax > winMin && winMin != 0xFFFF) ? (winMax - winMin) : 0;
  flameDips = winDips;
  winMin = 0xFFFF; winMax = 0; winDips = 0;
}

/* ------------------------------------------------------------ baseline */

static void saveBaselines() {
  prefs.begin("safefire", false);
  prefs.putFloat("vo0", vo0);
  prefs.putFloat("objBase", objBase);
  prefs.putUShort("flameBase", flameBaseMv);
  prefs.putUInt("epoch", baseEpoch);
  prefs.end();
}

static void loadBaselines() {
  prefs.begin("safefire", true);
  vo0        = prefs.getFloat("vo0", NAN);
  objBase    = prefs.getFloat("objBase", NAN);
  flameBaseMv = prefs.getUShort("flameBase", 0);
  baseEpoch  = prefs.getUInt("epoch", 0);
  prefs.end();
}

static void takeBaselines() {
  Serial.println(F("# BASELINE  clean air, nothing hot in the field. 6 s."));
  double sv = 0, so = 0, sf = 0;
  int nv = 0, no = 0, nf = 0;
  for (int i = 0; i < 30; i++) {
    float v = mq2Volts();
    if (v > 0.01f) { sv += v; nv++; }
    float o;
    if (mlxRead(0x07, &o)) { so += o; no++; }
    sf += flameMillivolts(); nf++;
    delay(200);
  }
  if (nv) vo0 = sv / nv;
  if (no >= 20) objBase = so / no;
  if (nf) flameBaseMv = (uint16_t)(sf / nf);
  baseEpoch = millis() / 1000;
  saveBaselines();
  Serial.print(F("# vo0 "));      Serial.print(vo0, 4);
  Serial.print(F(" V   objBase ")); Serial.print(objBase, 2);
  Serial.print(F(" C   flameBase ")); Serial.print(flameBaseMv);
  Serial.println(F(" mV   saved to NVS"));
  if (no < 20) Serial.println(F("# WARNING: MLX90614 gave too few clean reads"));
}

/* ------------------------------------------------------------- decision
 *
 * The node never declares an alarm. It reports WATCH when its own channels
 * are elevated and lets the Jetson fuse. That is the asymmetric policy from
 * the thesis: sensors may raise the level, never suppress a camera alarm,
 * because a fire far from the node must still alarm.
 */
static const char *nodeLevel() {
  bool gas   = okMq2  && !isnan(gasRatio) && gasRatio < GAS_RISE_ALARM;
  bool therm = okMlx  && !isnan(surfaceC) && !isnan(objBase)
                      && (surfaceC - objBase) > SURF_RISE_ALARM;
  bool ir    = okFlame && flameBaseMv
                      && (int)flameBaseMv - (int)flameMinMv > FLAME_DROP_MV;
  int n = (gas ? 1 : 0) + (therm ? 1 : 0) + (ir ? 1 : 0);
  if (n == 0) return "NORMAL";
  return "WATCH";
}

/* ---------------------------------------------------------------- emit */

/* Two output modes on purpose.
 *
 * A human at the bench cannot read a JSON line per second, and the Jetson cannot
 * parse an aligned table. So the node prints the table by default and switches to
 * JSON when something asks it to with 'j'. The Jetson sends that on connect.
 *
 * A value with no baseline prints as "----", never as 0. Printing zero for
 * "unknown" is what made the first run look like a dead gas channel when the
 * only thing missing was a baseline. */
static bool jsonMode = false;
static uint8_t rowsSinceHeader = 250;

static void humanHeader() {
  Serial.println();
  Serial.println(F("    time |  air C | surf C |  dSurf | Rs/R0 | gas % | flame mV |  drop |  p2p | level"));
  Serial.println(F("---------+--------+--------+--------+-------+-------+----------+-------+------+--------"));
  rowsSinceHeader = 0;
}

static void emitHuman() {
  if (rowsSinceHeader >= 20) humanHeader();
  rowsSinceHeader++;

  char line[160], c1[9], c2[9], c3[9], c4[8], c5[8], c6[8];
  if (okDs && !isnan(ambientC)) snprintf(c1, sizeof(c1), "%6.2f", ambientC);
  else                          snprintf(c1, sizeof(c1), "  ----");
  if (okMlx && !isnan(surfaceC)) snprintf(c2, sizeof(c2), "%6.2f", surfaceC);
  else                           snprintf(c2, sizeof(c2), "  ----");
  if (okMlx && !isnan(surfaceC) && !isnan(objBase))
       snprintf(c3, sizeof(c3), "%+6.2f", surfaceC - objBase);
  else snprintf(c3, sizeof(c3), "  ----");
  if (okMq2 && !isnan(gasRatio)) snprintf(c4, sizeof(c4), "%5.3f", gasRatio);
  else                           snprintf(c4, sizeof(c4), " ----");
  if (okMq2 && !isnan(gasRatio)) snprintf(c5, sizeof(c5), "%5.1f", 100.0f * (1.0f - gasRatio));
  else                           snprintf(c5, sizeof(c5), " ----");
  if (okFlame && flameBaseMv) snprintf(c6, sizeof(c6), "%5d", (int)flameBaseMv - (int)flameMinMv);
  else                        snprintf(c6, sizeof(c6), " ----");

  snprintf(line, sizeof(line), " %6.1fs | %s | %s | %s | %s | %s | %8u | %s | %4u | %s",
           millis() / 1000.0f, c1, c2, c3, c4, c5,
           (unsigned)flameMinMv, c6, (unsigned)flameP2p, nodeLevel());
  Serial.print(line);

  if (isnan(vo0) || isnan(objBase)) Serial.print(F("   <- press b, no baseline"));
  else if (!okDs || !okMlx || !okMq2 || !okFlame) Serial.print(F("   <- a channel is down, press s"));
  Serial.println();
}

static void emitJson() {
  /* gasPpm is deliberately -1. The MQ-2 datasheet defines R0 as the
   * resistance in 1000 ppm LPG, while our Vo0 is taken in clean air, so the
   * published ppm curves do not apply to this ratio. Emitting a number
   * anyway would be a fabricated unit. gasRatio is the real measurement and
   * gasRisePct is the readable form of it. */
  /* null, not 0, for anything without a baseline or a healthy channel. A
   * consumer can tell "unknown" from "measured zero"; it cannot if both are 0. */
  Serial.print(F("{\"t\":"));            Serial.print(millis());
  Serial.print(F(",\"ambientC\":"));
  if (okDs && !isnan(ambientC)) Serial.print(ambientC, 2); else Serial.print(F("null"));
  Serial.print(F(",\"surfaceC\":"));
  if (okMlx && !isnan(surfaceC)) Serial.print(surfaceC, 2); else Serial.print(F("null"));
  Serial.print(F(",\"surfaceRiseC\":"));
  if (okMlx && !isnan(surfaceC) && !isnan(objBase)) Serial.print(surfaceC - objBase, 2);
  else Serial.print(F("null"));
  Serial.print(F(",\"gasRatio\":"));
  if (okMq2 && !isnan(gasRatio)) Serial.print(gasRatio, 4); else Serial.print(F("null"));
  Serial.print(F(",\"gasRisePct\":"));
  if (okMq2 && !isnan(gasRatio)) Serial.print(100.0f * (1.0f - gasRatio), 1);
  else Serial.print(F("null"));
  Serial.print(F(",\"gasPpm\":null"));
  /* flameIr is normalised 0..1 with 1 meaning strong infrared, because that is
   * what the app's gauge expects. The sensor moves the other way, so the sign is
   * flipped here rather than in the app. */
  float irNorm = flameBaseMv
      ? constrain((float)((int)flameBaseMv - (int)flameMinMv) / 1000.0f, 0.0f, 1.0f)
      : 0.0f;
  Serial.print(F(",\"flameMv\":"));      Serial.print(flameMv);
  Serial.print(F(",\"flameMinMv\":"));   Serial.print(flameMinMv);
  Serial.print(F(",\"flameDips\":"));    Serial.print(flameDips);
  Serial.print(F(",\"flameP2pMv\":"));   Serial.print(flameP2p);
  Serial.print(F(",\"flameDropMv\":")); Serial.print(flameBaseMv ?
      (int)flameBaseMv - (int)flameMinMv : 0);
  Serial.print(F(",\"flameIr\":"));      Serial.print(irNorm, 3);
  Serial.print(F(",\"level\":\""));      Serial.print(nodeLevel());
  Serial.print(F("\",\"ok\":{\"ds\":")); Serial.print(okDs ? 1 : 0);
  Serial.print(F(",\"mlx\":"));          Serial.print(okMlx ? 1 : 0);
  Serial.print(F(",\"mq2\":"));          Serial.print(okMq2 ? 1 : 0);
  Serial.print(F(",\"flame\":"));        Serial.print(okFlame ? 1 : 0);
  Serial.print(F("},\"calAgeS\":"));     Serial.print(baseEpoch ? (millis() / 1000 - baseEpoch) : 0);
  Serial.println(F("}"));
}

/* ---------------------------------------------------------- boot check
 *
 * Names which channel failed, at the moment power is applied, before any
 * measurement is attempted. Four sensors were wired one at a time for exactly
 * this reason: a single "sensor error" line would send you looking at all four.
 */
static void bootCheck() {
  Serial.println(F("# --------------------------------------------------"));
  Serial.println(F("# BOOT CHECK"));

  int n = ds.getDeviceCount();
  ds.requestTemperatures();
  delay(DS_CONV_MS);
  float t = ds.getTempCByIndex(0);
  okDs = (n > 0 && t > -100.0f && t < 120.0f);
  Serial.print(F("#  DS18B20  GPIO 4    "));
  if (okDs) { Serial.print(F("PASS   ")); Serial.print(t, 2); Serial.println(F(" C")); }
  else if (n == 0) Serial.println(F("FAIL   no device. 4.7k pull-up to 3.3 V missing, or S and middle swapped."));
  else             Serial.println(F("FAIL   device seen but reading is -127. Check the pull-up."));

  Wire.beginTransmission(MLX_ADDR);
  bool addr = (Wire.endTransmission() == 0);
  float o = NAN;
  okMlx = addr && mlxRead(0x07, &o);
  Serial.print(F("#  MLX90614 21/22    "));
  if (okMlx) { Serial.print(F("PASS   ")); Serial.print(o, 2); Serial.println(F(" C object")); }
  else if (!addr) Serial.println(F("FAIL   nothing at 0x5A. SDA/SCL swapped, no 3.3 V, or ground open."));
  else            Serial.println(F("FAIL   answers but the checksum is bad. Reseat SDA and SCL."));

  uint16_t fmv = flameMillivolts();
  okFlame = (fmv > 0 && fmv < 3200);
  Serial.print(F("#  IR flame GPIO 35   "));
  if (okFlame) { Serial.print(F("PASS   ")); Serial.print(fmv); Serial.println(F(" mV")); }
  else Serial.println(F("FAIL   pinned or dead. Pin order is AO / G / + / DO, supply is THIRD."));

  float v = mq2Volts();
  okMq2 = (v > 0.02f && v < MQ2_VCC);
  Serial.print(F("#  MQ-2    GPIO 34   "));
  if (okMq2) {
    Serial.print(F("PASS   ")); Serial.print(v, 4);
    Serial.print(F(" V at AO, ")); Serial.print(v / MQ2_GAIN, 3);
    Serial.println(F(" V at the pin"));
  } else if (v <= 0.02f) {
    Serial.println(F("FAIL   near zero. AO open, no 5 V, or the divider node is shorted to GND."));
  } else {
    Serial.println(F("FAIL   at the ceiling. Divider not built, or GPIO 34 is on AO directly."));
    Serial.println(F("#           DISCONNECT GPIO 34 NOW - on 5 V that pin is exposed."));
  }

  int pass = (okDs ? 1 : 0) + (okMlx ? 1 : 0) + (okFlame ? 1 : 0) + (okMq2 ? 1 : 0);
  Serial.print(F("#  ")); Serial.print(pass); Serial.println(F(" / 4 channels alive"));
  if (pass < 4)
    Serial.println(F("#  Fix the failing channel before trusting anything below."));
  Serial.println(F("# --------------------------------------------------"));
}

static void status() {
  Serial.println(F("# --------------------------------------------------"));
  Serial.print(F("# DS18B20  ")); Serial.print(okDs ? F("ok  ") : F("FAIL"));
  Serial.print(F("  ambient ")); Serial.print(ambientC, 2); Serial.println(F(" C"));
  Serial.print(F("# MLX90614 ")); Serial.print(okMlx ? F("ok  ") : F("FAIL"));
  Serial.print(F("  surface ")); Serial.print(surfaceC, 2);
  Serial.print(F(" C   base ")); Serial.print(objBase, 2); Serial.println(F(" C"));
  Serial.print(F("# MQ-2     ")); Serial.print(okMq2 ? F("ok  ") : F("FAIL"));
  Serial.print(F("  Rs/R0 ")); Serial.print(gasRatio, 3);
  Serial.print(F("   Vo0 ")); Serial.print(vo0, 4); Serial.println(F(" V"));
  Serial.print(F("# flame    ")); Serial.print(okFlame ? F("ok  ") : F("FAIL"));
  Serial.print(F("  now ")); Serial.print(flameMv);
  Serial.print(F(" mV   window min ")); Serial.print(flameMinMv);
  Serial.print(F(" mV   base ")); Serial.print(flameBaseMv);
  Serial.print(F(" mV   p2p ")); Serial.print(flameP2p);
  Serial.print(F(" mV   entries ")); Serial.println(flameDips);
  Serial.print(F("# level    ")); Serial.println(nodeLevel());
  Serial.println(F("# --------------------------------------------------"));
}

/* ---------------------------------------------------------------------- */

void setup() {
  Serial.begin(115200);
  delay(600);
  Serial.println();
  Serial.println(F("# =================================================="));
  Serial.println(F("#  SAFE-Fire sensor node"));
  Serial.println(F("#  MQ-2 34 | flame 35 | DS18B20 4 | MLX 21/22"));
  Serial.println(F("# =================================================="));

  analogSetPinAttenuation(PIN_MQ2, ADC_11db);
  analogSetPinAttenuation(PIN_FLAME, ADC_11db);

  ds.begin();
  ds.setResolution(12);
  Wire.begin(PIN_SDA, PIN_SCL, I2C_HZ);

  /* The boot check is allowed to block, because nothing is being watched yet
   * and naming the broken channel is worth 800 ms. Async mode is enabled only
   * afterwards, for the loop that has to keep up with a flame flicker. */
  bootCheck();
  ds.setWaitForConversion(false);

  loadBaselines();
  if (isnan(vo0) || isnan(objBase)) {
    Serial.println(F("# no stored baselines. Press b in clean air."));
  } else {
    Serial.print(F("# baselines restored from NVS: vo0 "));
    Serial.print(vo0, 4); Serial.print(F(" V   objBase "));
    Serial.print(objBase, 2); Serial.println(F(" C"));
  }
  Serial.println(F("# human table by default. j switches to JSON for the Jetson."));
  Serial.println(F("# b baseline | s status | j json/table | c clear | h help"));

  ds.requestTemperatures();
  dsAskedAt = millis();
  dsPending = true;
}

void loop() {
  if (Serial.available()) {
    char k = Serial.read();
    if (k == 'b') { takeBaselines(); return; }
    if (k == 's') { status(); return; }
    if (k == 'c') {
      prefs.begin("safefire", false); prefs.clear(); prefs.end();
      vo0 = objBase = NAN; flameBaseMv = 0; baseEpoch = 0;
      Serial.println(F("# baselines cleared"));
      return;
    }
    if (k == 'j') {
      jsonMode = !jsonMode;
      Serial.print(F("# output mode: "));
      Serial.println(jsonMode ? F("JSON, one line per second")
                              : F("human table"));
      if (!jsonMode) rowsSinceHeader = 250;
      return;
    }
    if (k == 'h') {
      Serial.println(F("# b baseline | s status | j json/table | c clear | h help"));
      return;
    }
  }

  /* DS18B20, collected only when the conversion has had time to finish */
  if (dsPending && millis() - dsAskedAt >= DS_CONV_MS) {
    float t = ds.getTempCByIndex(0);
    okDs = (t > -100.0f && t < 120.0f);
    if (okDs) ambientC = t;
    ds.requestTemperatures();
    dsAskedAt = millis();
  }

  float o;
  okMlx = mlxRead(0x07, &o);
  if (okMlx) surfaceC = o;
  float a;
  if (mlxRead(0x06, &a)) mlxAmbC = a;

  float v = mq2Volts();
  okMq2 = (v > 0.02f && v < MQ2_VCC);
  if (okMq2) gasRatio = mq2Ratio(v);

  flameSample();
  okFlame = (flameMv > 0);

  if (millis() - lastEmit >= EMIT_MS) {
    lastEmit = millis();
    flameCloseWindow();
    if (jsonMode) emitJson(); else emitHuman();
  }
  delay(5);
}
