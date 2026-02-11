
from argparse import ArgumentParser
from base64 import urlsafe_b64encode
from hashlib import sha256
from pprint import pprint
from secrets import token_urlsafe
from sys import exit
from urllib.parse import urlencode, urlparse, parse_qs
from webbrowser import open as open_url

import requests
import time
import json
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

# Latest app version can be found using GET /v1/application-info/android
USER_AGENT = "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"
REDIRECT_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"


def s256(data):
    """S256 transformation method."""

    return urlsafe_b64encode(sha256(data).digest()).rstrip(b"=").decode("ascii")


def oauth_pkce(transform):
    """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

    code_verifier = token_urlsafe(32)
    code_challenge = transform(code_verifier.encode("ascii"))

    return code_verifier, code_challenge


def get_auth_token_data(response):
    data = response.json()

    try:
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
    except KeyError:
        print("error:")
        pprint(data)
        return None, None

    print("access_token:", access_token)
    print("refresh_token:", refresh_token)
    print("expires_in:", data.get("expires_in", 0))
    return access_token, refresh_token


def selenium_login(url):
    """Attempt to capture the callback URL automatically using Selenium."""
    if not SELENIUM_AVAILABLE:
        return None

    print("\n[!] Starting automated browser to capture login...")
    options = Options()
    options.add_experimental_option("detach", True)
    # Enable performance logging to capture redirects
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(url)

    print("\n>>> PLEASE LOG IN IN THE OPENED CHROME WINDOW <<<")
    print(">>> The script will automatically detect when you finish. <<<\n")

    captured_code = None
    last_url = None
    
    def extract_code(target_url):
        if "code=" in target_url:
            parsed = urlparse(target_url)
            query_dict = parse_qs(parsed.query)
            if "code" in query_dict:
                return query_dict["code"][0]
        return None

    try:
        while True:
            # 1. Check current URL
            try:
                current_url = driver.current_url
                if current_url != last_url:
                    display_url = (current_url[:75] + '...') if len(current_url) > 75 else current_url
                    print(f"[*] Current URL: {display_url}")
                    last_url = current_url
                
                captured_code = extract_code(current_url)
                if captured_code:
                    print(f"\n[+] Successfully captured code from URL!")
                    break
            except Exception:
                # Browser might be closed or disconnected, we still check logs below
                pass

            # 2. Check Performance Logs (Captures redirects that don't finish loading)
            try:
                logs = driver.get_log('performance')
                for entry in logs:
                    message = json.loads(entry['message'])['message']
                    if 'params' in message and 'request' in message['params']:
                        req_url = message['params']['request'].get('url', '')
                        captured_code = extract_code(req_url)
                        if captured_code:
                            print(f"\n[+] Successfully captured code from network logs!")
                            return captured_code
            except Exception:
                pass

            # 3. Check if window was closed
            try:
                if not driver.window_handles:
                    print("\n[!] Window closed.")
                    break
            except Exception:
                print("\n[!] Browser connection lost.")
                break
                
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Automation interrupted by user.")
    except Exception as e:
        print(f"\n[!] Automation error: {e}")
    finally:
        try:
            driver.quit()
        except:
            pass
    
    return captured_code


def login():
    code_verifier, code_challenge = oauth_pkce(s256)
    login_params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }

    auth_url = f"{LOGIN_URL}?{urlencode(login_params)}"
    
    # Try automation first
    code = selenium_login(auth_url)

    if not code:
        print("\n--- Manual Fallback ---")
        print(f"1. Open the following URL in your browser: \n{auth_url}")
        print("2. Log in with your Pixiv account.")
        print("3. After logging in, you will be redirected to a blank page (or see an error).")
        print("4. Copy the entire URL from the address bar and paste it below.")

        while True:
            try:
                user_input = input("Paste URL or Code here: ").strip()
                
                # Basic validation
                if not user_input:
                    continue

                parsed = urlparse(user_input)
                query_dict = parse_qs(parsed.query)

                if "code" in query_dict:
                    code = query_dict["code"][0]
                    break
                elif len(user_input) > 50 and "http" in user_input:
                    print("\n[!] The URL you pasted does not contain the 'code' parameter.")
                    print("    Please ensure you are copying the final URL (callback) after logging in.")
                    print("    It should look like: .../callback?code=...")
                    if "post-redirect" in user_input:
                        print("    (You seem to be on the intermediate redirect page. Please let it finish loading or click the link if stuck.)")
                    print("    Try again:\n")
                else:
                    # Assume it's the raw code if length is reasonable or no URL structure
                    code = user_input
                    break
            except (EOFError, KeyboardInterrupt):
                return

    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "code_verifier": code_verifier,
            "grant_type": "authorization_code",
            "include_policy": "true",
            "redirect_uri": REDIRECT_URI,
        },
        headers={"User-Agent": USER_AGENT},
    )

    _, refresh_token = get_auth_token_data(response)
    return refresh_token


def refresh(refresh_token):
    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "refresh_token",
            "include_policy": "true",
            "refresh_token": refresh_token,
        },
        headers={"User-Agent": USER_AGENT},
    )
    _, new_refresh_token = get_auth_token_data(response)
    return new_refresh_token


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers()
    parser.set_defaults(func=lambda _: parser.print_usage())
    login_parser = subparsers.add_parser("login")
    login_parser.set_defaults(func=lambda _: login())
    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("refresh_token")
    refresh_parser.set_defaults(func=lambda ns: refresh(ns.refresh_token))
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()