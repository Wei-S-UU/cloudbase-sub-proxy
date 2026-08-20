import os
import requests
from flask import Flask, Response, abort

app = Flask(__name__)

UPSTREAM_TEMPLATE = os.environ.get(
    "UPSTREAM_TEMPLATE",
    "https://hg.keydosm.us/s/ap.download/true/{id}"
)

@app.route("/s/<path:sub_id>", methods=["GET"])
def subscription(sub_id):
    if not sub_id:
        abort(404)

    url = UPSTREAM_TEMPLATE.format(id=sub_id)

    try:
        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        r.raise_for_status()

        content_type = r.headers.get(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        return Response(
            r.content,
            status=r.status_code,
            content_type=content_type
        )

    except requests.RequestException:
        abort(502)


@app.route("/", methods=["GET"])
def index():
    return "CloudBase subscription proxy is running."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    app.run(host="0.0.0.0", port=port)
