# -*- coding: utf-8 -*-
"""
pipeline.py

核心比對邏輯，改寫自原本 main.py 的 Eel 版本，重點差異：
  1. doc_to_docx()：win32com → subprocess 呼叫 LibreOffice headless（Linux 相容）
  2. 拿掉所有 @eel.expose，改成一般函式
  3. 拿掉 global time_stamp_dir，改成明確傳遞 job_dir 參數（每次上傳互不干擾）
  4. 拿掉 SQLite 建庫（buildDB），因為單次上傳→處理→下載的場景用不到
  5. 路徑一律用 os.path.join，不寫死 Windows 反斜線
"""

import os
import subprocess
import time
from typing import Dict, List, Tuple
from zipfile import ZipFile

import cv2
import imagehash
import numpy as np
from fitz import open as fitzopen
from PIL import Image
from skimage.metrics import structural_similarity as ssim

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".jfif", ".tif", ".tiff")
COMPARISON_THRESHOLD = 15  # pHash 漢明距離門檻
SSIM_THRESHOLD = 60.0      # SSIM 相似度門檻（百分比）


# ============================================================
# Step 1：依副檔名分類上傳檔案到 job_dir 底下的子資料夾
# ============================================================
def classify_uploaded_files(uploaded_file_paths: List[str], job_dir: str) -> Dict[str, str]:
    sub_dirs = {
        "doc": os.path.join(job_dir, "doc"),
        "docx": os.path.join(job_dir, "docx"),
        "pdf": os.path.join(job_dir, "pdf"),
        "xlsx": os.path.join(job_dir, "xlsx"),
        "extracted_images": os.path.join(job_dir, "extracted_images"),
    }
    for d in sub_dirs.values():
        os.makedirs(d, exist_ok=True)

    for src_path in uploaded_file_paths:
        filename = os.path.basename(src_path)
        ext = filename.split(".")[-1].lower()

        if ext == "doc":
            dest = os.path.join(sub_dirs["doc"], filename)
        elif ext == "docx":
            dest = os.path.join(sub_dirs["docx"], filename)
        elif ext == "pdf":
            dest = os.path.join(sub_dirs["pdf"], filename)
        elif ext == "xlsx":
            dest = os.path.join(sub_dirs["xlsx"], filename)
        elif ext.lower() in ("jpg", "jpeg", "png", "gif", "tif", "tiff", "bmp", "jfif"):
            dest = os.path.join(sub_dirs["extracted_images"], filename)
        else:
            print(f"檔案格式不符合需求，跳過處理: {filename}")
            continue

        with open(src_path, "rb") as fsrc, open(dest, "wb") as fdst:
            fdst.write(fsrc.read())

    return sub_dirs


# ============================================================
# Step 2：.doc 轉 .docx（改用 LibreOffice headless，取代 win32com）
# ============================================================
def convert_doc_to_docx(doc_dir: str, docx_dir: str):
    if not os.path.isdir(doc_dir):
        return
    for filename in os.listdir(doc_dir):
        if not filename.lower().endswith(".doc"):
            continue
        src_path = os.path.join(doc_dir, filename)
        print(f"正在用 LibreOffice 轉檔: {filename}")
        try:
            subprocess.run(
                [
                    "soffice", "--headless", "--norestore",
                    "--convert-to", "docx",
                    "--outdir", docx_dir,
                    src_path,
                ],
                check=True,
                timeout=120,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"LibreOffice 轉檔失敗: {filename} ({e.stderr})")
        except subprocess.TimeoutExpired:
            print(f"LibreOffice 轉檔逾時: {filename}")


# ============================================================
# Step 3：從 PDF 抽取內嵌照片
# ============================================================
def extract_images_from_pdf(pdf_path: str, output_dir: str, prefix: str):
    pdf_document = fitzopen(pdf_path)
    for page_number in range(len(pdf_document)):
        page = pdf_document.load_page(page_number)
        image_list = page.get_images(full=True)
        for image_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_filename = os.path.join(
                output_dir, f"{prefix}_page_{page_number + 1}_image_{image_index + 1}.jpeg"
            )
            with open(image_filename, "wb") as img_file:
                img_file.write(image_bytes)
    pdf_document.close()


def extract_all_pdfs(pdf_dir: str, output_dir: str):
    if not os.path.isdir(pdf_dir):
        return
    for pdf in os.listdir(pdf_dir):
        full_path = os.path.join(pdf_dir, pdf)
        file_name = os.path.splitext(pdf)[0]
        try:
            extract_images_from_pdf(full_path, output_dir, file_name)
        except Exception as e:
            print(f"PDF 抽圖失敗: {pdf} ({e})")


# ============================================================
# Step 4：從 DOCX 抽取內嵌照片（docx 本質是 zip 檔）
# ============================================================
def extract_images_from_docx(file_name: str, docx_path: str, output_dir: str):
    with ZipFile(docx_path, "r") as docx_zip:
        for zip_name in docx_zip.namelist():
            if zip_name.startswith("word/media/") and not zip_name.endswith(".emf"):
                docx_zip.extract(zip_name, output_dir)
                extracted_path = os.path.join(output_dir, zip_name)
                new_file_name = file_name + os.path.basename(extracted_path)
                new_path = os.path.join(output_dir, new_file_name)
                os.rename(extracted_path, new_path)


def extract_all_docxs(docx_dir: str, output_dir: str):
    if not os.path.isdir(docx_dir):
        return
    for docx in os.listdir(docx_dir):
        full_path = os.path.join(docx_dir, docx)
        file_name = os.path.splitext(docx)[0]
        try:
            extract_images_from_docx(file_name, full_path, output_dir)
        except Exception as e:
            print(f"DOCX 抽圖失敗: {docx} ({e})")

    # 清除 zip 解壓縮殘留的 word/ 資料夾
    leftover = os.path.join(output_dir, "word")
    if os.path.isdir(leftover):
        import shutil
        shutil.rmtree(leftover, ignore_errors=True)


# ============================================================
# Step 5：從 XLSX 抽取內嵌照片
# ============================================================
def extract_images_from_xlsx(xlsx_path: str, output_dir: str):
    excel_name = os.path.splitext(os.path.basename(xlsx_path))[0]
    with ZipFile(xlsx_path, "r") as zip_ref:
        for file_name in zip_ref.namelist():
            if file_name.startswith("xl/media/"):
                img_data = zip_ref.read(file_name)
                img_name = os.path.join(output_dir, excel_name + "_" + os.path.basename(file_name))
                with open(img_name, "wb") as img_file:
                    img_file.write(img_data)


def extract_all_xlsxs(xlsx_dir: str, output_dir: str):
    if not os.path.isdir(xlsx_dir):
        return
    for file in os.listdir(xlsx_dir):
        full_path = os.path.join(xlsx_dir, file)
        try:
            extract_images_from_xlsx(full_path, output_dir)
        except Exception as e:
            print(f"XLSX 抽圖失敗: {file} ({e})")


# ============================================================
# Step 6：pHash 初篩
# ============================================================
def load_and_hash_photos(directory: str) -> Dict[str, imagehash.ImageHash]:
    photo_hashes: Dict[str, imagehash.ImageHash] = {}
    for root, _, files in os.walk(directory):
        for filename in files:
            if filename.lower().endswith(PHOTO_EXTENSIONS):
                full_path = os.path.join(root, filename)
                try:
                    img = Image.open(full_path)
                    photo_hashes[filename] = imagehash.phash(img)
                    img.close()
                except Exception as e:
                    print(f"警告：無法處理檔案 {filename} ({e})")
    return photo_hashes


def find_similar_photos(
    photo_hashes: Dict[str, imagehash.ImageHash],
    threshold: int = COMPARISON_THRESHOLD,
) -> List[Tuple[str, str, int]]:
    filenames = list(photo_hashes.keys())
    hashes = list(photo_hashes.values())
    num_photos = len(filenames)
    similar_pairs = []

    start_time = time.time()
    for i in range(num_photos):
        for j in range(i + 1, num_photos):
            distance = hashes[i] - hashes[j]
            if distance <= threshold:
                similar_pairs.append((filenames[i], filenames[j], distance))
    print(f"pHash 比對完成，耗時 {time.time() - start_time:.2f} 秒，共 {len(similar_pairs)} 組候選")
    return similar_pairs


# ============================================================
# Step 7：SSIM 複篩
# ============================================================
def cv_imread_chinese_path(file_path):
    """安全讀取含中文路徑的圖片。"""
    try:
        with open(file_path, "rb") as f:
            binary_data = f.read()
        np_array = np.frombuffer(binary_data, np.uint8)
        img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        if img is None:
            print(f"警告：成功讀取檔案但無法解碼: {file_path}")
        return img
    except Exception as e:
        print(f"讀取或解碼圖片時發生錯誤：{e}")
        return None


def compare_images(pair: Tuple[str, str, int], extracted_images_dir: str):
    """pair: (檔名1, 檔名2, distance)。回傳 (檔名1, 檔名2, distance, percentage) 或 None。"""
    filename1, filename2, distance = pair
    img1_path = os.path.join(extracted_images_dir, filename1)
    img2_path = os.path.join(extracted_images_dir, filename2)
    try:
        img1 = cv_imread_chinese_path(img1_path)
        img2 = cv_imread_chinese_path(img2_path)

        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)

        h = min(gray1.shape[0], gray2.shape[0])
        w = min(gray1.shape[1], gray2.shape[1])
        gray1 = cv2.resize(gray1, (w, h))
        gray2 = cv2.resize(gray2, (w, h))

        score, _ = ssim(gray1, gray2, full=True)
        percentage = score * 100

        if percentage > SSIM_THRESHOLD:
            return (filename1, filename2, distance, percentage)
        return None
    except Exception as e:
        print(f"SSIM 比對失敗 {filename1} vs {filename2}: {e}")
        return None


# ============================================================
# 整合 pipeline：從上傳檔案到比對結果
# ============================================================
def run_pipeline(uploaded_file_paths: List[str], job_dir: str, progress_callback=None):
    """
    progress_callback(fraction: float, desc: str) 用於回報進度給前端（Gradio Progress）。
    回傳: (result_list, all_photo_names, extracted_images_dir)
    """
    def _report(fraction, desc):
        if progress_callback:
            progress_callback(fraction, desc)
        print(f"[{int(fraction*100)}%] {desc}")

    _report(0.05, "分類上傳檔案...")
    sub_dirs = classify_uploaded_files(uploaded_file_paths, job_dir)
    extracted_dir = sub_dirs["extracted_images"]

    _report(0.15, "轉換 .doc 為 .docx...")
    convert_doc_to_docx(sub_dirs["doc"], sub_dirs["docx"])

    _report(0.35, "從 PDF 抽取照片...")
    extract_all_pdfs(sub_dirs["pdf"], extracted_dir)

    _report(0.55, "從 DOCX 抽取照片...")
    extract_all_docxs(sub_dirs["docx"], extracted_dir)

    _report(0.65, "從 XLSX 抽取照片...")
    extract_all_xlsxs(sub_dirs["xlsx"], extracted_dir)

    _report(0.75, "計算照片 pHash 指紋...")
    photo_hashes = load_and_hash_photos(extracted_dir)

    _report(0.85, "初篩相似照片對...")
    candidate_pairs = find_similar_photos(photo_hashes, COMPARISON_THRESHOLD)

    _report(0.92, "SSIM 複篩比對中...")
    result_list = []
    for pair in candidate_pairs:
        result = compare_images(pair, extracted_dir)
        if result is not None:
            result_list.append(result)

    _report(1.0, "比對完成")
    return result_list, list(photo_hashes.keys()), extracted_dir
