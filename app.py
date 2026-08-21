import os
import json
import re
import requests
from urllib.parse import urlparse
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


def extract_sub_id(url):
    """
    从原始订阅链接提取最后一段 ID。

    例如：
    https://hg.keydosm.us/s/ap.download/true/n4xcbk1awb2q39qg

    返回：
    n4xcbk1awb2q39qg
    """

    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    if not path:
        return None

    sub_id = path.split("/")[-1]

    if not sub_id:
        return None

    # 防止异常字符进入 URL 路径
    if not re.match(r"^[A-Za-z0-9_-]+$", sub_id):
        return None

    return sub_id


@app.route("/")
def index():
    return "创建成功"


@app.route("/admin", methods=["GET", "POST"])
def admin():

    subscriptions = load_subscriptions()

    if request.method == "POST":

        upstream_url = request.form.get("url", "").strip()

        if not upstream_url.startswith(("http://", "https://")):
            return "链接格式错误", 400

        # 从原链接提取最后一段
        sub_id = extract_sub_id(upstream_url)

        if not sub_id:
            return "无法提取订阅链接最后一段 ID", 400

        # 保存映射
        subscriptions[sub_id] = upstream_url

        save_subscriptions(subscriptions)

        return redirect(url_for("admin"))

    rows = ""

    base_url = request.host_url.rstrip("/")

    for sub_id, upstream_url in subscriptions.items():

        # 正常 CloudBase 订阅地址
        proxy_url = f"{base_url}/s/{sub_id}"

        # 生成两个 # 的展示格式
        display_url = proxy_url.replace(
            "://",
            ":/#/",
            1
        )

        # 只替换域名中的 .com
        if ".com/" in display_url:
            display_url = display_url.replace(
                ".com/",
                ".#com/",
                1
            )

        rows += f"""
        <tr>

            <td>
                {sub_id}
            </td>

            <td>

                <div>
                    <strong>原始订阅：</strong>
                </div>

                <div
                    style="
                    word-break:break-all;
                    margin:5px 0 15px 0;
                    "
                >
                    {upstream_url}
                </div>

                <div>
                    <strong>CloudBase 订阅：</strong>
                </div>

                <input
                    value="{proxy_url}"
                    readonly
                    style="
                    width:90%;
                    padding:7px;
                    "
                >

                <br><br>

                <div>
                    <strong>软件填写格式：</strong>
                </div>

                <div
                    style="
                    margin-top:5px;
                    padding:10px;
                    background:#f5f5f5;
                    word-break:break-all;
                    "
                >
                    {display_url}
                </div>

                <div
                    style="
                    margin-top:8px;
                    font-size:14px;
                    color:#555;
                    "
                >
                    填入软件中（将上行的 两个# 去除掉
                    账号就是网址，不是打开网站里的内容）
                </div>

            </td>

            <td>

                <form
                    method="POST"
                    action="/admin/delete/{sub_id}"
                >

                    <button
                        type="submit"
                        style="
                        padding:6px 12px;
                        cursor:pointer;
                        "
                    >
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
        max-width:1100px;
        margin:50px auto;
        font-family:Arial;
        "
    >

        <h2>订阅管理</h2>

        <form method="POST">

            <input
                type="text"
                name="url"
                placeholder="粘贴原始订阅链接"
                style="
                width:70%;
                padding:10px;
                "
                required
            >

            <button
                type="submit"
                style="
                padding:10px 20px;
                cursor:pointer;
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

                <th>
                    ID
                </th>

                <th>
                    订阅信息
                </th>

                <th>
                    操作
                </th>

            </tr>

            {rows}

        </table>

    </body>

    </html>
    """


@app.route(
    "/admin/delete/<sub_id>",
    methods=["POST"]
)
def delete_subscription(sub_id):

    subscriptions = load_subscriptions()

    if sub_id in subscriptions:

        del subscriptions[sub_id]

        save_subscriptions(subscriptions)

    return redirect(url_for("admin"))


@app.route(
    "/s/<sub_id>",
    methods=["GET"]
)
def subscription(sub_id):

    subscriptions = load_subscriptions()

    if sub_id not in subscriptions:
        abort(404)

    user_agent = request.headers.get(
        "User-Agent",
        ""
    ).lower()

    # 判断是否为订阅客户端
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

    # 获取原始订阅
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
