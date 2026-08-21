import os
import json
import re
import requests

from io import BytesIO
from urllib.parse import urlparse

from flask import (
    Flask,
    Response,
    abort,
    request,
    send_file
)

app = Flask(__name__)

DATA_FILE = "subscriptions.json"


# =========================
# 读取订阅数据
# =========================

def load_subscriptions():

    if not os.path.exists(DATA_FILE):
        return {}

    try:

        with open(
            DATA_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {}


# =========================
# 保存订阅数据
# =========================

def save_subscriptions(data):

    with open(
        DATA_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================
# 提取原链接最后一段
# =========================

def extract_sub_id(url):

    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    if not path:
        return None

    sub_id = path.split("/")[-1]

    if not sub_id:
        return None

    # 只允许常见 URL ID 字符
    if not re.match(
        r"^[A-Za-z0-9_-]+$",
        sub_id
    ):
        return None

    return sub_id


# =========================
# 首页
# =========================

@app.route("/")
def index():

    return "创建成功"


# =========================
# 管理后台
# =========================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    # =====================
    # 打开后台
    # =====================

    if request.method == "GET":

        return """
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
content="width=device-width, initial-scale=1.0">

<title>Subscription Generator</title>

</head>

<body
style="
margin:0;
background:#f5f5f5;
font-family:Arial,sans-serif;
">

<div
style="
max-width:700px;
margin:80px auto;
background:white;
padding:35px;
border-radius:12px;
box-shadow:0 2px 12px rgba(0,0,0,0.08);
">

<h2>
订阅生成器
</h2>

<p
style="
color:#666;
"
>
输入原始订阅链接，生成订阅文件。
</p>

<form method="POST">

<input
type="url"
name="url"
placeholder="粘贴原始订阅链接"
required
style="
width:100%;
box-sizing:border-box;
padding:12px;
font-size:15px;
border:1px solid #ccc;
border-radius:6px;
margin-bottom:15px;
"
>

<button
type="submit"
style="
width:100%;
padding:12px;
font-size:15px;
border:0;
border-radius:6px;
cursor:pointer;
"
>
生成并下载
</button>

</form>

</div>

</body>

</html>
"""


    # =====================
    # 获取原始链接
    # =====================

    upstream_url = request.form.get(
        "url",
        ""
    ).strip()


    if not upstream_url.startswith(
        ("http://", "https://")
    ):

        return (
            "链接格式错误",
            400
        )


    # =====================
    # 提取 ID
    # =====================

    sub_id = extract_sub_id(
        upstream_url
    )


    if not sub_id:

        return (
            "无法提取原始链接最后一段 ID",
            400
        )


    # =====================
    # 保存映射
    # =====================

    subscriptions = load_subscriptions()

    subscriptions[sub_id] = upstream_url

    save_subscriptions(
        subscriptions
    )


    # =====================
    # 获取当前 CloudBase 地址
    # =====================

    base_url = request.host_url.rstrip("/")

    proxy_url = (
        base_url
        + "/s/"
        + sub_id
    )


    # =====================
    # 生成文字变式
    #
    # https://xxx.com/s/xxx
    #
    # ↓
    #
    # https:/#/xxx.#com/s/xxx
    # =====================

    display_url = proxy_url.replace(
        "://",
        ":/#/",
        1
    )


    if ".com/" in display_url:

        display_url = display_url.replace(
            ".com/",
            ".#com/",
            1
        )


    # =====================
    # TXT 内容
    # =====================

    txt_content = (
        "CloudBase订阅地址：\n"
        f"{proxy_url}\n\n"

        "软件填写格式：\n"
        f"{display_url}\n\n"

        "填入软件中（将上行的 两个# 去除掉 "
        "账号就是网址，不是打开网站里的内容）\n"
    )


    # =====================
    # 内存生成 TXT
    # =====================

    file_data = BytesIO(
        txt_content.encode("utf-8")
    )

    file_data.seek(0)


    filename = (
        f"{sub_id}.txt"
    )


    return send_file(
        file_data,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=filename
    )


# =========================
# 订阅接口
# =========================

@app.route(
    "/s/<sub_id>",
    methods=["GET"]
)
def subscription(sub_id):

    subscriptions = load_subscriptions()


    # =====================
    # 检查 ID
    # =====================

    if sub_id not in subscriptions:

        abort(404)


    upstream_url = subscriptions[
        sub_id
    ]


    # =====================
    # 请求原始订阅
    # =====================

    try:

        r = requests.get(
            upstream_url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "Chrome/120.0 Safari/537.36"
                )
            }
        )


        r.raise_for_status()


        # =====================
        # 原样返回
        # =====================

        response = Response(
            r.content,
            status=200
        )


        # 保留上游 Content-Type
        if r.headers.get(
            "Content-Type"
        ):

            response.headers[
                "Content-Type"
            ] = r.headers[
                "Content-Type"
            ]

        else:

            response.headers[
                "Content-Type"
            ] = "text/plain; charset=utf-8"


        # 防止缓存导致刷新拿到旧订阅
        response.headers[
            "Cache-Control"
        ] = "no-store, no-cache, must-revalidate"


        response.headers[
            "Pragma"
        ] = "no-cache"


        return response


    except requests.RequestException as e:

        return Response(
            "Upstream subscription request failed",
            status=502,
            content_type="text/plain; charset=utf-8"
        )


# =========================
# 启动
# =========================

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
