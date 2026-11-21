"""PNG 아이콘 생성 (홈 화면 추가용). icon.svg 와 같은 모양을 Pillow 로 그림."""
from PIL import Image, ImageDraw, ImageFont
import os
def draw(size):
    s = size / 512
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(96 * s), fill="#1c5d99")
    # 핀: 원 + 아래 삼각형
    d.ellipse([130 * s, 92 * s, 382 * s, 344 * s], fill="white")
    d.polygon([(150 * s, 270 * s), (362 * s, 270 * s), (256 * s, 428 * s)], fill="white")
    d.ellipse([194 * s, 156 * s, 318 * s, 280 * s], fill="#e03131")
    try:
        f = ImageFont.truetype("arialbd.ttf", int(76 * s))
    except OSError:
        f = ImageFont.load_default()
    d.text((256 * s, 218 * s), "₩", fill="white", font=f, anchor="mm")
    return im
for n in (180, 192, 512):
    draw(n).save(f"site/icons/icon-{n}.png")
print(os.listdir("site/icons"))
