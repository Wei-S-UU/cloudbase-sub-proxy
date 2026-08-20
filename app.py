import os
import requests
from flask import Flask, Response, abort, request

app = Flask(__name__)

UPSTREAM_TEMPLATE = os.environ.get(
    "UPSTREAM_TEMPLATE",
    "https://hg.keydosm.us/s/ap.download/true/{id}"
)

# 常见订阅客户端
SUBSCRIPTION_CLIENTS = [
    "shadowrocket",
    "clash",
    "clashmeta",
    "stash",
    "surge",
    "quantumult",
    "quantumult x",
    "sing-box",
    "v2ray",
    "v2rayng",
    "nekoray",
    "hiddify",
]

@app.route("/s/<path:sub_id>", methods=["GET"])
def subscription(sub_id):
    if not sub_id:
        abort(404)

    user_agent = request.headers.get("User-Agent", "").lower()

    # 浏览器访问：显示创建成功
    is_browser = (
        "mozilla" in user_agent
        and not any(client in user_agent for client in SUBSCRIPTION_CLIENTS)
    )

    if is_browser:
        return Response(
            "创建成功",
            status=200,
            content_type="text/plain; charset=utf-8"
        )

    # 订阅客户端访问：返回原订阅
    url = UPSTREAM_TEMPLATE.format(id=sub_id)

    try:
        r = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": user_agent or "Mozilla/5.0"
            }
        )

        r.raise_for_status()

        return Response(
            r.content,
            status=200,
            content_type=r.headers.get(
                "Content-Type",
                "text/plain; charset=utf-8"
            )
        )

    except requests.RequestException:
        abort(502)


@app.route("/", methods=["GET"])
def index():
    return "创建成功"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    app.run(host="0.0.0.0", port=port)
