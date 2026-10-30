#!/usr/bin/env python3
"""Simple Microsoft Authentication for Minecraft (Java Edition).

No custom Azure registration needed (uses standard launcher client ID).
Stores account and tokens directly in a plain JSON file (auth.json).
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "c36a9fb6-4f2a-41ff-90bd-ae7cc92031eb"
OUTPUT_FILE = os.path.expanduser("~/horizon/auth.json")

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

def main():
    print("=" * 60)
    print("Minecraft Microsoft Authentication (Simple JSON Flow)")
    print("=" * 60)
    
    # Step 1: Request Device Code from Microsoft
    print("\n[1/6] Requesting device authorization from Microsoft...")
    status, res = http_post(
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode",
        data={
            "client_id": CLIENT_ID,
            "scope": "XboxLive.signin offline_access"
        }
    )
    if status != 200:
        print(f"Failed to get device code ({status}): {res}")
        sys.exit(1)
        
    user_code = res["user_code"]
    device_code = res["device_code"]
    verification_uri = res["verification_uri"]
    interval = res.get("interval", 5)
    expires_in = res.get("expires_in", 900)
    
    print("\n" + "*" * 60)
    print(f"  👉 Go to:   {verification_uri}")
    print(f"  👉 Code:    {user_code}")
    print("*" * 60 + "\n")
    
    # Try opening browser automatically
    print(f"Attempting to open browser at {verification_uri}...")
    try:
        # Check if xdg-open works
        if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
            subprocess.Popen(["xdg-open", verification_uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Opened in your browser window!")
        else:
            webbrowser.open(verification_uri)
    except Exception as e:
        print(f"Could not open browser automatically: {e}")
        print(f"Please open {verification_uri} manually.")

    # Step 2: Poll for Microsoft Token
    print(f"\n[2/6] Waiting for you to sign in with code '{user_code}'...")
    start_time = time.time()
    ms_tokens = None
    
    while time.time() - start_time < expires_in:
        time.sleep(interval)
        status, poll_res = http_post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code
            }
        )
        if status == 200:
            ms_tokens = poll_res
            print("\nMicrosoft authentication successful!")
            break
        
        err = poll_res.get("error")
        if err == "authorization_pending":
            print(".", end="", flush=True)
            continue
        elif err == "slow_down":
            print("s", end="", flush=True)
            time.sleep(5)
            continue
        else:
            print(f"\nSign-in error: {poll_res}")
            sys.exit(1)

    if not ms_tokens:
        print("\nTimed out waiting for sign-in.")
        sys.exit(1)

    ms_access_token = ms_tokens["access_token"]
    ms_refresh_token = ms_tokens.get("refresh_token")

    # Step 3: Authenticate with Xbox Live
    print("\n[3/6] Authenticating with Xbox Live (user.auth.xboxlive.com)...")
    status, xbl_res = http_post(
        "https://user.auth.xboxlive.com/user/authenticate",
        json_data={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
    )
    if status != 200:
        print(f"Xbox Live auth failed ({status}): {xbl_res}")
        sys.exit(1)
        
    xbl_token = xbl_res["Token"]
    user_hash = xbl_res["DisplayClaims"]["xui"][0]["uhs"]

    # Step 4: Authorize with XSTS
    print("[4/6] Authorizing with XSTS for Minecraft (xsts.auth.xboxlive.com)...")
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
        xerr = xsts_res.get("XErr")
        if xerr == 2148916233:
            print("Error: Account has no Xbox profile. Please create one on xbox.com first.")
        elif xerr == 2148916238:
            print("Error: Child account. Needs to be added to a Microsoft Family.")
        else:
            print(f"XSTS authorization failed ({status}): {xsts_res}")
        sys.exit(1)
        
    xsts_token = xsts_res["Token"]

    # Step 5: Login to Minecraft Services
    print("[5/6] Logging in to Minecraft Services (api.minecraftservices.com)...")
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

    # Step 6: Verify Entitlements and Profile
    print("[6/6] Verifying game ownership and fetching Minecraft profile...")
    auth_header = {"Authorization": f"Bearer {mc_access_token}"}
    
    # Ownership
    _, entitlements = http_get(
        "https://api.minecraftservices.com/entitlements/mcstore",
        headers=auth_header
    )
    items = entitlements.get("items", [])
    owns_mc = any(it.get("name") in ("game_minecraft", "product_minecraft") for it in items)
    
    # Profile
    p_status, profile = http_get(
        "https://api.minecraftservices.com/minecraft/profile",
        headers=auth_header
    )
    if p_status != 200:
        print(f"Could not load Minecraft profile ({p_status}): {profile}")
        username = "Unknown"
        uuid = None
    else:
        username = profile.get("name")
        uuid = profile.get("id")

    print("\n" + "=" * 60)
    print("SUCCESSFULLY AUTHENTICATED!")
    print(f"  Minecraft Username: {username}")
    print(f"  UUID:               {uuid}")
    print(f"  Owns Java Edition:  {'Yes' if owns_mc else 'No'}")
    print("=" * 60)

    # Store directly in a simple JSON file
    auth_data = {
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
    
    print(f"\nSaved auth info to: {OUTPUT_FILE}")
    print(f"Tokens stored cleanly as JSON without OS keychain complexity.\n")

def refresh():
    if not os.path.exists(OUTPUT_FILE):
        print(f"No existing {OUTPUT_FILE} found. Run auth first.")
        sys.exit(1)
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    refresh_token = data.get("microsoft_refresh_token")
    if not refresh_token:
        print("No refresh token in auth.json. Run auth again.")
        sys.exit(1)

    print("[1/4] Refreshing Microsoft OAuth token...")
    status, ms_tokens = http_post(
        "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
    )
    if status != 200:
        print(f"Failed to refresh Microsoft token ({status}): {ms_tokens}")
        sys.exit(1)

    ms_access_token = ms_tokens["access_token"]
    ms_refresh_token = ms_tokens.get("refresh_token", refresh_token)

    print("[2/4] Authenticating with Xbox Live...")
    status, xbl_res = http_post(
        "https://user.auth.xboxlive.com/user/authenticate",
        json_data={
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={ms_access_token}"
            },
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT"
        }
    )
    if status != 200:
        print(f"Xbox Live auth failed: {xbl_res}")
        sys.exit(1)
    xbl_token = xbl_res["Token"]
    user_hash = xbl_res["DisplayClaims"]["xui"][0]["uhs"]

    print("[3/4] Authorizing with XSTS for Minecraft...")
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
        print(f"XSTS authorization failed: {xsts_res}")
        sys.exit(1)
    xsts_token = xsts_res["Token"]

    print("[4/4] Obtaining new Minecraft access token...")
    status, mc_res = http_post(
        "https://api.minecraftservices.com/authentication/login_with_xbox",
        json_data={
            "identityToken": f"XBL3.0 x={user_hash};{xsts_token}"
        }
    )
    if status != 200:
        print(f"Minecraft login failed: {mc_res}")
        sys.exit(1)

    data["minecraft_access_token"] = mc_res["access_token"]
    data["minecraft_expires_at"] = int(time.time() + mc_res.get("expires_in", 86400))
    data["microsoft_refresh_token"] = ms_refresh_token
    data["last_updated"] = int(time.time())

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Successfully refreshed tokens in {OUTPUT_FILE}!\n")

def make_session(path):
    if not os.path.exists(OUTPUT_FILE):
        print(f"No existing {OUTPUT_FILE} found. Run auth first.")
        sys.exit(1)
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    session = {
        "name": data["username"],
        "uuid": data["uuid"],
        "access_token": data["minecraft_access_token"],
        "user_type": "msa"
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    print(f"Session written to {path} (mode 0600)")

if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    elif "--session" in sys.argv:
        idx = sys.argv.index("--session")
        target = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "session.json"
        make_session(target)
    else:
        main()
