#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py —— “向世界介绍云南少数民族”项目 · Flask 后端
=====================================================

项目主题：哈尼族（Hani Ethnic Group）

功能总览：
  1. 静态托管：启动后访问 http://localhost:5000 即是网站首页（托管 frontend/）
  2. 大模型 API：/api/chat 接入“哈尼族文化专家”（DashScope 兼容模式）
  3. 用户权限：Session 登录，三级权限
       - 管理员 admin   ：增删改查（词汇 / 图集 / 图片管理）
       - 普通用户 user   ：浏览、查询、AI 互动、上传图片
       - 游客（未登录） ：仅浏览
  4. 数据接口：/api/vocabulary、/api/gallery、/api/vocab、/api/ethnic-groups
  5. 图片上传：/api/upload 保存到 frontend/images/，数据库存相对路径（images/xxx.jpg）

接口一览：
  POST /api/register            注册（普通用户，注册后自动登录）
  POST /api/login               登录
  POST /api/logout              登出
  GET  /api/me                  当前登录用户（未登录返回 {"user": null}）
  POST /api/chat                哈尼族文化专家对话（普通用户/管理员；支持文字 + 本地图片 URL）
  GET  /api/vocabulary          词汇列表（旧版兼容格式，前端 language.js 在用）
  GET  /api/vocab               词汇列表（新版，支持 民族/分类/关键词 筛选）
  POST /api/vocabulary          新增词汇（管理员）
  PUT  /api/vocabulary/<id>     修改词汇（管理员）
  DELETE /api/vocabulary/<id>   删除词汇（管理员）
  GET  /api/gallery             图集列表（所有人）
  POST /api/gallery             新增图集（管理员）
  PUT  /api/gallery/<id>        修改图集（管理员或上传者本人）
  DELETE /api/gallery/<id>      删除图集（管理员或上传者本人）
  POST /api/upload              上传图片（普通用户/管理员）-> 保存到 frontend/images/，
                                数据库 gallery 存相对路径 images/xxx.jpg
  GET  /api/ethnic-groups       民族列表（含各词汇条数）
  GET  /api/health              健康检查

大模型配置（/api/chat，支持任意 OpenAI 兼容接口）：
  方式一（推荐）：复制 .env.example 为 .env，填入自己的 API（启动时自动加载）
  方式二：设置环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_SYSTEM_PROMPT
  默认值：base_url=https://maas.qianwenaiapi.com/compatible-mode/v1, model=qwen3.8-flash
  兼容旧变量名 DASHSCOPE_API_KEY
"""

import base64
import mimetypes
import os
import secrets
import sqlite3
import uuid
from functools import wraps

from flask import (Flask, abort, jsonify, request, send_from_directory,
                   session)
from flask_cors import CORS
from werkzeug.utils import secure_filename

from init_db import (DEFAULT_CATEGORY, DB_PATH, get_connection,
                     hash_password, verify_password)

# 可选依赖：openai 未安装时 /api/chat 返回 503，其余接口不受影响
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:  # pragma: no cover
    OPENAI_AVAILABLE = False
    OpenAI = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

# ------------------------------------------------------------ 大模型配置 ----
# 支持任意「OpenAI 兼容」接口：DashScope 阿里百炼 / DeepSeek / Moonshot Kimi /
# OpenAI / 自建兼容服务。想换成自己的 API，只需配置以下环境变量（无需改代码）：
#
#   LLM_API_KEY        你的 API Key（必需；兼容旧变量名 DASHSCOPE_API_KEY）
#   LLM_BASE_URL       接口地址（默认 DashScope 兼容模式）
#   LLM_MODEL          模型名称（默认 qwen3.8-flash）
#   LLM_SYSTEM_PROMPT  系统提示词 / AI 助手人设（可选）
#
# 两种配置方式（可同时使用，系统环境变量优先）：
#   1. 环境变量：set LLM_API_KEY=sk-xxxx  （Linux/macOS 用 export）
#   2. 配置文件：复制 .env.example 为 .env，填入自己的值，启动时自动加载

# 加载 backend/.env（存在则生效；不覆盖已设置的系统环境变量）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:  # 未安装 python-dotenv 时跳过，仍可读取系统环境变量
    pass

DEFAULT_SYSTEM_PROMPT = ("你是一位精通云南哈尼族文化、历史、语言和梯田农耕文明的专家。"
                         "请用热情、专业的语气回答用户的问题。")


def _clean_config(value):
    """清理配置值；把启动脚本里的占位符视为未配置。"""
    value = (value or "").strip()
    if "请替换" in value or "粘贴" in value:
        return ""
    return value


LLM_API_KEY = _clean_config(os.environ.get("LLM_API_KEY")
                            or os.environ.get("DASHSCOPE_API_KEY"))
LLM_BASE_URL = (_clean_config(os.environ.get("LLM_BASE_URL"))
                or "https://maas.qianwenaiapi.com/compatible-mode/v1")
LLM_MODEL = _clean_config(os.environ.get("LLM_MODEL")) or "qwen3.8-flash"
SYSTEM_PROMPT = os.environ.get("LLM_SYSTEM_PROMPT") or DEFAULT_SYSTEM_PROMPT

# ------------------------------------------------------------ 上传配置 ------

UPLOAD_DIR = os.path.join(FRONTEND_DIR, "images")   # 图片保存目录：frontend/images/
UPLOAD_URL_PREFIX = "images/"                       # 数据库存储的相对路径前缀
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
MAX_UPLOAD_SIZE = 8 * 1024 * 1024                   # 单张图片上限 8MB

# 新分类 -> 旧前端分类码（language.js 的筛选器仍在用，保证兼容）
LEGACY_CAT_MAP = {"农耕": "farming", "称谓": "greeting", "文化习俗": "greeting"}

# 允许托管的前端静态资源后缀
ALLOWED_EXTENSIONS = {
    ".html", ".htm", ".css", ".js", ".json", ".jpg", ".jpeg", ".png",
    ".gif", ".svg", ".ico", ".webp", ".mp3", ".wav", ".ogg", ".pdf",
    ".woff", ".woff2", ".ttf", ".otf",
}

app = Flask(__name__)
# Session 密钥：优先读环境变量 SECRET_KEY（生产环境请固定设置，否则重启后登录态失效）
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE + 1024 * 1024  # 表单余量 1MB
CORS(app)  # 允许前端跨域访问

_llm_client = None


def get_llm_client():
    """惰性创建大模型客户端（避免未配置 key 时启动报错）。"""
    global _llm_client
    if _llm_client is None and OPENAI_AVAILABLE and LLM_API_KEY:
        _llm_client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    if _llm_client is None:
        print(f"[DEBUG] get_llm_client 返回 None -> openai可用={OPENAI_AVAILABLE}, "
              f"Key已设置={'是' if LLM_API_KEY else '否'}", flush=True)
    return _llm_client


# ------------------------------------------------------------ 工具函数 ------

def query(sql, args=()):
    """执行查询并返回 dict 列表，自动关闭连接。"""
    conn = get_connection()
    try:
        return [dict(row) for row in conn.execute(sql, args).fetchall()]
    finally:
        conn.close()


def to_legacy_category(category):
    """新分类 -> 旧前端分类码，未命中的一律归入生活类。"""
    return LEGACY_CAT_MAP.get(category, "life")


def current_user():
    """从 Session 读取当前登录用户；未登录返回 None（即游客）。"""
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, username, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def login_required(*roles):
    """权限装饰器：要求登录，且角色在 roles 之内（不传则不限制角色）。

    用法：
      @login_required()                # 仅要求登录
      @login_required("admin")         # 仅管理员
      @login_required("user", "admin") # 普通用户或管理员
    """
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user is None:
                return jsonify({"error": "请先登录后再进行操作"}), 401
            if roles and user["role"] not in roles:
                return jsonify({"error": "权限不足：该操作需要 {} 权限".format(" / ".join(roles))}), 403
            return view(*args, **kwargs)
        return wrapper
    return decorator


def resolve_local_image(image_url):
    """把前端传入的图片 URL 解析为服务器本地绝对路径（限制在 frontend/ 内）。

    支持形式：
      images/xxx.jpg
      /images/xxx.jpg
      http://localhost:5000/images/xxx.jpg
    返回 None 表示路径非法或文件不存在（防路径穿越）。
    """
    if not image_url:
        return None
    path = image_url.strip()
    for prefix in ("http://localhost:5000/", "http://127.0.0.1:5000/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
            break
    path = path.lstrip("/")
    if not path:
        return None
    full_path = os.path.abspath(os.path.join(FRONTEND_DIR, path))
    try:
        if os.path.commonpath([full_path, FRONTEND_DIR]) != FRONTEND_DIR:
            return None  # 穿越到 frontend/ 之外，拒绝
    except ValueError:
        return None      # 跨盘符等异常路径，拒绝
    if not os.path.isfile(full_path):
        return None
    return full_path


def image_to_data_url(path):
    """读取本地图片文件，转为 base64 data URL 供多模态大模型使用。"""
    mime_type, _ = mimetypes.guess_type(path)
    mime_type = mime_type or "image/jpeg"
    with open(path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return "data:{};base64,{}".format(mime_type, encoded)


# ------------------------------------------------------------ 前端静态托管 -

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_static(filename):
    if filename.startswith("api/"):  # 兜底防御，API 路由永远优先
        abort(404)
    if os.path.splitext(filename)[1].lower() not in ALLOWED_EXTENSIONS:
        abort(404)
    return send_from_directory(FRONTEND_DIR, filename)


# ------------------------------------------------------------ 用户认证 ------

@app.route("/api/register", methods=["POST"])
def api_register():
    """注册普通用户（注册成功后自动登录）。"""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not 3 <= len(username) <= 20:
        return jsonify({"error": "用户名长度需在 3~20 个字符之间"}), 400
    if len(password) < 6:
        return jsonify({"error": "密码长度至少 6 位"}), 400

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, 'user')",
            (username, hash_password(password)),
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "用户名已被注册"}), 409
    finally:
        conn.close()

    session.permanent = True
    session["user_id"] = user_id
    return jsonify({"id": user_id, "username": username, "role": "user",
                    "message": "注册成功，已自动登录"}), 201


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    finally:
        conn.close()

    if row is None or not verify_password(password, row["password_hash"]):
        return jsonify({"error": "用户名或密码错误"}), 401

    session.permanent = True
    session["user_id"] = row["id"]
    return jsonify({"id": row["id"], "username": row["username"],
                    "role": row["role"], "message": "登录成功"})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"message": "已退出登录"})


@app.route("/api/me")
def api_me():
    user = current_user()
    return jsonify({"user": user})


# ------------------------------------------------------------ 大模型对话 ----

@app.route("/api/chat", methods=["POST"])
@login_required("user", "admin")
def api_chat():
    """哈尼族文化专家对话。

    请求体 JSON：
      { "message": "哈尼族的十月年是怎么过的？", "image_url": "images/xxx.jpg" }
    - message   ：用户文字（可与图片同时提供，也可只传图片）
    - image_url ：本地图片 URL（相对于站点根路径，如 images/xxx.jpg），
                  读取后以 base64 形式随消息发送给多模态大模型
    返回：{ "reply": "...", "model": "<当前配置的模型>" }
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    if not message and not image_url:
        return jsonify({"error": "message 与 image_url 至少提供一个"}), 400

    # 组装多模态消息内容：文字 + 本地图片（base64 data URL）
    content = []
    if message:
        content.append({"type": "text", "text": message})
    if image_url:
        image_path = resolve_local_image(image_url)
        if image_path is None:
            return jsonify({"error": "图片不存在或路径不合法：{}".format(image_url)}), 400
        content.append({"type": "image_url",
                        "image_url": {"url": image_to_data_url(image_path)}})

    # ---- 调试信息：确认环境是否真的拿到了 Key ----
    print("[DEBUG] 读取到的Key:", (LLM_API_KEY[:5] if LLM_API_KEY else "None"), flush=True)
    print("[DEBUG] openai是否可用:", OPENAI_AVAILABLE, flush=True)
    print("[DEBUG] base_url:", LLM_BASE_URL, flush=True)
    print("[DEBUG] model:", LLM_MODEL, flush=True)

    # 请求参数全部合法后，再检查大模型服务可用性
    client = get_llm_client()
    if client is None:
        return jsonify({"error": "大模型服务未配置：请复制 backend/.env.example 为 "
                                    "backend/.env 并填入 LLM_API_KEY"
                                    "（并确认已安装 openai 库）"}), 503

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
        reply = (response.choices[0].message.content or "").strip()
        return jsonify({"reply": reply, "model": LLM_MODEL})
    except Exception as error:
        # 打印真实错误到终端，便于排查（网络错误 / 认证失败 / 余额不足等）
        print("[DEBUG] 大模型调用失败:", str(error), flush=True)
        return jsonify({"error": f"大模型调用失败: {str(error)}"}), 500


# ------------------------------------------------------------ 词汇接口 ------

@app.route("/api/vocabulary")
def api_vocabulary_legacy():
    """词汇列表（旧版格式，兼容现有前端 language.js）。

    返回数组元素形如：
      { cat, zh, mian, script, bunu, lajia, ... }
    同时附带 id / ethnic_group / word / meaning / category / audio_url 等新字段，
    方便后续前端平滑升级。哈尼族词汇统一写入 mian / script 两列。
    """
    rows = query("SELECT * FROM vocabulary ORDER BY id")
    result = []
    for row in rows:
        is_hani = row["ethnic_group"] == "哈尼族"
        result.append({
            # ---- 旧前端字段 ----
            "cat": to_legacy_category(row["category"]),
            "zh": row["meaning"],
            "mian": row["word"] if is_hani else "",
            "script": row["word"] if is_hani else "",
            "bunu": "",
            "lajia": "",
            # ---- 新字段（超集，旧前端会忽略） ----
            "id": row["id"],
            "ethnic_group": row["ethnic_group"],
            "word": row["word"],
            "meaning": row["meaning"],
            "category": row["category"],
            "audio_url": row["audio_url"],
        })
    return jsonify(result)


@app.route("/api/vocab")
def api_vocab():
    """词汇列表（新格式），支持筛选：
      ?ethnic_group=哈尼族&category=日常&q=谷子&limit=50&offset=0
    """
    rows = query("SELECT * FROM vocabulary ORDER BY id")

    ethnic_group = request.args.get("ethnic_group", "").strip()
    category = request.args.get("category", "").strip()
    keyword = request.args.get("q", "").strip()

    if ethnic_group:
        rows = [row for row in rows if row["ethnic_group"] == ethnic_group]
    if category:
        rows = [row for row in rows if row["category"] == category]
    if keyword:
        rows = [row for row in rows
                if keyword in row["meaning"] or keyword in row["word"]]

    total = len(rows)
    limit = request.args.get("limit", type=int)
    offset = request.args.get("offset", type=int, default=0)
    if limit:
        rows = rows[offset:offset + limit]
    elif offset:
        rows = rows[offset:]

    return jsonify({"total": total, "items": rows})


@app.route("/api/vocabulary", methods=["POST"])
@login_required("admin")
def api_vocabulary_create():
    """新增词汇（管理员）。"""
    data = request.get_json(silent=True) or {}
    word = (data.get("word") or "").strip()
    meaning = (data.get("meaning") or "").strip()
    if not word or not meaning:
        return jsonify({"error": "word 和 meaning 不能为空"}), 400

    ethnic_group = (data.get("ethnic_group") or "哈尼族").strip()
    category = (data.get("category") or DEFAULT_CATEGORY).strip()
    audio_url = (data.get("audio_url") or "").strip()

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO vocabulary (ethnic_group, word, meaning, category,"
            " audio_url, source_url) VALUES (?, ?, ?, ?, ?, 'manual')",
            (ethnic_group, word, meaning, category, audio_url),
        )
        conn.commit()
        vocab_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "该词汇已存在（同一民族下词汇不可重复）"}), 409
    finally:
        conn.close()

    return jsonify({"id": vocab_id, "message": "新增成功"}), 201


@app.route("/api/vocabulary/<int:vocab_id>", methods=["PUT"])
@login_required("admin")
def api_vocabulary_update(vocab_id):
    """修改词汇（管理员）。可更新字段：ethnic_group / word / meaning / category / audio_url"""
    data = request.get_json(silent=True) or {}
    fields, values = [], []
    for key in ("ethnic_group", "word", "meaning", "category", "audio_url"):
        if key in data:
            value = (data.get(key) or "").strip()
            if key in ("ethnic_group", "word", "meaning") and not value:
                return jsonify({"error": "{} 不能为空".format(key)}), 400
            fields.append(key)
            values.append(value)
    if not fields:
        return jsonify({"error": "没有需要更新的字段"}), 400

    values.append(vocab_id)
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE vocabulary SET {} WHERE id = ?".format(
                ", ".join("{}=?".format(name) for name in fields)),
            values,
        )
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "词汇不存在"}), 404
    except sqlite3.IntegrityError:
        return jsonify({"error": "更新后与已有词汇重复"}), 409
    finally:
        conn.close()

    return jsonify({"message": "更新成功"})


@app.route("/api/vocabulary/<int:vocab_id>", methods=["DELETE"])
@login_required("admin")
def api_vocabulary_delete(vocab_id):
    """删除词汇（管理员）。"""
    conn = get_connection()
    try:
        cursor = conn.execute("DELETE FROM vocabulary WHERE id = ?", (vocab_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return jsonify({"error": "词汇不存在"}), 404
    finally:
        conn.close()
    return jsonify({"message": "删除成功"})


# ------------------------------------------------------------ 图集接口 ------

@app.route("/api/gallery")
def api_gallery_list():
    """图集列表（所有人可看）。"""
    rows = query(
        "SELECT g.*, u.username AS uploader_name FROM gallery g"
        " LEFT JOIN users u ON u.id = g.uploader_id ORDER BY g.id DESC"
    )
    return jsonify(rows)


@app.route("/api/gallery", methods=["POST"])
@login_required("admin")
def api_gallery_create():
    """新增图集（管理员，直接以 URL/路径形式入库）。"""
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    image_url = (data.get("image_url") or "").strip()
    if not title or not image_url:
        return jsonify({"error": "title 和 image_url 不能为空"}), 400

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO gallery (title, image_url, description, uploader_id)"
            " VALUES (?, ?, ?, ?)",
            (title, image_url, (data.get("description") or "").strip(),
             data.get("uploader_id")),
        )
        conn.commit()
        gallery_id = cursor.lastrowid
    finally:
        conn.close()
    return jsonify({"id": gallery_id, "message": "新增成功"}), 201


@app.route("/api/gallery/<int:gallery_id>", methods=["PUT"])
@login_required("user", "admin")
def api_gallery_update(gallery_id):
    """修改图集（管理员，或上传者本人）。可更新字段：title / image_url / description"""
    user = current_user()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM gallery WHERE id = ?", (gallery_id,)).fetchone()
        if row is None:
            return jsonify({"error": "图集不存在"}), 404
        if user["role"] != "admin" and row["uploader_id"] != user["id"]:
            return jsonify({"error": "权限不足：只能修改自己上传的图集"}), 403

        data = request.get_json(silent=True) or {}
        fields, values = [], []
        for key in ("title", "image_url", "description"):
            if key in data:
                value = (data.get(key) or "").strip()
                if key in ("title", "image_url") and not value:
                    return jsonify({"error": "{} 不能为空".format(key)}), 400
                fields.append(key)
                values.append(value)
        if not fields:
            return jsonify({"error": "没有需要更新的字段"}), 400

        values.append(gallery_id)
        conn.execute(
            "UPDATE gallery SET {} WHERE id = ?".format(
                ", ".join("{}=?".format(name) for name in fields)),
            values,
        )
        conn.commit()
    finally:
        conn.close()
    return jsonify({"message": "更新成功"})


@app.route("/api/gallery/<int:gallery_id>", methods=["DELETE"])
@login_required("user", "admin")
def api_gallery_delete(gallery_id):
    """删除图集（管理员，或上传者本人）。仅删除数据库记录，图片文件保留在 images/ 目录。"""
    user = current_user()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM gallery WHERE id = ?", (gallery_id,)).fetchone()
        if row is None:
            return jsonify({"error": "图集不存在"}), 404
        if user["role"] != "admin" and row["uploader_id"] != user["id"]:
            return jsonify({"error": "权限不足：只能删除自己上传的图集"}), 403

        conn.execute("DELETE FROM gallery WHERE id = ?", (gallery_id,))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"message": "删除成功（图片文件保留在 images/ 目录）"})


# ------------------------------------------------------------ 图片上传 ------

@app.route("/api/upload", methods=["POST"])
@login_required("user", "admin")
def api_upload():
    """上传图片（普通用户/管理员）。

    - 文件保存到 frontend/images/ 目录
    - 数据库 gallery 表存相对路径：images/xxx.jpg
    - 表单字段：file（图片文件）、title（可选，默认取原文件名）、description（可选）
    返回：{ "id": 图集ID, "url": "images/xxx.jpg", "message": "上传成功" }
    """
    image_file = request.files.get("file")
    if image_file is None or not image_file.filename:
        return jsonify({"error": "请选择要上传的图片文件（表单字段名：file）"}), 400

    filename = secure_filename(image_file.filename) or "image.jpg"
    extension = os.path.splitext(filename)[1].lower()
    if extension not in ALLOWED_IMAGE_EXT:
        return jsonify({"error": "不支持的图片格式：{}（支持 {}）".format(
            extension, " / ".join(sorted(ALLOWED_IMAGE_EXT)))}), 400

    # 校验文件真实大小（限制 8MB）
    image_file.seek(0, os.SEEK_END)
    file_size = image_file.tell()
    image_file.seek(0)
    if file_size > MAX_UPLOAD_SIZE:
        return jsonify({"error": "图片过大：上限 8MB，当前 {:.1f}MB".format(
            file_size / 1024 / 1024)}), 400

    # 生成随机文件名，避免重名与特殊字符问题
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stored_name = "{}_{}{}".format(uuid.uuid4().hex[:12], secrets.token_hex(4), extension)
    image_file.save(os.path.join(UPLOAD_DIR, stored_name))
    relative_url = UPLOAD_URL_PREFIX + stored_name   # 数据库存相对路径：images/xxx.jpg

    user = current_user()
    title = (request.form.get("title") or "").strip() or filename
    description = (request.form.get("description") or "").strip()

    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO gallery (title, image_url, description, uploader_id)"
            " VALUES (?, ?, ?, ?)",
            (title, relative_url, description, user["id"]),
        )
        conn.commit()
        gallery_id = cursor.lastrowid
    finally:
        conn.close()

    return jsonify({"id": gallery_id, "url": relative_url, "message": "上传成功"}), 201


@app.route("/api/images")
def api_images():
    """扫描 frontend/images/ 目录，返回其中的图片文件列表（相对路径）。

    前端图集页用它在"数据库图集记录"之外，自动展示用户手动放进目录的图片。
    返回：{ "count": n, "images": ["images/xxx.jpg", ...] }（按文件名排序）
    """
    images = []
    if os.path.isdir(UPLOAD_DIR):
        for name in sorted(os.listdir(UPLOAD_DIR)):
            if os.path.splitext(name)[1].lower() in ALLOWED_IMAGE_EXT:
                images.append(UPLOAD_URL_PREFIX + name)
    return jsonify({"count": len(images), "images": images})


# ------------------------------------------------------------ 其它接口 ------

@app.route("/api/ethnic-groups")
def api_ethnic_groups():
    rows = query(
        "SELECT ethnic_group, COUNT(*) AS count FROM vocabulary"
        " GROUP BY ethnic_group ORDER BY count DESC"
    )
    return jsonify([
        {"ethnic_group": row["ethnic_group"], "count": row["count"]}
        for row in rows
    ])


@app.route("/api/health")
def api_health():
    key = LLM_API_KEY
    return jsonify({
        "status": "ok",
        "db": DB_PATH,
        "llm_configured": bool(key) and OPENAI_AVAILABLE,
        "llm_base_url": LLM_BASE_URL,
        "llm_model": LLM_MODEL,
        # 只显示 Key 的首尾各 4 位，便于确认加载的是哪把钥匙，避免泄露完整 Key
        "llm_api_key_hint": (key[:4] + "..." + key[-4:]) if len(key) >= 8 else "",
    })


@app.errorhandler(413)
def handle_too_large(_error):
    return jsonify({"error": "请求体过大：图片上限 8MB"}), 413


# ------------------------------------------------------------------ 启动 ------

if __name__ == "__main__":
    print("🚀 后端正在启动 ...")
    print("   网站首页     http://localhost:5000/")
    print("   词汇接口     http://localhost:5000/api/vocabulary")
    print("   AI 对话      http://localhost:5000/api/chat")
    print("   大模型接口   {}".format(LLM_BASE_URL))
    print("   模型名称     {}".format(LLM_MODEL))
    if LLM_API_KEY:
        print("   API Key      已加载（{}...）".format(LLM_API_KEY[:4]))
    else:
        print("   [提示] 未检测到 API Key：请复制 .env.example 为 .env 并填入 LLM_API_KEY")
    print("   数据库文件   {}".format(DB_PATH))
    # 部署适配：检测到 PORT 环境变量时视为线上部署——绑定 0.0.0.0 并关闭 debug；
    # 本地直接运行（无 PORT）保持原有行为：127.0.0.1:5000 + debug 自动重载
    _port = int(os.environ.get("PORT", 5000))
    _deployed = bool(os.environ.get("PORT"))
    app.run(host="0.0.0.0" if _deployed else "127.0.0.1",
            port=_port, debug=not _deployed)
