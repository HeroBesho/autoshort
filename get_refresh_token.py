"""Run this ONCE on your own computer to get a YouTube refresh token.
Usage:  pip install google-auth-oauthlib
        python get_refresh_token.py
Paste your Client ID and Client Secret when asked (type them here, never in chat)."""
from google_auth_oauthlib.flow import InstalledAppFlow

client_id = input("Client ID: ").strip()
client_secret = input("Client Secret: ").strip()

flow = InstalledAppFlow.from_client_config(
    {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    },
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
print("\nREFRESH TOKEN (save it as the GitHub secret YT_REFRESH_TOKEN):\n")
print(creds.refresh_token)
