#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_json.py —— 把数据库词汇导出为前端可用的 JSON
====================================================

读取 backend/ich_data.db 的 vocabulary 新表，输出到
frontend/vocab_data.json，格式与 language.js 期望的
{ cat, zh, mian, script, bunu, lajia } 保持一致（向后兼容）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from init_db import DB_PATH, get_connection  # noqa: E402

OUTPUT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "vocab_data.json")
)

# 新分类 -> 旧前端分类码
LEGACY_CAT_MAP = {"农耕": "farming", "称谓": "greeting", "文化习俗": "greeting"}


def main():
    conn = get_connection(DB_PATH)
    rows = conn.execute("SELECT * FROM vocabulary ORDER BY id").fetchall()
    conn.close()

    result = []
    for row in rows:
        is_hani = row["ethnic_group"] == "哈尼族"
        result.append({
            "cat": LEGACY_CAT_MAP.get(row["category"], "life"),
            "zh": row["meaning"],
            "mian": row["word"] if is_hani else "",
            "script": row["word"] if is_hani else "",
            "bunu": "",
            "lajia": "",
        })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)

    print("🎉 导出成功！共计 {} 条数据 -> {}".format(len(result), OUTPUT_PATH))


if __name__ == "__main__":
    main()
