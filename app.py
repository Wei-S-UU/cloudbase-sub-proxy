import os
import json
import re
import traceback
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

# =========================
# 腾讯云 COS 配置与初始化
# =========================
SECRET_ID = os.environ.get("TENCENT_SECRET_ID", "").strip()
SECRET_KEY = os.environ.get("TENCENT_SECRET_KEY", "").strip()
REGION = os.environ.get("COS_REGION", "ap-shanghai").strip()
BUCKET = os.environ.get("COS_BUCKET", "sub-proxy-1432414508").strip()
FILE_KEY = "subscriptions.json"

cos_client = None

if SECRET_ID and SECRET_KEY:
    try:
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(Region=REGION, SecretId=SECRET_ID, SecretKey=SECRET_KEY)
        cos_client = CosS3Client(config)
        print(f"[COS] 客户端初始化成功 -> Bucket: {BUCKET}, Region: {REGION}", flush=True)
    except Exception as e:
        print(f"[COS Init Error] 初始化失败: {str(e)}", flush=True)
else:
    print("[COS Warning] 未检测到完整的 TENCENT_SECRET_ID / TENCENT_SECRET_KEY 环境变量，将临时使用本地存储模式", flush=True)


# =========================
# 读取订阅数据
# =========================
def load_subscriptions():
    if cos_client:
        try:
            response = cos_client.get_object(
                Bucket=BUCKET,
                Key=FILE_KEY
            )
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except Exception as e:
            err_msg = str(e)
            if "NoSuchResource" in err_msg or "404" in err_msg or "NoSuchKey" in err_msg:
                print("[COS] subscriptions.json 尚不存在，使用初始空数据", flush=True)
                return {}
            print(f"[COS Load Error] 读取失败: {err_msg}", flush=True)
            return {}
    else:
        # 本地备用读取
        if os.path.exists(FILE_KEY):
            try:
                with open(FILE_KEY, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}


# =========================
# 保存订阅数据
# =========================
def save_subscriptions(data):
    if cos_client:
        try:
            body_data = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
            cos_client.put_object(
                Bucket=BUCKET,
                Key=FILE_KEY,
                Body=body_data
            )
            print(f"[COS] 数据成功保存到 COS 存储桶 {BUCKET}/{FILE_KEY}", flush=True)
            return True, None
        except Exception as e:
            err_details = traceback.format_exc()
            print(f"[COS Save Error] 写入 COS 失败:\n{err_details}", flush=True)
            return False, f"COS 写入失败: {str(e)}"
    else:
        try:
            with open(FILE_KEY, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("[Local] 数据已保存至本地文件", flush=True)
            return True, None
        except Exception as e:
            return False, f"本地写入失败: {str(e)}"


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

    if not re.match(r"^[A-Za-z0-9_-]+$", sub_id):
        return None

    return sub_id


# =========================
# 首页
# =========================
@app.route("/")
def index():
    return "服务运行正常"


# =========================
# 管理后台
# =========================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "GET":
        return """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Subscription Generator</title>
</head>
<body style="margin:0;background:#f5f5f5;font-family:Arial,sans-serif;">
<div style="max-width:700px;margin:80px auto;background:white;padding:35px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
<h2>订阅生成器</h2>
<p style="color:#666;">输入原始订阅链接，生成订阅文件。</p>
<form method="POST">
<input type="url" name="url" placeholder="粘贴原始订阅链接" required style="width:100%;box-sizing:border-box;padding:12px;font-size:15px;border:1px solid #ccc;border-radius:6px;margin-bottom:15px;">
<button type="submit" style="width:100%;padding:12px;font-size:15px;border:0;border-radius:6px;cursor:pointer;background:#006eff;color:#fff;">生成并下载</button>
</form>
</div>
</body>
</html>
"""

    upstream_url = request.form.get("url", "").strip()

    if not upstream_url.startswith(("http://", "https://")):
        return ("链接格式错误，必须以 http:// 或 https:// 开头", 400)

    sub_id = extract_sub_id(upstream_url)
    if not sub_id:
        return ("无法提取原始链接最后一段 ID，请检查链接格式", 400)

    subscriptions = load_subscriptions()
    subscriptions[sub_id] = upstream_url
    success, err = save_subscriptions(subscriptions)

    if not success:
        return (f"存储数据失败，原因: {err}。请检查云托管环境变量与 CAM 权限。", 500)

    base_url = request.host_url.rstrip("/")
    sub_url = f"{base_url}/s/{sub_id}"
    clash_url = f"{base_url}/c/{sub_id}"

    display_sub = sub_url.replace("://", ":/#/", 1)
    if ".com/" in display_sub:
        display_sub = display_sub.replace(".com/", ".#com/", 1)

    display_clash = clash_url.replace("://", ":/#/", 1)
    if ".com/" in display_clash:
        display_clash = display_clash.replace(".com/", ".#com/", 1)

    txt_content = (
        "【小火箭 / 通用订阅 (Base64)】\n"
        f"直连地址：{sub_url}\n"
        f"防封格式：{display_sub}\n\n"
        "------------------------------------\n"
        "【Clash / Mihomo 专属订阅 (YAML)】\n"
        f"直连地址：{clash_url}\n"
        f"防封格式：{display_clash}\n\n"
        "说明：填入对应软件时，将防封格式中的两个 # 去除即可。\n"
    )

    file_data = BytesIO(txt_content.encode("utf-8"))
    file_data.seek(0)
    filename = f"{sub_id}.txt"

    return send_file(
        file_data,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=filename
    )


# =========================
# 1. 小火箭 / 通用订阅接口 (拦截 Clash / Mihomo 访问)
# =========================
@app.route("/s/<sub_id>", methods=["GET"])
def subscription(sub_id):
    client_ua = request.headers.get("User-Agent", "").lower()
    
    # 严格拦截 Clash 客户端
    if "clash" in client_ua or "mihomo" in client_ua:
        return Response("Access Denied: Clash client is not allowed on this link.", status=403, content_type="text/plain; charset=utf-8")

    subscriptions = load_subscriptions()

    if sub_id not in subscriptions:
        abort(404)

    upstream_url = subscriptions[sub_id]

    try:
        r = requests.get(
            upstream_url,
            timeout=20,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"
                )
            }
        )
        r.raise_for_status()

        response = Response(r.content, status=200)

        if r.headers.get("Content-Type"):
            response.headers["Content-Type"] = r.headers["Content-Type"]
        else:
            response.headers["Content-Type"] = "text/plain; charset=utf-8"

        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        return response

    except requests.RequestException as e:
        print(f"[Proxy Error] 拉取上游订阅失败: {str(e)}", flush=True)
        return Response(
            "Upstream subscription request failed",
            status=502,
            content_type="text/plain; charset=utf-8"
        )


# =========================
# 2. Clash 专属订阅接口 (拦截 小火箭 / 普通浏览器 偷用)
# =========================
@app.route("/c/<sub_id>", methods=["GET"])
def clash_subscription(sub_id):
    client_ua = request.headers.get("User-Agent", "").lower()
    
    # 严格拦截 小火箭 (Shadowrocket)
    if "shadowrocket" in client_ua:
        return Response("Access Denied: Shadowrocket is not allowed on this link.", status=403, content_type="text/plain; charset=utf-8")
    
    # 限制仅允许 Clash / Mihomo 系列内核请求
    if "clash" not in client_ua and "mihomo" not in client_ua:
        return Response("Access Denied: Only Clash / Mihomo clients are allowed.", status=403, content_type="text/plain; charset=utf-8")

    upstream_clash_template = os.environ.get("UPSTREAM_CLASH", "").strip()
    if not upstream_clash_template:
        return Response("UPSTREAM_CLASH not configured", status=500, content_type="text/plain; charset=utf-8")

    # 替换模板中的 {id} 占位符或拼接末尾
    if "{id}" in upstream_clash_template:
        clash_upstream_url = upstream_clash_template.replace("{id}", sub_id)
    elif "{}" in upstream_clash_template:
        clash_upstream_url = upstream_clash_template.replace("{}", sub_id)
    else:
        clash_upstream_url = f"{upstream_clash_template.rstrip('/')}/{sub_id}"

    try:
        r = requests.get(
            clash_upstream_url,
            timeout=20,
            headers={
                "User-Agent": request.headers.get("User-Agent", "Clash/1.0")
            }
        )
        r.raise_for_status()

        response = Response(r.content, status=200)

        if r.headers.get("Content-Type"):
            response.headers["Content-Type"] = r.headers["Content-Type"]
        else:
            response.headers["Content-Type"] = "text/plain; charset=utf-8"

        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        return response

    except requests.RequestException as e:
        print(f"[Clash Proxy Error] 拉取 Clash 上游订阅失败: {str(e)}", flush=True)
        return Response(
            "Upstream Clash subscription request failed",
            status=502,
            content_type="text/plain; charset=utf-8"
        )


# =========================
# 启动
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "80"))
    app.run(host="0.0.0.0", port=port)
