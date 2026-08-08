/*  SAFE-Fire - MLX90614ESF-BAA on a GY-906 breakout
 *  ---------------------------------------------------------------
 *  VIN -> 3.3 V     GND -> GND     SDA -> GPIO 21     SCL -> GPIO 22
 *
 *  THE PART IS CONFIRMED: MLX90614ESF-BAA.
 *      The trailing B is the 3 V die. 5 V damages it. There is no
 *      regulator on this breakout, so VIN goes straight to the sensor
 *      and 3.3 V is the only correct supply - not a cautious choice.
 *      Single zone, so RAM 0x07 is the only object register that means
 *      anything. Factory range: object -70..+380 C, ambient -40..+125 C.
 *
 *  THE PULL-UP QUESTION, SETTLED BY MEASUREMENT
 *      The listing says "10k pull up resistors ... with optional solder
 *      jumpers ... may or may not need to be soldered". That is the same
 *      ambiguity that cost two rounds on the KY-001, whose documented
 *      pull-up did not exist. So this sketch does not assume: it scans
 *      TWICE.
 *          pass 1 - ESP32 internal pull-ups DISABLED. Anything that
 *                   answers is answering through the BOARD's resistors.
 *          pass 2 - internal pull-ups enabled (~45k, weak).
 *      Answering in pass 1 proves the board's pull-ups are connected.
 *      Answering only in pass 2 proves they are not, and the jumpers
 *      need bridging or external 4.7k adding. Silence in both is wiring.
 *      No meter required, and no belief required either.
 *
 *  NO LIBRARY ON PURPOSE
 *      Three modules in this project contradicted their own published
 *      documentation. A library reports "read error" and stops there;
 *      raw Wire code can say WHICH step failed - addressing, the
 *      repeated start, the byte count, or the checksum.
 *
 *  THE CHECKSUM IS THE POINT
 *      Every SMBus read returns a PEC byte: CRC-8 over
 *          [addr<<1, reg, addr<<1|1, lo, hi]
 *      Verifying it separates "the sensor says 23.4 C" from "the bus
 *      handed me bytes that happen to decode to 23.4 C". Without it a
 *      loose wire reads as a temperature - which is exactly how the
 *      DS18B20 bring-up went wrong.
 *
 *  Keys:  r rescan   i identify   b baseline   s summary
 *         l / c / p / x  stamp a labelled marker into the log
 *                        (lighter / candle / paper / other)
 *
 *  WHY THE MARKER KEYS EXIST
 *      The whole point of the source comparison is that the lighter may
 *      produce almost NO signal - a clean blue flame radiates around
 *      4.3 um, outside this sensor's 5.5-14 um window. If that happens
 *      the log has nine trials and only six visible excursions, and a
 *      real null becomes indistinguishable from a trial that was never
 *      run. Stamping the log makes the absence itself a datum.
 */

#include <Wire.h>
#include "driver/gpio.h"

#define PIN_SDA        21
#define PIN_SCL        22
#define ADDR         0x5A      // factory default
#define I2C_HZ      100000L    // SMBus part; 100 kHz is its home

#define RAM_TA        0x06     // ambient - the chip's own die
#define RAM_TOBJ1     0x07     // object - what the field of view sees
#define EE_EMISSIVITY 0x24     // EEPROM 0x04, read as 0x20|0x04
#define EE_ADDRESS    0x2E     // EEPROM 0x0E

#define OBJ_MAX      380.0f    // datasheet ceiling; above this the reading is meaningless

/* Measured on this rig, not assumed: 249 samples over 124.5 s aimed at a wooden
 * door at 1.1 m with the air conditioning running gave sigma = 0.163 C and a
 * two-minute drift of 0.008 C. 3 sigma is therefore the smallest dObj worth
 * believing. Re-measure and change this if the mounting or the scene changes. */
#define NOISE_3SIG     0.49f

/* dAmb is the temperature of the sensor's OWN die, and the internal object
 * compensation is built on it. If it moves, the sensor itself is heating and
 * the object reading is no longer about the scene - so the trial is void, not
 * merely noisy. This is why a flame must never come closer than ~15 cm. */
#define AMB_VOID       0.50f

static float    baseObj = NAN, baseAmb = NAN;
static uint32_t startMs;
static bool     boardPullups = false;
static bool     ambVoided = false;   // a trial that drifted must not pass silently
static float    noise3sig = NOISE_3SIG;   // replaced by the n key, per site

/* ------------------------------------------------------------------ helpers */

static void rule() {
  Serial.println(F("----------------------------------------------------------"));
}

static void internalPullups(bool on) {
  if (on) {
    gpio_pullup_en((gpio_num_t)PIN_SDA);
    gpio_pullup_en((gpio_num_t)PIN_SCL);
  } else {
    gpio_pullup_dis((gpio_num_t)PIN_SDA);
    gpio_pullup_dis((gpio_num_t)PIN_SCL);
  }
  delay(5);
}

static uint8_t crc8(const uint8_t *d, uint8_t n) {
  uint8_t c = 0;
  while (n--) {
    c ^= *d++;
    for (uint8_t i = 0; i < 8; i++)
      c = (c & 0x80) ? (uint8_t)((c << 1) ^ 0x07) : (uint8_t)(c << 1);
  }
  return c;
}

/* 0 on success, or a step code, so a failure names its own cause. */
static int readReg(uint8_t reg, uint16_t *val, bool *pecOk) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return 1;      // no ACK on the address
  if (Wire.requestFrom((int)ADDR, 3) != 3)  return 2;  // short read
  uint8_t lo = Wire.read(), hi = Wire.read(), pec = Wire.read();
  uint8_t buf[5] = { (uint8_t)(ADDR << 1), reg, (uint8_t)((ADDR << 1) | 1), lo, hi };
  *pecOk = (crc8(buf, 5) == pec);
  *val = ((uint16_t)hi << 8) | lo;
  return 0;
}

/* raw * 0.02 K, minus absolute zero. Bit 15 set = the chip flagging an error. */
static bool degC(uint8_t reg, float *out, bool *pecOk) {
  uint16_t v;
  if (readReg(reg, &v, pecOk) != 0) return false;
  if (v & 0x8000) return false;
  *out = v * 0.02f - 273.15f;
  return true;
}

static bool present() {
  Wire.beginTransmission(ADDR);
  return Wire.endTransmission() == 0;
}

/* ------------------------------------------------------- bus health check
 *
 * Run BEFORE Wire.begin(), so it cannot hang. I2C is open-drain: both lines
 * idle HIGH through their pull-ups, and any device pulls them LOW to talk.
 * So reading them as plain inputs with the ESP32's own pull-ups on is a
 * continuity test that needs no meter:
 *
 *     both HIGH  - the lines are free, it is safe to start the bus
 *     one LOW    - that line is shorted to ground, or a part is holding it
 *
 * Without this, a line shorted to GND makes every Wire transaction wait for
 * its timeout - 126 addresses x 2 passes of apparent silence, which reads
 * exactly like "the sketch prints nothing".
 */
static bool busHealth() {
  pinMode(PIN_SDA, INPUT_PULLUP);
  pinMode(PIN_SCL, INPUT_PULLUP);
  delay(10);
  int sda = digitalRead(PIN_SDA), scl = digitalRead(PIN_SCL);
  rule();
  Serial.println(F("BUS CHECK  idle levels, before starting I2C"));
  Serial.print(F("   SDA (GPIO ")); Serial.print(PIN_SDA);
  Serial.print(F(")  ")); Serial.println(sda ? F("HIGH  ok") : F("LOW   <-- STUCK"));
  Serial.print(F("   SCL (GPIO ")); Serial.print(PIN_SCL);
  Serial.print(F(")  ")); Serial.println(scl ? F("HIGH  ok") : F("LOW   <-- STUCK"));
  Serial.println();
  if (sda && scl) {
    Serial.println(F("   PASS: both lines idle high. Starting the bus."));
    return true;
  }
  Serial.println(F("   FAIL: a line is held low. Do NOT start the bus - every"));
  Serial.println(F("   transaction would sit waiting for a timeout."));
  Serial.println(F("     - that wire shorted to GND, or in the wrong rail"));
  Serial.println(F("     - a solder bridge between two pads on the breakout"));
  Serial.println(F("     - the module wired backwards, pulling the line down"));
  return false;
}

/* --------------------------------------------------------------- bus scan */

static int listBus() {
  int found = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print(F("     0x"));
      if (a < 16) Serial.print('0');
      Serial.print(a, HEX);
      if (a == ADDR) Serial.print(F("   <- MLX90614"));
      Serial.println();
      found++;
    }
  }
  return found;
}

static bool scan() {
  rule();
  Serial.println(F("SCAN  twice, to settle the pull-up question by measurement"));
  Serial.println();

  Serial.println(F("   pass 1 - ESP32 internal pull-ups OFF"));
  Serial.println(F("            anything answering here is using the BOARD's 10k"));
  internalPullups(false);
  int n1 = listBus();
  bool ok1 = present();
  Serial.print(F("     ")); Serial.print(n1); Serial.println(F(" device(s)"));
  Serial.println();

  Serial.println(F("   pass 2 - internal pull-ups ON (~45k, weak)"));
  internalPullups(true);
  int n2 = listBus();
  bool ok2 = present();
  Serial.print(F("     ")); Serial.print(n2); Serial.println(F(" device(s)"));
  Serial.println();

  boardPullups = ok1;

  if (ok1) {
    Serial.println(F("   PASS. 0x5A answered without any help from the ESP32, so"));
    Serial.println(F("   the board's 10k pull-ups ARE connected. Do not solder the"));
    Serial.println(F("   jumpers. Do not add external resistors. Leaving the weak"));
    Serial.println(F("   internal ones on alongside them is harmless."));
    return true;
  }
  if (ok2) {
    Serial.println(F("   PARTIAL. 0x5A answered only with the ESP32's weak internal"));
    Serial.println(F("   pull-ups, so the board's 10k are NOT in circuit - the solder"));
    Serial.println(F("   jumpers are open. It may work now and fail intermittently."));
    Serial.println(F("   FIX IT: bridge the two solder jumpers on the breakout, OR"));
    Serial.println(F("   add 4.7k from SDA to 3.3V and 4.7k from SCL to 3.3V."));
    Serial.println(F("   Then rescan with r - it must pass on pass 1."));
    return true;
  }
  if (n1 == 0 && n2 == 0) {
    Serial.println(F("   FAIL: nothing on the bus at all. In order of likelihood:"));
    Serial.println(F("     1. a solder joint is not joined - reflow all four"));
    Serial.println(F("     2. SDA and SCL swapped   (SDA=21, SCL=22)"));
    Serial.println(F("     3. GND not actually on the ground rail"));
    Serial.println(F("     4. no 3.3 V at VIN"));
  } else {
    Serial.println(F("   FAIL: the bus works - something else replied - but 0x5A"));
    Serial.println(F("   does not. SDA, SCL and GND are therefore fine. Either the"));
    Serial.println(F("   part was re-addressed in EEPROM, or it is damaged."));
  }
  return false;
}

/* ------------------------------------------------------------- identify */

static void identify() {
  rule();
  Serial.println(F("IDENTIFY  read EEPROM, to prove this really is an MLX90614"));
  uint16_t v; bool pec;
  if (readReg(EE_EMISSIVITY, &v, &pec) == 0) {
    Serial.print(F("   emissivity   ")); Serial.print(v / 65535.0f, 3);
    Serial.print(F("   (raw 0x")); Serial.print(v, HEX);
    Serial.print(F(", PEC ")); Serial.print(pec ? F("ok") : F("BAD"));
    Serial.println(F(")"));
    Serial.println(F("   factory default is 1.000. LEAVE IT - the thesis reports a"));
    Serial.println(F("   RELATIVE rise, and emissivity cancels in a difference."));
  } else {
    Serial.println(F("   could not read emissivity"));
  }
  if (readReg(EE_ADDRESS, &v, &pec) == 0) {
    Serial.print(F("   SMBus addr   0x")); Serial.print(v & 0xFF, HEX);
    Serial.print(F("   (PEC ")); Serial.print(pec ? F("ok") : F("BAD"));
    Serial.println(F(")"));
  }
  Serial.print(F("   board pull-ups in circuit: "));
  Serial.println(boardPullups ? F("yes") : F("NO - see the scan"));
  Serial.println();
}

/* ---------------------------------------------------------- noise floor
 *
 * Measures the scene's own restlessness for two minutes and sets the
 * detection threshold from it. Run this ONCE per site, before any trial.
 *
 * WHY IT HAS TO BE MEASURED AND NOT ASSUMED
 *     3 sigma = 0.49 C was measured indoors on a wooden door at 1.1 m with
 *     the air conditioning holding the room still. Outdoors - sun on
 *     surfaces, wind moving things through the field, a hot wall cooling
 *     after sunset - sigma can be several times larger. Carrying the indoor
 *     number outside would turn scene wander into "detections". The
 *     threshold has to belong to the scene it is used in.
 *
 * It also replaces the 30-sample baseline with the mean of 240 samples,
 * which is a better reference than b gives, and reports the drift and the
 * die-temperature excursion so an unusable site announces itself.
 */
static void noiseFloor() {
  const int   N = 240;              // 120 s at 0.5 s
  const float DT = 0.5f;
  rule();
  Serial.println(F("NOISE FLOOR  120 s. Aim it, then WALK AWAY and touch nothing."));
  Serial.println(F("             Stand outside the 90 degree cone."));
  Serial.println();

  double so = 0, sa = 0, sq = 0, firstHalf = 0, secondHalf = 0;
  float  lo = 1e9, hi = -1e9, ampLo = 1e9, ampHi = -1e9, ref = NAN;
  int    n = 0, bad = 0;

  for (int i = 0; i < N; i++) {
    float o, a; bool po, pa;
    if (degC(RAM_TOBJ1, &o, &po) && degC(RAM_TA, &a, &pa) && po && pa) {
      if (isnan(ref)) ref = o;      // subtract an offset so the sum of squares
      float d = o - ref;            // keeps its precision at these magnitudes
      so += d; sq += (double)d * d; sa += a;
      if (o < lo) lo = o;
      if (o > hi) hi = o;
      if (a < ampLo) ampLo = a;
      if (a > ampHi) ampHi = a;
      if (i < N / 2) firstHalf += d; else secondHalf += d;
      n++;
    } else bad++;
    if ((i + 1) % 40 == 0) { Serial.print(F("   ")); Serial.print((i + 1) * DT, 0); Serial.println(F(" s")); }
    delay((int)(DT * 1000));
  }

  if (n < N * 3 / 4) {
    Serial.print(F("   ABORT: only ")); Serial.print(n);
    Serial.print(F("/")); Serial.print(N);
    Serial.println(F(" clean reads. Fix the bus before measuring anything."));
    return;
  }

  float mean = so / n;
  float var  = (float)(sq / n) - mean * mean;
  float sd   = var > 0 ? sqrtf(var) : 0.0f;
  float drift = (float)(secondHalf / (n / 2) - firstHalf / (n / 2));

  baseObj = ref + mean;
  baseAmb = sa / n;
  noise3sig = 3.0f * sd;
  ambVoided = false;

  Serial.println();
  Serial.print(F("   samples        ")); Serial.print(n);
  if (bad) { Serial.print(F("   (")); Serial.print(bad); Serial.print(F(" rejected)")); }
  Serial.println();
  Serial.print(F("   baseline obj   ")); Serial.print(baseObj, 2); Serial.println(F(" C"));
  Serial.print(F("   baseline amb   ")); Serial.print(baseAmb, 2); Serial.println(F(" C"));
  Serial.print(F("   sigma          ")); Serial.print(sd, 3);   Serial.println(F(" C"));
  Serial.print(F("   range          ")); Serial.print(hi - lo, 2); Serial.println(F(" C peak to peak"));
  Serial.print(F("   drift 120 s    ")); Serial.print(drift, 3); Serial.println(F(" C"));
  Serial.print(F("   die swing      ")); Serial.print(ampHi - ampLo, 2); Serial.println(F(" C"));
  Serial.println();
  Serial.print(F("   >>> detection threshold 3 sigma = "));
  Serial.print(noise3sig, 2); Serial.println(F(" C"));
  Serial.println();

  Serial.print(F("   Indoors on the door this was 0.49 C. This site is "));
  Serial.print(noise3sig / 0.49f, 1); Serial.println(F("x that."));
  if (sd > 1.0f) {
    Serial.println(F("   TOO NOISY. A burning paper strip gave +7.9 C at 0.5 m, so"));
    Serial.println(F("   the near points would still show - but the far ones will"));
    Serial.println(F("   drown. Shade the target, shade the sensor, or wait for dusk."));
  } else if (sd > 0.4f) {
    Serial.println(F("   Workable, but the 2 m point is at risk. Usable near, weak far."));
  } else {
    Serial.println(F("   Good - as quiet as the indoor scene. Proceed."));
  }
  if (ampHi - ampLo > 0.5f) {
    Serial.println(F("   WARNING: the die temperature itself moved more than 0.5 C."));
    Serial.println(F("   The sensor is heating or cooling - shade it and repeat."));
  }
  rule();
  Serial.println(F("    time |  object C | ambient C |   dObj  |  dAmb  | note"));
  Serial.println(F("---------+-----------+-----------+---------+--------+--------------"));
}

/* ------------------------------------------------------------- baseline */

static void baseline() {
  rule();
  Serial.println(F("BASELINE  aim at the empty scene. Nothing hot in the field."));
  double ao = 0, aa = 0; int n = 0;
  for (int i = 0; i < 30; i++) {
    float o, a; bool p1, p2;
    if (degC(RAM_TOBJ1, &o, &p1) && degC(RAM_TA, &a, &p2) && p1 && p2) {
      ao += o; aa += a; n++;
    }
    delay(150);
  }
  if (n < 20) {
    Serial.print(F("   only ")); Serial.print(n);
    Serial.println(F("/30 clean reads - fix the bus before trusting anything."));
    return;
  }
  baseObj = ao / n; baseAmb = aa / n;
  Serial.print(F("   object  ")); Serial.print(baseObj, 2); Serial.println(F(" C"));
  Serial.print(F("   ambient ")); Serial.print(baseAmb, 2); Serial.println(F(" C"));
  Serial.print(F("   (")); Serial.print(n); Serial.println(F("/30 clean reads)"));
  ambVoided = false;
  Serial.print(F("   detection limit 3 sigma = ")); Serial.print(noise3sig, 2);
  Serial.println(F(" C    |    trial VOID if |dAmb| > 0.50 C"));
  if (noise3sig == NOISE_3SIG)
    Serial.println(F("   (still the INDOOR default - press n once per new site)"));
  rule();
  Serial.println(F("LIVE.  dObj is the signal. Watch that dAmb stays still: a flame"));
  Serial.println(F("       raises the SURFACE temperature in view long before it"));
  Serial.println(F("       warms the air - which is the whole reason for this part."));
  Serial.println();
  Serial.println(F("    time |  object C | ambient C |   dObj  |  dAmb  | note"));
  Serial.println(F("---------+-----------+-----------+---------+--------+--------------"));
}

/* ---------------------------------------------------------------------- */

void setup() {
  Serial.begin(115200);
  delay(600);
  Serial.println();
  Serial.println(F("=========================================================="));
  Serial.println(F("  SAFE-Fire  -  MLX90614ESF-BAA  (GY-906)"));
  Serial.print  (F("  SDA GPIO ")); Serial.print(PIN_SDA);
  Serial.print  (F("   SCL GPIO ")); Serial.print(PIN_SCL);
  Serial.println(F("   VIN 3.3 V  <- NOT 5 V"));
  Serial.println(F("=========================================================="));

  startMs = millis();

  if (!busHealth()) {
    Serial.println();
    Serial.println(F("  Stopping on purpose. Fix the wiring, then press EN."));
    while (true) { Serial.println(F("  [waiting - bus is stuck]")); delay(3000); }
  }

  Wire.begin(PIN_SDA, PIN_SCL, I2C_HZ);

  if (!scan()) {
    Serial.println();
    Serial.println(F("  Fix it, then press r to rescan. No reset needed."));
  } else {
    identify();
    Serial.println(F("  Aim it at the empty scene, then press b."));
  }
}

void loop() {
  if (Serial.available()) {
    char k = Serial.read();
    if (k == 'r') { scan(); return; }
    if (k == 'i') { identify(); return; }
    if (k == 'b') { baseline(); return; }
    if (k == 'n') { noiseFloor(); return; }
    if (k == 'l' || k == 'c' || k == 'p' || k == 'x') {
      static uint8_t trialNo[4] = {0, 0, 0, 0};
      const char *nm[4] = {"LIGHTER", "CANDLE ", "PAPER  ", "OTHER  "};
      uint8_t i = (k == 'l') ? 0 : (k == 'c') ? 1 : (k == 'p') ? 2 : 3;
      trialNo[i]++;
      char m[110];
      snprintf(m, sizeof(m),
               "===== MARK  %s  trial %u  at %.1f s  =====",
               nm[i], (unsigned)trialNo[i], (millis() - startMs) / 1000.0f);
      Serial.println(m);
      return;
    }
    if (k == 's') {
      float o, a; bool p1, p2;
      if (degC(RAM_TOBJ1, &o, &p1) && degC(RAM_TA, &a, &p2))
        { Serial.print(F("   object ")); Serial.print(o, 2);
          Serial.print(F(" C   ambient ")); Serial.print(a, 2);
          Serial.println(F(" C")); }
      else Serial.println(F("   bad read"));
      return;
    }
  }

  /* A heartbeat while waiting for b. Without it the sketch is silent after
   * setup, and a Serial Monitor opened late shows an empty screen forever -
   * indistinguishable from a dead board. Never leave a bring-up tool silent. */
  if (isnan(baseObj)) {
    static uint32_t last = 0;
    if (millis() - last > 3000) {
      last = millis();
      float o, a; bool po, pa;
      if (degC(RAM_TOBJ1, &o, &po) && degC(RAM_TA, &a, &pa) && po && pa) {
        Serial.print(F("  [alive] object "));  Serial.print(o, 2);
        Serial.print(F(" C   ambient "));      Serial.print(a, 2);
        Serial.println(F(" C   - press b to take the baseline"));
      } else {
        Serial.println(F("  [alive] sensor not answering - press r to rescan"));
      }
    }
    delay(100);
    return;
  }

  float o, a; bool po, pa;
  if (!(degC(RAM_TOBJ1, &o, &po) && degC(RAM_TA, &a, &pa)) || !po || !pa) {
    Serial.print(F(" "));
    Serial.print((millis() - startMs) / 1000.0f, 1);
    Serial.println(F("s |  ---- BAD READ (checksum or error flag) - not a value ----"));
    delay(500);
    return;
  }

  float dO = o - baseObj, dA = a - baseAmb;
  char line[130];
  snprintf(line, sizeof(line), " %6.1fs | %9.2f | %9.2f | %+7.2f | %+6.2f | ",
           (millis() - startMs) / 1000.0f, o, a, dO, dA);
  Serial.print(line);
  /* Order matters. The dAmb check comes FIRST because it invalidates the row
   * outright - a large dObj measured while the die is warming is not a small
   * signal to be treated with caution, it is not a measurement of the scene
   * at all. Reporting it as "STRONG heat source" would be the wrong answer
   * confidently stated. */
  if (fabsf(dA) > AMB_VOID) {
    Serial.print(F("VOID - the sensor itself is heating (dAmb "));
    Serial.print(dA, 2);
    Serial.print(F(") - pull the source back, wait, redo"));
    ambVoided = true;
  }
  else if (o >= OBJ_MAX - 5.0f)  Serial.print(F("SATURATED - move the source back"));
  else if (dO >= 20.0f)          Serial.print(F("STRONG heat source"));
  else if (dO >=  5.0f)          Serial.print(F("clear rise"));
  else if (dO >=  1.5f)          Serial.print(F("slight rise"));
  else if (dO >= noise3sig)      Serial.print(F("above 3 sigma"));
  else if (dO <= -noise3sig)     Serial.print(F("below 3 sigma"));
  Serial.println();

  /* Say it once when the run recovers, so a trial that was voided mid-way
   * cannot be quietly written into a table as if it had been clean. */
  if (ambVoided && fabsf(dA) <= AMB_VOID) {
    ambVoided = false;
    Serial.println(F("   ^ dAmb is back in range, but THIS TRIAL IS SPENT."));
    Serial.println(F("     Wait for dObj to fall under 3 sigma, press b, start again."));
  }
  delay(500);
}
