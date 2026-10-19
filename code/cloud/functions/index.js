/**
 * SAFE-Fire push fan-out.
 *
 * One Firestore trigger. When the edge device writes a new alarm into
 * `events/`, this sends a message to the `alarms` topic, which every installed
 * app subscribes to on start.
 *
 * WHY THE CLOUD AND NOT THE JETSON
 *   The Jetson can send these itself, and `JETSON/scripts/notify.py` still can,
 *   but doing so needs a service account private key sitting on a device in a
 *   flat in Thi Qar, in a repository that is published under a DOI. Here the
 *   credential never exists outside Google's infrastructure: the Admin SDK is
 *   authenticated by the runtime. That is the whole argument.
 *
 *   The cost is one hop. The edge path sends at the same instant it writes the
 *   document; this path waits for the write to commit and the trigger to fire,
 *   and a cold start adds more. Both are worth measuring, which is why the edge
 *   sender was kept behind a flag rather than deleted.
 *
 * WHY DATA ONLY, WITH NO notification BLOCK
 *   A `notification` block is rendered by the system, which bypasses
 *   onMessageReceived while the app is backgrounded. The app would lose its
 *   per-level channel, PRIORITY_MAX and CATEGORY_ALARM. Data only keeps the app
 *   in charge of how a fire alarm looks.
 *
 * WHY ONLY A LEVEL AND AN ID ARE SENT
 *   The sentence the edge writes into the event is English. Composing the text
 *   here would push English onto an Arabic phone. The app builds both the title
 *   and the body from its own string resources, so the notification arrives in
 *   the reader's language. The payload carries the two facts that cannot be
 *   derived: which level, and which event to open.
 */
const {onDocumentCreated} = require("firebase-functions/v2/firestore");
const {setGlobalOptions} = require("firebase-functions/v2");
const logger = require("firebase-functions/logger");
const {initializeApp} = require("firebase-admin/app");
const {getMessaging} = require("firebase-admin/messaging");

initializeApp();

// maxInstances is a cost fuse, not a performance setting. A runaway write loop
// on the edge must not be able to bill an unbounded number of invocations.
//
// The region is not a preference. This project's Firestore database lives in
// eur3, the European multi-region, so the Eventarc trigger is created there;
// deploying the function into us-central1 left the trigger and its target on
// opposite sides of the Atlantic. europe-west1 sits inside eur3, which removes
// that hop and is also far closer to Thi Qar than Iowa is.
setGlobalOptions({maxInstances: 5, region: "europe-west1"});

/** Must match ALARM_TOPIC in SafeFireApp.kt. */
const TOPIC = "alarms";

/**
 * WATCH is sensors elevated with the camera clear. The system deliberately does
 * not call that an alarm, so it does not wake anyone at three in the morning
 * either. Only these two are pushed.
 */
const ALARM_LEVELS = new Set(["ALERT", "CONFIRMED"]);

exports.notifyOnAlarm = onDocumentCreated("events/{eventId}", async (event) => {
  const snap = event.data;
  if (!snap) {
    return;
  }

  const doc = snap.data() || {};
  const level = String(doc.level || "");

  if (!ALARM_LEVELS.has(level)) {
    logger.info("no push for level", {level, eventId: event.params.eventId});
    return;
  }

  const eventId = String(doc.id || event.params.eventId);

  try {
    const id = await getMessaging().send({
      topic: TOPIC,
      data: {
        level: level,
        eventId: eventId,
      },
      android: {
        // Without high priority the message waits for the next Doze
        // maintenance window, which for a fire alarm is the same as not
        // sending it. ttl bounds how long a stale alarm may still arrive.
        priority: "high",
        ttl: 120000,
      },
    });
    logger.info("push sent", {level, eventId, messageId: id});
  } catch (err) {
    // Logged and swallowed. Throwing would retry the whole trigger, and a
    // duplicate fire alarm on the phone is worse than a missing log line.
    logger.error("push failed", {level, eventId, error: String(err)});
  }
});
