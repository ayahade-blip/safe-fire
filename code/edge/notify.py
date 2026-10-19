# -*- coding: utf-8 -*-
"""SAFE-Fire - push an alarm to the phone through FCM HTTP v1.

WHY THIS FILE EXISTS
    The app has had the receiving half all along: a FirebaseMessagingService
    declared in the manifest, three notification channels by level, and a
    runtime permission request. Nothing ever sent it anything. Claim C-16 in
    CLAIMS_TO_VERIFY.md records that push alerts could not fire, and this is the
    missing half.

WHY IT SENDS FROM THE JETSON AND NOT FROM A CLOUD FUNCTION
    Cloud Functions for Firebase has required the Blaze plan since 2020, which
    means a billing account even though the free quota would cover this project
    many times over. Sending from the device needs no billing, and it also takes
    Firestore out of the alarm path entirely, which is worth a line in the
    latency chapter: the notification leaves at the same moment the event
    document does, rather than after it.

WHY NOT THE SERVER KEY EVERY TUTORIAL SHOWS
    The legacy endpoint, POST https://fcm.googleapis.com/fcm/send with an
    Authorization: key=... header, was deprecated in June 2023 and shut down on
    22 July 2024. It cannot work. HTTP v1 replaces it and authenticates with a
    short-lived OAuth2 access token minted from a service account.

WHY A TOPIC AND NOT DEVICE TOKENS
    HTTP v1 has no multicast in the REST API, so a token list means one request
    per phone and a device collection that has to be kept clean as tokens
    rotate. A topic is one request regardless of how many phones subscribe, and
    the subscription is managed by the client. The app subscribes to "alarms".

SETUP, ONCE
    1. Firebase console -> Project settings -> Service accounts -> Generate new
       private key. Save the JSON on the Jetson, readable only by your user:
           chmod 600 ~/safefire-fcm.json
    2. Point this at it:
           export SAFEFIRE_FCM_KEY=/home/aya5/safefire-fcm.json
    3. Install a signer. Either is fine:
           pip3 install google-auth
           pip3 install "pyjwt[crypto]"
    4. Check it end to end, with the phone in your hand:
           python3 -u notify.py --selftest

SECURITY
    That JSON file is a credential for the whole messaging API of the project.
    It must never enter the git repository or the DOI archive. It is read from
    a path in an environment variable for exactly that reason.
"""
from __future__ import print_function

import argparse
import json
import os
import ssl
import sys
import time

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
except ImportError:                                    # Python 2 fallback
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode


PROJECT_DEFAULT = "safefire-1"
TOPIC_DEFAULT = "alarms"
SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL = "https://oauth2.googleapis.com/token"
FCM_URL = "https://fcm.googleapis.com/v1/projects/%s/messages:send"
HTTP_TIMEOUT_S = 8.0

# Tokens are good for an hour. Refreshing at 45 minutes leaves room for a slow
# link without ever presenting an expired one.
TOKEN_TTL_S = 45 * 60

# Only these two are alarms. WATCH is sensors elevated with the camera clear,
# which the system deliberately does not treat as an alarm, so it does not wake
# anybody at night either.
NOTIFY_LEVELS = ("ALERT", "CONFIRMED")


class FcmSender(object):
    """Minimal FCM HTTP v1 client for one topic."""

    def __init__(self, project=PROJECT_DEFAULT, key_file=None,
                 topic=TOPIC_DEFAULT, verbose=False):
        self.project = project
        self.topic = topic
        self.verbose = verbose
        self.key_file = key_file or os.environ.get("SAFEFIRE_FCM_KEY")
        self.stats = {"sent": 0, "errors": 0, "skipped": 0, "last_error": None}
        self._token = None
        self._token_at = 0.0
        self._sa = None
        self._ctx = ssl.create_default_context()

    # -- credentials -----------------------------------------------------

    def available(self):
        return bool(self.key_file) and os.path.exists(self.key_file)

    def _service_account(self):
        if self._sa is None:
            if not self.available():
                raise RuntimeError(
                    "no service account key. Set SAFEFIRE_FCM_KEY to the JSON "
                    "downloaded from Firebase console, Project settings, "
                    "Service accounts.")
            f = open(self.key_file, "r")
            try:
                self._sa = json.load(f)
            finally:
                f.close()
        return self._sa

    def _access_token(self):
        """A short lived OAuth2 token, cached.

        google-auth is preferred because it is the library Google maintains for
        exactly this. PyJWT is the fallback because it installs from a wheel on
        arm64 without a compiler in more cases than google-auth's dependency
        chain does. Both produce the same assertion.
        """
        now = time.time()
        if self._token and (now - self._token_at) < TOKEN_TTL_S:
            return self._token

        sa = self._service_account()

        try:
            from google.oauth2 import service_account          # noqa: F401
            from google.auth.transport.requests import Request as GRequest
            creds = service_account.Credentials.from_service_account_info(
                sa, scopes=[SCOPE])
            creds.refresh(GRequest())
            self._token = creds.token
            self._token_at = now
            return self._token
        except ImportError:
            pass

        try:
            import jwt
        except ImportError:
            raise RuntimeError(
                "no JWT signer installed. Run one of:\n"
                "    pip3 install google-auth\n"
                "    pip3 install \"pyjwt[crypto]\"")

        issued = int(now)
        claims = {
            "iss": sa["client_email"],
            "scope": SCOPE,
            "aud": TOKEN_URL,
            "iat": issued,
            "exp": issued + 3600,
        }
        assertion = jwt.encode(claims, sa["private_key"], algorithm="RS256")
        if isinstance(assertion, bytes):                # PyJWT 1.x returns bytes
            assertion = assertion.decode("ascii")

        body = urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        }).encode("ascii")
        req = Request(TOKEN_URL, data=body,
                      headers={"Content-Type":
                               "application/x-www-form-urlencoded"})
        r = urlopen(req, timeout=HTTP_TIMEOUT_S, context=self._ctx)
        try:
            payload = json.loads(r.read().decode("utf-8"))
        finally:
            r.close()
        self._token = payload["access_token"]
        self._token_at = now
        return self._token

    # -- sending ---------------------------------------------------------

    def notify(self, level, title, body, event_id=None, force=False):
        """Send one alarm. Returns (ok, detail).

        Data only, with no notification block, on purpose. The app builds the
        notification itself so it can pick the channel for the level and set
        CATEGORY_ALARM, and a notification block would bypass onMessageReceived
        while the app is in the background and lose all of that.
        """
        if not force and level not in NOTIFY_LEVELS:
            self.stats["skipped"] += 1
            return False, "level %s is not an alarm" % level

        if not self.available():
            self.stats["skipped"] += 1
            return False, "no service account key configured"

        message = {
            "message": {
                "topic": self.topic,
                # Every value in a data payload must be a string. FCM rejects
                # the whole request otherwise, with a 400 that names no field.
                "data": {
                    "level": str(level),
                    "title": str(title),
                    "body": str(body),
                    "eventId": str(event_id or ""),
                },
                "android": {
                    # Without this the message waits for the next maintenance
                    # window in Doze, which for a fire alarm is useless.
                    "priority": "high",
                    "ttl": "120s",
                },
            }
        }

        try:
            token = self._access_token()
        except Exception as e:
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return False, str(e)

        req = Request(
            FCM_URL % self.project,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json; UTF-8",
                     "Authorization": "Bearer %s" % token})
        t0 = time.time()
        try:
            r = urlopen(req, timeout=HTTP_TIMEOUT_S, context=self._ctx)
            r.read()
            r.close()
            rtt = (time.time() - t0) * 1000.0
            self.stats["sent"] += 1
            if self.verbose:
                print("  fcm %s sent in %.0f ms" % (level, rtt))
            return True, "%.0f ms" % rtt
        except HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            self.stats["errors"] += 1
            self.stats["last_error"] = "HTTP %s %s" % (e.code, detail)
            return False, self.stats["last_error"]
        except (URLError, Exception) as e:
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            return False, str(e)


def from_rationale(level, why, event_id=None):
    """Title and body for an alarm, from the fusion output."""
    title = {
        "ALERT": "Fire alert",
        "CONFIRMED": "Fire confirmed",
    }.get(level, level)
    body = (why or {}).get("conclusion") or ""
    return title, body


def _selftest(a):
    s = FcmSender(project=a.project, key_file=a.key, topic=a.topic, verbose=True)
    print("project    :", s.project)
    print("topic      :", s.topic)
    print("key file   :", s.key_file or "NOT SET")
    if not s.available():
        print()
        print("FAILED: no service account key.")
        print("  export SAFEFIRE_FCM_KEY=/path/to/serviceAccount.json")
        return 1

    print()
    print("minting an access token")
    try:
        tok = s._access_token()
        print("  ok, %d characters" % len(tok))
    except Exception as e:
        print("  FAILED:", e)
        return 1

    print()
    print("sending a test alarm to the topic")
    ok, detail = s.notify(
        a.level,
        "SAFE-Fire test",
        "This is a test alarm sent from the Jetson. No fire was detected.",
        event_id="selftest",
        force=True)
    print("  %s  %s" % ("ok" if ok else "FAILED", detail))
    if ok:
        print()
        print("Look at the phone. Nothing arriving means the app has not")
        print("subscribed to the topic yet, or notifications are blocked for")
        print("it in Android settings.")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="SAFE-Fire push sender, FCM HTTP v1")
    ap.add_argument("--project", default=PROJECT_DEFAULT)
    ap.add_argument("--topic", default=TOPIC_DEFAULT)
    ap.add_argument("--key", default=None,
                    help="service account JSON, or set SAFEFIRE_FCM_KEY")
    ap.add_argument("--level", default="CONFIRMED",
                    help="level to put in the test message")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if not args.selftest:
        ap.print_help()
        sys.exit(2)
    sys.exit(_selftest(args))
