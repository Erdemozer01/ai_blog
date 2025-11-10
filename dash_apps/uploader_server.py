# uploader_server.py
import os
import dash
import dash_uploader as du
from dash import html

UPLOAD_ROOT = r"C:\Users\virtu\PycharmProjects\ai_blog\uploads"
os.makedirs(UPLOAD_ROOT, exist_ok=True)

app = dash.Dash(__name__)  # DİKKAT: DjangoDash DEĞİL
server = app.server

# upload_api: BİR YOL (path) OLMALIDIR, TAM URL DEĞİL
du.configure_upload(app, UPLOAD_ROOT, upload_api="/uploader")  # -> /uploader (POST/GET)

app.layout = html.Div("Uploader alive")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8051, debug=True)