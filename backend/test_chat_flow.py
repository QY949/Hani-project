#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""端到端验证：登录 -> 上传图片 -> 拿本地路径 -> 调 /api/chat。"""
import io
import sys

import requests

BASE = "http://127.0.0.1:5000"
AVATAR = r"C:\Users\Admin\Desktop\yaozu-ich-project\frontend\images\ai_avatar.png"

s = requests.Session()

def check(name, ok, extra=""):
    print(("PASS" if ok else "FAIL"), name, extra)
    if not ok:
        sys.exit(1)

# 1. 静态资源
for path, expect in [("/", 200), ("/ai-assistant.html", 200),
                     ("/images/ai_avatar.png", 200), ("/css/style.css", 200),
                     ("/js/ai-assistant.js", 200), ("/js/auth.js", 200)]:
    r = s.get(BASE + path, timeout=5)
    check("GET " + path, r.status_code == expect, str(r.status_code))

# 2. 游客状态
r = s.get(BASE + "/api/me", timeout=5)
check("GET /api/me 游客", r.status_code == 200 and r.json()["user"] is None)

# 3. 未登录调 chat 应 401
r = s.post(BASE + "/api/chat", json={"message": "你好"}, timeout=5)
check("POST /api/chat 未登录 -> 401", r.status_code == 401, str(r.status_code))

# 4. 登录（种子管理员）
r = s.post(BASE + "/api/login", json={"username": "admin", "password": "admin123"}, timeout=5)
check("POST /api/login admin", r.status_code == 200, r.text[:80])

# 5. 上传图片
with open(AVATAR, "rb") as f:
    r = s.post(BASE + "/api/upload",
               files={"file": ("chat_test.png", io.BytesIO(f.read()), "image/png")},
               timeout=10)
check("POST /api/upload", r.status_code == 201, r.text[:120])
upload_url = r.json()["url"]
print("   返回本地路径:", upload_url)

# 6. 用返回路径调 chat（无 DASHSCOPE_API_KEY 应 503；出现 503 说明参数校验通过、链路可达）
r = s.post(BASE + "/api/chat",
           json={"message": "请识别这张图片", "image_url": upload_url}, timeout=15)
check("POST /api/chat 带图片路径 -> 503(未配key)/200", r.status_code in (200, 503),
      str(r.status_code) + " " + r.text[:100])

# 7. 非法图片路径应 400
r = s.post(BASE + "/api/chat", json={"message": "x", "image_url": "../secret.png"}, timeout=5)
check("POST /api/chat 路径穿越 -> 400", r.status_code == 400, str(r.status_code))

print("\n全部通过 ✔")
