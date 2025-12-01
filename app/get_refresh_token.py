#!/usr/bin/env python3
"""
Helper script to obtain OneDrive refresh token for GitHub Actions.
Run this script locally to get the refresh token needed for the workflow.
"""

import requests
import webbrowser
from urllib.parse import urlencode, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

CLIENT_ID = input("Enter your Azure AD Application (Client) ID: ").strip()
CLIENT_SECRET = input("Enter your Azure AD Client Secret: ").strip()
REDIRECT_URI = "http://localhost:8080"

# Store the authorization code
auth_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler to receive OAuth callback."""
    
    def do_GET(self):
        global auth_code
        if self.path.startswith('/?'):
            query_params = parse_qs(self.path[2:])
            if 'code' in query_params:
                auth_code = query_params['code'][0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><body><h1>Authorization successful!</h1><p>You can close this window.</p></body></html>')
            elif 'error' in query_params:
                error = query_params['error'][0]
                self.send_response(400)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(f'<html><body><h1>Error: {error}</h1></body></html>'.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logging


def get_refresh_token():
    """Get refresh token using OAuth2 flow."""
    
    # Step 1: Start local server to receive callback
    server = HTTPServer(('localhost', 8080), OAuthHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    # Step 2: Build authorization URL
    auth_params = {
        'client_id': CLIENT_ID,
        'response_type': 'code',
        'redirect_uri': REDIRECT_URI,
        'response_mode': 'query',
        'scope': 'Files.ReadWrite offline_access',
        'state': '12345'
    }
    auth_url = f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{urlencode(auth_params)}"
    
    print("\n" + "="*60)
    print("Opening browser for authorization...")
    print("If browser doesn't open, visit this URL:")
    print(auth_url)
    print("="*60 + "\n")
    
    # Open browser
    webbrowser.open(auth_url)
    
    # Wait for authorization code
    print("Waiting for authorization...")
    timeout = 120  # 2 minutes
    elapsed = 0
    while auth_code is None and elapsed < timeout:
        import time
        time.sleep(1)
        elapsed += 1
    
    server.shutdown()
    
    if auth_code is None:
        print("Error: Authorization timed out or was cancelled.")
        return None
    
    # Step 3: Exchange code for tokens
    print("Exchanging authorization code for tokens...")
    token_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': auth_code,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'authorization_code'
    }
    
    response = requests.post(token_url, data=token_data)
    
    if response.status_code != 200:
        print(f"Error: Failed to get tokens. Status: {response.status_code}")
        print(f"Response: {response.text}")
        return None
    
    tokens = response.json()
    
    print("\n" + "="*60)
    print("SUCCESS! Here are your tokens:")
    print("="*60)
    print(f"\nRefresh Token (save this for GitHub secret ONEDRIVE_REFRESH_TOKEN):")
    print(f"{tokens['refresh_token']}\n")
    print(f"Access Token (expires in {tokens.get('expires_in', 'unknown')} seconds):")
    print(f"{tokens['access_token'][:50]}...\n")
    print("="*60)
    print("\nNext steps:")
    print("1. Copy the Refresh Token above")
    print("2. Go to your GitHub repository")
    print("3. Navigate to Settings → Secrets and variables → Actions")
    print("4. Add a new secret named ONEDRIVE_REFRESH_TOKEN with the value above")
    print("="*60 + "\n")
    
    return tokens['refresh_token']


if __name__ == "__main__":
    try:
        get_refresh_token()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

