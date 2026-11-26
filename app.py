import os
import requests
from flask import Flask, redirect, request, session, render_template, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "simon-secret-123")

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://simon-ai.onrender.com/callback")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
USER_URL = "https://open.tiktokapis.com/v2/user/info/"

@app.route("/")
def index():
    connected = "access_token" in session
    user = session.get("user", {})
    return render_template("index.html", connected=connected, user=user)

@app.route("/login")
def login():
    url = f"{AUTH_URL}?client_key={CLIENT_KEY}&scope=user.info.basic,video.publish,video.upload&response_type=code&redirect_uri={REDIRECT_URI}&state=simon123"
    return redirect(url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=no_code")
    data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }
    r = requests.post(TOKEN_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    result = r.json()
    access_token = result.get("access_token")
    if not access_token:
        return f"Error: {result} <br><a href='/'>Go Back</a>"
    session["access_token"] = access_token
    # Get user info for beautiful dashboard
    try:
        u = requests.get(USER_URL, headers={"Authorization": f"Bearer {access_token}"}, params={"fields": "open_id,union_id,avatar_url,display_name,username"}).json()
        session["user"] = u.get("data", {}).get("user", {})
    except:
        session["user"] = {}
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    if "access_token" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session.get("user", {}))

@app.route("/post", methods=["POST"])
def post():
    token = session.get("access_token")
    if not token:
        return redirect("/")
    video_file = request.files.get("video")
    caption = request.form.get("caption", "")
    privacy = request.form.get("privacy", "SELF_ONLY")
    if not video_file:
        return "Please choose a video <a href='/dashboard'>Back</a>"
    video_bytes = video_file.read()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    init_data = {
        "post_info": {
            "title": caption,
            "privacy_level": privacy,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
            "video_cover_timestamp_ms": 1000
        },
        "source_info": {"source": "FILE_UPLOAD", "video_size": len(video_bytes), "chunk_size": len(video_bytes), "total_chunk_count": 1}
    }
    init_res = requests.post(UPLOAD_URL, headers=headers, json=init_data).json()
    publish_id = init_res.get("data", {}).get("publish_id")
    upload_url = init_res.get("data", {}).get("upload_url")
    if not upload_url:
        return f"Upload failed: {init_res} <br><a href='/dashboard'>Back</a>"
    requests.put(upload_url, headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{len(video_bytes)-1}/{len(video_bytes)}"}, data=video_bytes)
    return render_template("success.html", caption=caption)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
