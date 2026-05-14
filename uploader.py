"""
uploader.py — YouTube API v3 upload (adapted from NCS bot)
Supports both regular video and Shorts upload.
"""
import os
import random
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

scopes = ["https://www.googleapis.com/auth/youtube.upload"]


def get_authenticated_service():
    """Authenticate using client_secret.json and token.json."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing YouTube access token...")
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secret.json"):
                print("Error: client_secret.json not found!")
                return None
            print("No token — starting browser login...")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", scopes)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())
            print("Saved token.json!")

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path, title, description, tags, is_short=False):
    """Upload a video (or Short) to YouTube."""
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22" if not is_short else "23",  # 22=People, 23=Comedy
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    if is_short:
        body["snippet"]["categoryId"] = "23"

    media = MediaFileUpload(file_path, chunksize=1024 * 1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print(f">>> Uploading to YouTube ({'Shorts' if is_short else 'Video'})...")
    response = request.execute()
    video_id = response.get("id")
    print(f">>> Upload success! Video ID: {video_id}")
    return video_id


def run_upload(file_path, title, is_short=False):
    """Main entry point."""
    youtube = get_authenticated_service()
    if not youtube:
        return False

    tags = ["movie", "shorts", "cinematic", "viral", "trending", "movie scene"]
    description = f"🎬 {title}\n\n#movie #shorts #viral #cinematic"

    video_id = upload_video(youtube, file_path, title, description, tags, is_short=is_short)
    return bool(video_id)
