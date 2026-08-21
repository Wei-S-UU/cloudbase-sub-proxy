import os
import json
import secrets
import requests
from flask import Flask, Response, abort, request, redirect, url_for

app = Flask(__name__)

DATA_FILE = "subscriptions.json"

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


def load_subscriptions():
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_subscriptions(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_id():
    return secrets.token_urlsafe(8)


@app.route("/")
def index():
    return """
https:/#/test-2393204-1312544453.ap-guangzhou.run.tcloudbase.#com/s/yGx65WTf

填入软件中（将上行的 两个# 去除掉 账号就是网址，不是打开网站里的内容）
"""


@app.route("/admin", methods=["GET", "POST"])
def admin():

    subscriptions = load_subscriptions()

    if request.method == "POST":

        upstream_url = request.form.get("url", "").strip()

        if not upstream_url.startswith(("http://", "https://")):
            return "链接格式错误", 400

        sub_id = generate_id()

        while sub_id in subscriptions:
            sub_id = generate_id()

        subscriptions[sub_id] = upstream_url

        save_subscriptions(subscriptions)

        return redirect(url_for("admin"))

    rows = ""

    for sub_id, upstream_url in subscriptions.items():

        proxy_url = (
            request.host_url.rstrip("/")
            + "/s/"
            + sub_id
        )

        rows += f"""
        <tr>
            <td>{sub_id}</td>

            <td>
                <input
                    value="{proxy_url}"
                    readonly
                    style="width:420px"
                >
            </td>

            <td>
                <form
                    method="POST"
                    action="/admin/delete/{sub_id}"
                >
                    <button type="submit">
                        删除
                    </button>
                </form>
            </td>
        </tr>
        """

    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<title>Subscription Manager</title>

</head>

<body
style="
max-width:1000px;
margin:50px auto;
font-family:Arial;
">

<h2>订阅管理</h2>

<form method="POST">

<input
type="text"
name="url"
placeholder="粘贴原始订阅链接"
style="
width:650px;
padding:10px;
"
required
>

<button
type="submit"
style="
padding:10px 20px;
"
>
生成
</button>

</form>

<hr>

<table
border="1"
cellpadding="10"
cellspacing="0"
width="100%"
>

<tr>

<th>ID</th>

<th>CloudBase 订阅地址</th>

<th>操作</th>

</tr>

{rows}

</table>

</body>

</html>
"""


@app.route("/admin/delete/<sub_id>", methods=["POST"])
def delete_subscription(sub_id):

    subscriptions = load_subscriptions()

    if sub_id in subscriptions:

        del subscriptions[sub_id]

        save_subscriptions(subscriptions)

    return redirect(url_for("admin"))


@app.route("/s/<sub_id>", methods=["GET"])
def subscription(sub_id):

    subscriptions = load_subscriptions()

    if sub_id not in subscriptions:
        abort(404)

    user_agent = request.headers.get(
        "User-Agent",
        ""
    ).lower()

    is_subscription_client = any(
        client in user_agent
        for client in SUBSCRIPTION_CLIENTS
    )

    # 普通浏览器访问
    if not is_subscription_client:

        return Response(
            "创建成功",
            status=200,
            content_type="text/plain; charset=utf-8"
        )

    # 订阅客户端访问
    upstream_url = subscriptions[sub_id]

    try:

        r = requests.get(
            upstream_url,
            timeout=20,
            headers={
                "User-Agent": user_agent
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


if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "80"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
