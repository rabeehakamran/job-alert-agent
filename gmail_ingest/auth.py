"""
Handles Gmail OAuth authentication and token persistence.

First-time setup (one-time, local machine):
1. Go to console.cloud.google.com, create a project
2. Enable the Gmail API (APIs & Services -> Library -> search "Gmail API")
3. Configure OAuth consent screen -> External -> add yourself as a test user
4. Credentials -> Create Credentials -> OAuth client ID -> Desktop app
5. Download the JSON, save it as credentials.json in this project's root

Running this file directly will trigger the one-time browser login
and save a reusable token to token.pickle.
"""

import os
import pickle

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Read-only scope only -- we never need to modify or send mail from this pipeline.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDENTIALS_PATH = os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json")
TOKEN_PATH = os.getenv("GMAIL_TOKEN_PATH", "token.pickle")


def get_gmail_service():
    """Returns an authenticated Gmail API service object.

    On first run this opens a browser for consent. On later runs it reuses
    (and silently refreshes) the saved token, so the cron job never needs
    a human in the loop.
    """
    creds = None

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_PATH):
                raise FileNotFoundError(
                    f"Missing {CREDENTIALS_PATH}. Download OAuth client credentials "
                    "from Google Cloud Console first (see module docstring)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("gmail", "v1", credentials=creds)


if __name__ == "__main__":
    # Running this file directly does the one-time interactive login
    # and confirms the connection works.
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated as: {profile['emailAddress']}")
