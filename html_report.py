# -*- coding: utf-8 -*-
"""
html_report.py

負責把比對結果組裝成單一可攜式 HTML 報告（照片以 base64 內嵌）。
獨立於 pipeline 邏輯之外，方便日後替換成別種報告格式（例如 Excel）。
"""

import os
import base64
import io
from datetime import datetime
from typing import List, Tuple


def image_to_base64_thumbnail(image_path: str, max_size: int = 320) -> str:
    """讀取照片、等比例縮小、轉成 base64 字串。讀取失敗回傳空字串。"""
    try:
        from PIL import Image
        img = Image.open(image_path)
        img = img.convert("RGB")
        img.thumbnail((max_size, max_size))
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=82)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"警告：縮圖產生失敗 {image_path} ({e})")
        return ""


def generate_html_report(
    results_list: List[Tuple[str, str, int, float]],
    all_photo_names: List[str],
    extracted_images_dir: str,
    output_path: str,
):
    """
    Args:
        results_list: [(檔名1, 檔名2, distance, percentage), ...]
        all_photo_names: 本次參與比對的所有照片檔名
        extracted_images_dir: 照片實際所在資料夾路徑
        output_path: 輸出 HTML 檔案的完整路徑
    """
    exec_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sorted_results = sorted(results_list, key=lambda x: x[3], reverse=True)

    exact_count = sum(1 for r in sorted_results if r[2] == 0)
    similar_count = len(sorted_results) - exact_count

    cards_html = ""
    for filename1, filename2, distance, percentage in sorted_results:
        img1_path = os.path.join(extracted_images_dir, filename1)
        img2_path = os.path.join(extracted_images_dir, filename2)
        b64_1 = image_to_base64_thumbnail(img1_path)
        b64_2 = image_to_base64_thumbnail(img2_path)

        is_exact = (distance == 0)
        card_class = "card exact" if is_exact else "card similar"
        badge_text = "完全相同" if is_exact else "疑似相似"
        badge_class = "badge-exact" if is_exact else "badge-similar"

        def _img_tag(b64, name):
            if b64:
                return f'<img src="data:image/jpeg;base64,{b64}" alt="{name}">'
            return '<div class="no-image">無法載入縮圖</div>'

        cards_html += f"""
        <div class="{card_class}">
            <div class="card-header">
                <span class="badge {badge_class}">{badge_text}</span>
                <span class="score">相似度 {round(percentage, 2)}% ・ 距離 {distance}</span>
            </div>
            <div class="pair">
                <div class="photo-box">
                    {_img_tag(b64_1, filename1)}
                    <div class="filename">{filename1}</div>
                </div>
                <div class="vs">vs</div>
                <div class="photo-box">
                    {_img_tag(b64_2, filename2)}
                    <div class="filename">{filename2}</div>
                </div>
            </div>
        </div>
        """

    if not sorted_results:
        cards_html = '<div class="empty-state">本次比對未發現任何疑似重複的照片。</div>'

    photo_list_html = "".join(f"<li>{name}</li>" for name in sorted(all_photo_names))

    html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<title>佐證照片比對報告</title>
<style>
    body {{ font-family: "Noto Sans CJK TC", "Microsoft JhengHei", sans-serif;
            background: #f5f6f8; color: #2c2c2c; margin: 0; padding: 24px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    h1 {{ font-size: 22px; margin-bottom: 4px; }}
    .disclaimer {{ background: #fff8e1; border: 1px solid #f0dca0; border-radius: 6px;
                   padding: 12px 16px; font-size: 13px; line-height: 1.7; color: #5c4a13;
                   margin: 12px 0 20px 0; }}
    .summary {{ background: #ffffff; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.08); font-size: 14px; line-height: 1.8; }}
    .summary b {{ color: #1a73e8; }}
    .exec-time {{ color: #888; font-size: 12px; }}
    .card {{ background: #fff; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px;
             box-shadow: 0 1px 3px rgba(0,0,0,0.08); border-left: 5px solid #f0a500; }}
    .card.exact {{ border-left: 5px solid #e53935; }}
    .card-header {{ display: flex; justify-content: space-between; align-items: center;
                    margin-bottom: 10px; font-size: 13px; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; color: #fff; }}
    .badge-exact {{ background: #e53935; }}
    .badge-similar {{ background: #f0a500; }}
    .score {{ color: #555; }}
    .pair {{ display: flex; align-items: flex-start; gap: 12px; }}
    .photo-box {{ flex: 1; text-align: center; }}
    .photo-box img {{ max-width: 100%; max-height: 220px; border-radius: 6px; border: 1px solid #ddd; }}
    .no-image {{ padding: 40px 0; color: #aaa; border: 1px dashed #ccc; border-radius: 6px; font-size: 13px; }}
    .filename {{ margin-top: 6px; font-size: 12px; color: #555; word-break: break-all; }}
    .vs {{ align-self: center; color: #999; font-size: 13px; padding-top: 90px; }}
    .empty-state {{ background: #fff; border-radius: 8px; padding: 30px; text-align: center; color: #888; }}
    details {{ margin-top: 24px; background: #fff; border-radius: 8px; padding: 12px 18px;
               box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
    summary {{ cursor: pointer; font-size: 14px; color: #444; }}
    ul {{ columns: 2; font-size: 12px; color: #666; line-height: 1.8; }}
</style>
</head>
<body>
<div class="container">
    <h1>🏠 佐證照片比對報告</h1>
    <div class="disclaimer">
        本系統係基於感知雜湊（pHash）演算法之「輔助比對工具」。<br>
        系統所提供之相似度數值，僅供業務主管單位作為抽查與複核之決策參考，不具備法律之上之最終判定效力。<br>
        施工照片之真實性審查、現場查核以及最終結果之核定，其行政管理責任仍歸屬於【業務主辦/審核單位】。
    </div>

    <div class="summary">
        <div class="exec-time">執行時間：{exec_time}</div>
        本次比對共 <b>{len(all_photo_names)}</b> 張照片，發現 <b>{len(sorted_results)}</b> 組疑似重複
        （其中完全相同 <b>{exact_count}</b> 組、僅相似 <b>{similar_count}</b> 組）。
    </div>

    {cards_html}

    <details>
        <summary>參與此次比對所有照片檔名（共 {len(all_photo_names)} 張，點擊展開）</summary>
        <ul>{photo_list_html}</ul>
    </details>
</div>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return output_path
