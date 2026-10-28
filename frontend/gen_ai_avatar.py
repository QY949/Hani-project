#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 AI 助手头像 ./images/ai_avatar.png（墨绿底 + 金色竹筒/水珠，呼应竹筒倒水主题）。"""
import math
import os

from PIL import Image, ImageDraw

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
OUT_PATH = os.path.join(FRONTEND_DIR, "images", "ai_avatar.png")

W = H = 256
CX = W / 2
CY = H / 2
R = W / 2

# 配色
FOREST_DEEP = (18, 41, 28)      # #12291C
FOREST_LIGHT = (47, 90, 64)     # #2F5A40
BAMBOO = (34, 74, 50)           # 竹身
BAMBOO_HI = (61, 110, 78)       # 竹身高光
GOLD = (212, 175, 55)           # #D4AF37 梯田金黄
GOLD_DK = (168, 134, 43)
WATER = (125, 205, 200)         # 水珠青


def lerp(a, b, t):
    return int(round(a + (b - a) * t))


# --- 1. 径向渐变背景 ---
bg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
px = bg.load()
max_d = W * 0.72
for y in range(H):
    for x in range(W):
        dx = x - CX
        dy = y - CY
        d = min(math.sqrt(dx * dx + dy * dy) / max_d, 1.0)
        r = lerp(FOREST_LIGHT[0], FOREST_DEEP[0], d)
        g = lerp(FOREST_LIGHT[1], FOREST_DEEP[1], d)
        b = lerp(FOREST_LIGHT[2], FOREST_DEEP[2], d)
        px[x, y] = (r, g, b, 255)

# --- 2. 圆形裁剪 ---
circle = Image.new("L", (W, H), 0)
ImageDraw.Draw(circle).ellipse([0, 0, W - 1, H - 1], fill=255)
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
img.paste(bg, (0, 0), circle)

# --- 3. 竹筒图层（倾斜） ---
bamboo_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
bd = ImageDraw.Draw(bamboo_layer)

bx0, by0, bx1, by1 = 78, 34, 132, 150   # 竹身（竖直）
# 竹身（圆角矩形用普通矩形近似 + 高光条）
bd.rounded_rectangle([bx0, by0, bx1, by1], radius=15, fill=BAMBOO)
bd.rounded_rectangle([bx0 + 6, by0 + 6, bx0 + 16, by1 - 6], radius=6, fill=BAMBOO_HI)  # 高光
# 竹节（深色带 + 金线）
for ny in (by0 + 34, by0 + 78):
    bd.rectangle([bx0, ny - 7, bx1, ny + 7], fill=(20, 46, 31))
    bd.line([(bx0, ny), (bx1, ny)], fill=GOLD_DK, width=2)
# 顶端切口（椭圆）
bd.ellipse([bx0, by0 - 8, bx1, by0 + 12], fill=(14, 36, 24))
bd.ellipse([bx0 + 8, by0 - 4, bx1 - 8, by0 + 8], fill=(9, 26, 17))

# 倾斜竹筒
bamboo = bamboo_layer.rotate(-20, resample=Image.BICUBIC, center=(CX, CY))
img.alpha_composite(bamboo)

# --- 4. 水珠（金/青渐变小滴，位于竹口下方） ---
drop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
dd = ImageDraw.Draw(drop)
dcx, dcy = 150, 150
dd.ellipse([dcx - 16, dcy - 4, dcx + 16, dcy + 28], fill=WATER)      # 水滴下半
dd.polygon([(dcx - 16, dcy + 4), (dcx + 16, dcy + 4), (dcx, dcy - 22)], fill=WATER)  # 尖头
dd.ellipse([dcx - 6, dcy - 2, dcx + 2, dcy + 8], fill=(200, 240, 236))  # 高光
img.alpha_composite(drop)

# --- 5. 金色细边环 ---
ring = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(ring).ellipse([4, 4, W - 5, H - 5], outline=GOLD, width=4)
img.alpha_composite(ring)

img.save(OUT_PATH)
print("saved:", OUT_PATH, img.size)
