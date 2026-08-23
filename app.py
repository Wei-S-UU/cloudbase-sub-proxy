import os
import json
import re
import time
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

from qcloud_cos import CosConfig
from qcloud_cos import CosS3Client


app = Flask(__name__)


# =========================
# COS 配置
# =========================

COS_SECRET_ID = os.environ.get(
    "COS_SECRET_ID",
    ""
)

COS_SECRET_KEY = os.environ.get(
    "COS_SECRET_KEY",
    ""
)

COS_REGION = os.environ.get(
    "COS_REGION",
    "ap-shanghai"
)

COS_BUCKET = os.environ.get(
    "COS_BUCKET",
    "7465-test-d9g7i55l98fd491bf-1432414508"
)

COS_FILE = "subscriptions.json"


# =========================
# 初始化 COS
# =========================

config = CosConfig(
    Region=COS_REGION,
    SecretId=COS_SECRET_ID,
    SecretKey=COS_SECRET_KEY
)

cos_client = CosS3Client(config)


# =========================
# 读取订阅数据
# =========================

def load_subscriptions():

    try:

        response = cos_client.get_object(
            Bucket=COS_BUCKET,
            Key=COS_FILE
        )

        content = response[
            "Body"
        ].get_raw_stream().read()

        data = json.loads(
            content.decode("utf-8")
        )

        return data

    except Exception:

        return {}


# =========================
# 保存订阅数据
# =========================

def save_subscriptions(data):

    content = json.dumps(
        data,
        ensure_ascii=False,
        indent=2
    )

    cos_client.put_object(
        Bucket=COS_BUCKET,
        Key=COS_FILE,
        Body=content.encode("utf-8")
    )


# =========================
# 清理超过30天的订阅
# =========================

def cleanup_expired(subscriptions):

    now = int(time.time())

    expire_seconds = 30 * 24 * 60 * 60

    expired_ids = []


    for sub_id, value in subscriptions.items():

        # 兼容旧格式
        if isinstance(
            value,
            str
        ):

            continue


        created_at = value.get(
            "created_at",
            0
        )


        if (
            now - created_at
            >= expire_seconds
        ):

            expired_ids.append(
                sub_id
            )


    for sub_id in expired_ids:

        del subscriptions[
            sub_id
        ]


    return subscriptions, bool(
        expired_ids
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
        (
            "http://",
            "https://"
        )
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
    # 读取数据
    # =====================

    subscriptions = load_subscriptions()


    # =====================
    # 清理30天过期订阅
    # =====================

    subscriptions, changed = cleanup_expired(
        subscriptions
    )


    # =====================
    # 保存当前订阅
    # =====================

    subscriptions[sub_id] = {

        "url": upstream_url,

        "created_at": int(
            time.time()
        )

    }


    save_subscriptions(
        subscriptions
    )


    # =====================
    # 获取当前 CloudBase 地址
    # =====================

    base_url = request.host_url.rstrip(
        "/"
    )


    proxy_url = (
        base_url
        + "/s/"
        + sub_id
    )


    # =====================
    # 生成文字变式
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
        txt_content.encode(
            "utf-8"
        )
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
    # 清理过期订阅
    # =====================

    subscriptions, changed = cleanup_expired(
        subscriptions
    )


    if changed:

        save_subscriptions(
            subscriptions
        )


    # =====================
    # 检查 ID
    # =====================

    if sub_id not in subscriptions:

        abort(404)


    item = subscriptions[
        sub_id
    ]


    # =====================
    # 兼容旧数据
    # =====================

    if isinstance(
        item,
        str
    ):

        upstream_url = item

    else:

        upstream_url = item.get(
            "url"
        )


    if not upstream_url:

        abort(404)


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


        response = Response(
            r.content,
            status=200
        )


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
            ] = (
                "text/plain; charset=utf-8"
            )


        response.headers[
            "Cache-Control"
        ] = (
            "no-store, no-cache, "
            "must-revalidate"
        )


        response.headers[
            "Pragma"
        ] = "no-cache"


        return response


    except requests.RequestException:

        return Response(
            "Upstream subscription request failed",
            status=502,
            content_type=(
                "text/plain; charset=utf-8"
            )
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
