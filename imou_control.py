"""Imou Ranger Dual detection control by Open Platform.

Usage: python imou_control.py state|activate|deactivate
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HOST = "https://openapi-fk.easy4ip.com"
REFERENCES = {"108800": "Movement", "18200": "Human Detection"}
CHANNELS = {
    0: "PT Lens",
    1: "Fixed Lens"
}


def load_env():
    """Reads the .env file next to the script without external dependencies."""
    file = Path(__file__).resolve().parent / ".env"
    if not file.is_file():
        return
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if name in {"IMOU_APP_ID", "IMOU_APP_SECRET", "IMOU_DEVICE_ID"}:
            os.environ.setdefault(name, value)


def credential(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} is missing. Configure the .env file")
    return value


def api(endpoint, params, app_id, app_secret):
    instant = int(time.time())
    nonce = str(uuid.uuid4())
    message = f"time:{instant},nonce:{nonce},appSecret:{app_secret}"
    key = hashlib.sha256(app_secret.encode()).hexdigest().encode()
    signature = base64.b64encode(hmac.new(key, message.encode(), hashlib.sha256).digest()).decode()
    body = {
        "system": {"ver": "1.0", "appId": app_id, "sign": signature, "time": instant, "nonce": nonce},
        "id": str(uuid.uuid4()),
        "params": params,
    }
    request = urllib.request.Request(
        f"{HOST}/openapi/{endpoint}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as answer:
            content = json.load(answer)
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(f"Network error at {endpoint}: {error}") from error
    result = content.get("result", {})
    if str(result.get("code")) != "0":
        raise RuntimeError(
            f"{endpoint} refused: {result.get('code')} - {result.get('msg')}"
        )
    return result.get("data") or {}


def get_product(token, device_id, app_id, app_secret):
    for page in range(1, 11):
        data = api("listDeviceDetailsByPage", {
            "token": token, "page": page, "pageSize": 20, "source": "bindAndShare"
        }, app_id, app_secret)
        devices = data.get("deviceList", [])
        for device in devices:
            if device.get("deviceId") == device_id:
                product = device.get("productId")
                if not product:
                    raise RuntimeError("The camera does not return the productId")
                return product
        if len(devices) < 20:
            break
    raise RuntimeError("The camera does not appear among the linked devices")


def read(token, device_id, product_id, channel, app_id, app_secret):
    data = api("getIotDeviceProperties", {
        "token": token,
        "deviceList": [{
            "deviceId": device_id, "channelId": channel,
            "productId": product_id, "properties": list(REFERENCES)
        }],
    }, app_id, app_secret)
    devices = data.get("deviceList") or []
    if not devices or not isinstance(devices[0].get("properties"), dict):
        raise RuntimeError(f"The channel {channel} has not returned valid properties")
    properties = devices[0]["properties"]
    if not all(ref in properties for ref in REFERENCES):
        raise RuntimeError(f"Properties are missing in channel {channel}: {list(properties)}")
    return {ref: properties[ref] for ref in REFERENCES}


def show_state(token, device_id, product_id, app_id, app_secret):
    for channel, name in CHANNELS.items():
        values = read(token, device_id, product_id, channel, app_id, app_secret)
        print(f"Channel {channel} ({name}): " + ", ".join(
            f"{REFERENCES[ref]}={values[ref]}" for ref in REFERENCES
        ))


def write(token, device_id, product_id, channel, value, app_id, app_secret):
    api("setIotDeviceProperties", {
        "token": token,
        "deviceList": [{
            "deviceId": device_id, "channelId": channel,
            "productId": product_id,
            "properties": {ref: value for ref in REFERENCES},
        }],
    }, app_id, app_secret)


def main():
    parser = argparse.ArgumentParser(description="Control of Imou Ranger Dual detection")
    parser.add_argument("action", choices=["state", "activate", "deactivate"])
    args = parser.parse_args()
    load_env()
    app_id = credential("IMOU_APP_ID")
    app_secret = credential("IMOU_APP_SECRET")
    device_id = credential("IMOU_DEVICE_ID")

    auth = api("accessToken", {}, app_id, app_secret)
    token = auth.get("accessToken")
    if not token:
        raise RuntimeError("Authentication did not return an accessToken")
    product = get_product(token, device_id, app_id, app_secret)

    print("\nInitial state:")
    show_state(token, device_id, product, app_id, app_secret)
    if args.action == "state":
        return

    value = 1 if args.action == "activate" else 0
    print(f"\nExecuting {args.action} for both lenses (without confirmation)...")
    errors = []
    for channel, name in CHANNELS.items():
        try:
            write(token, device_id, product, channel, value, app_id, app_secret)
            print(f"Order sent to channel {channel} ({name}).")
        except Exception as exc:
            errors.append(f"Channel {channel}: {exc}")
            print(f"ERROR in channel {channel}: {exc}")

    time.sleep(3)
    print("\nVerification:")
    for channel, name in CHANNELS.items():
        try:
            state = read(token, device_id, product, channel, app_id, app_secret)
            correct = all(str(x) == str(value) for x in state.values())
            print(f"Channel {channel} ({name}): {state} -> {'OK' if correct else 'MISMATCH'}")
            if not correct:
                errors.append(f"Channel {channel}: state different from requested")
        except Exception as exc:
            errors.append(f"Channel {channel}: read failure: {exc}")
            print(f"Channel {channel}: could not be verified: {exc}")

    if errors:
        print("\nERROR: Not all detection settings could be verified.")
        for error in errors:
            print("-", error)
        sys.exit(1)
    print("\nAll properties verified by API.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, KeyError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
