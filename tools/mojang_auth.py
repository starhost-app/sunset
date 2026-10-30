#!/usr/bin/env python3
"""Official Minecraft Launcher Authentication Flow (00000000402b5328).

Uses Mojang's official client ID and Live SDK endpoint (login.live.com).
Displays 'Minecraft Launcher' on the Microsoft login page.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "00000000402b5328"
REDIRECT_URI = "https://login.live.com/oauth20_desktop.srf"
SCOPE = "service::user.auth.xboxlive.com::MBI_SSL offline_access"
OUTPUT_FILE = os.path.expanduser("~/horizon/auth.json")

AUTH_URL = (
    "https://login.live.com/oauth20_authorize.srf?"
    + urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    })
)

def http_post(url, data=None, json_data=None, headers=None):
    headers = headers or {}
    if json_data is not None:
        payload = json.dumps(json_data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
    elif data is not None:
        payload = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    else:
        payload = b""

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed

def http_get(url, headers=None):
    headers = headers or {}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"raw": body}
        return e.code, parsed

def authenticate_with_code(code):
    print("\n[1/5] Exchanging authorization code at login.live.com/oauth20_token.srf...")
    status, token_res = http_post(
        "https://login.live.com/oauth20_token.srf",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }
    )
    if status != 200:
        print(f"Token exchange failed ({status}): {token_res}")
        sys.exit(1)

    ms_access_token = token_res["access_token"]
    ms_refresh_token = token_res.get("refresh_token")
    user_id = token_res.get("user_id")
    print(f"Acquired Microsoft Access Token (User ID: {user_id})")

    # [2/5] Xbox Live
    print("\n[2/5] Authenticating with Xbox Live...")
    # Live SDK tokens can be passed as raw token or with d= prefix
    xbl_res = None
    for ticket in [ms_access_token, f"d={ms_access_token}", f"t={ms_access_token}"]:
        status, res = http_post(
            "https://user.auth.xboxlive.com/user/authenticate",
            json_data={
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": ticket
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }
        )
        if status == 200:
            xbl_res = res
            break

    if not xbl_res:
        print(f"Xbox Live authentication failed ({status}): {res}")
        sys.exit(1)

    xbl_token = xbl_res["Token"]
    user_hash = xbl_res["DisplayClaims"]["xui"][0]["uhs"]

    # [3/5] XSTS
    print("[3/5] Authorizing with XSTS for Minecraft...")
    status, xsts_res = http_post(
        "https://xsts.auth.xboxlive.com/xsts/authorize",
        json_data={
            "Properties": {
                "SandboxId": "RETAIL",
                "UserTokens": [xbl_token]
            },
            "RelyingParty": "rp://api.minecraftservices.com/",
            "TokenType": "JWT"
        }
    )
    if status != 200:
        print(f"XSTS authorization failed ({status}): {xsts_res}")
        sys.exit(1)

    xsts_token = xsts_res["Token"]

    # [4/5] Minecraft Services
    print("[4/5] Logging in to Minecraft Services...")
    status, mc_res = http_post(
        "https://api.minecraftservices.com/authentication/login_with_xbox",
        json_data={
            "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
        }
    )
    if status != 200:
        print(f"Minecraft login failed ({status}): {mc_res}")
        sys.exit(1)

    mc_access_token = mc_res["access_token"]
    mc_expires_in = mc_res.get("expires_in", 86400)

    # [5/5] Profile & Entitlements
    print("[5/5] Fetching profile and verifying ownership...")
    auth_header = {"Authorization": f"Bearer {mc_access_token}"}
    _, entitlements = http_get(
        "https://api.minecraftservices.com/entitlements/mcstore",
        headers=auth_header
    )
    items = entitlements.get("items", [])
    owns_mc = any(it.get("name") in ("game_minecraft", "product_minecraft") for it in items)

    p_status, profile = http_get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers=auth_header
    )
    username = profile.get("name", "Unknown") if p_status == 200 else "Unknown"
    uuid = profile.get("id") if p_status == 200 else None

    print("\n" + "=" * 60)
    print("SUCCESSFULLY AUTHENTICATED VIA OFFICIAL MINECRAFT LAUNCHER ID!")
    print(f"  Minecraft Username: {username}")
    print(f"  UUID:               {uuid}")
    print(f"  Owns Java Edition:  {'Yes' if owns_mc else 'No'}")
    print("=" * 60)

    auth_data = {
        "client_id": CLIENT_ID,
        "auth_type": "mojang_official_live_sdk",
        "username": username,
        "uuid": uuid,
        "owns_minecraft": owns_mc,
        "minecraft_access_token": mc_access_token,
        "minecraft_expires_at": int(time.time() + mc_expires_in),
        "microsoft_refresh_token": ms_refresh_token,
        "last_updated": int(time.time())
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(auth_data, f, indent=2)

    print(f"\nSaved auth info to: {OUTPUT_FILE}\n")

def main():
    print("=" * 60)
    print("Official Minecraft Launcher Sign-In (00000000402b5328)")
    print("=" * 60)
    print("\nOpening your browser to Microsoft login...")
    print(f"\nURL: {AUTH_URL}\n")

    try:
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            subprocess.Popen(["xdg-open", AUTH_URL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            webbrowser.open(AUTH_URL)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

    print("*" * 60)
    print("Instructions:")
    print("1. Log in to your Microsoft Account in the opened browser.")
    print("2. The page will say 'Minecraft Launcher'.")
    print("3. When finished, you will be redirected to a page that starts with:")
    print("   https://login.live.com/oauth20_desktop.srf?code=...")
    print("4. Copy that full URL from the browser address bar.")
    print("*" * 60)

    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        raw_input = sys.argv[1]
    else:
        raw_input = input("\nPaste the redirect URL (or code) here: ").strip()

    if not raw_input:
        print("No input provided. Exiting.")
        sys.exit(1)

    code = raw_input
    if "code=" in raw_input:
        match = re.search(r"code=([^&]+)", raw_input)
        if match:
            code = urllib.parse.unquote(match.group(1))

    authenticate_with_code(code)

if __name__ == "__main__":
    main()
