# -*- coding: utf-8 -*-
"""
app.py (Streamlit Community Cloud 版)

跟 Gradio 版的差異：
  - 介面元件全部換成 st.* (file_uploader / button / progress / components.v1.html)
  - Streamlit 每次互動都會重跑整支腳本，所以比對結果要存進 st.session_state，
    避免使用者點「下載報告」按鈕時，畫面上的報告因為重跑而消失
  - pipeline.py / html_report.py 完全沿用，不需修改
"""

import os
import shutil
import uuid
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from pipeline import run_pipeline
from html_report import generate_html_report

JOBS_ROOT = os.path.join(os.getcwd(), "jobs")
os.makedirs(JOBS_ROOT, exist_ok=True)

st.set_page_config(page_title="佐證照片比對系統", page_icon="🏠", layout="wide")


def cleanup_old_jobs(keep_latest: int = 20):
    try:
        jobs = sorted(
            (os.path.join(JOBS_ROOT, d) for d in os.listdir(JOBS_ROOT)),
            key=os.path.getmtime,
        )
        for old_job in jobs[:-keep_latest]:
            shutil.rmtree(old_job, ignore_errors=True)
    except Exception as e:
        print(f"清理舊 job 失敗: {e}")


def save_uploaded_files(uploaded_files, dest_dir: str):
    """Streamlit 的 UploadedFile 物件要先寫到磁碟，pipeline.py 才能用路徑處理。"""
    os.makedirs(dest_dir, exist_ok=True)
    saved_paths = []
    for uf in uploaded_files:
        path = os.path.join(dest_dir, uf.name)
        with open(path, "wb") as f:
            f.write(uf.getbuffer())
        saved_paths.append(path)
    return saved_paths


# ---------------- 版面 ----------------
st.title("🏠 佐證照片比對系統")
st.markdown(
    """
本系統係基於感知雜湊（pHash）+ 結構相似性（SSIM）演算法之「輔助比對工具」。
系統所提供之相似度數值，僅供業務主管單位作為抽查與複核之決策參考，不具備法律之上之最終判定效力。
施工照片之真實性審查、現場查核以及最終結果之核定，其行政管理責任仍歸屬於【業務主辦/審核單位】。
"""
)

uploaded_files = st.file_uploader(
    "上傳施工紀錄文件（.doc / .docx / .pdf / .xlsx，或直接上傳照片 .jpg/.png）",
    accept_multiple_files=True,
)

run_clicked = st.button("開始比對", type="primary", disabled=not uploaded_files)

if run_clicked and uploaded_files:
    cleanup_old_jobs()

    job_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    job_dir = os.path.join(JOBS_ROOT, job_id)
    upload_dir = os.path.join(job_dir, "_uploads")

    progress_bar = st.progress(0, text="準備中...")

    def _progress_callback(fraction, desc):
        progress_bar.progress(min(fraction, 1.0), text=desc)

    try:
        saved_paths = save_uploaded_files(uploaded_files, upload_dir)
        result_list, all_photo_names, extracted_dir = run_pipeline(
            saved_paths, job_dir, progress_callback=_progress_callback
        )

        report_path = os.path.join(job_dir, "比對結果.html")
        generate_html_report(result_list, all_photo_names, extracted_dir, report_path)

        with open(report_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 存進 session_state，避免下載按鈕觸發重跑後畫面消失
        st.session_state["report_html"] = html_content
        st.session_state["report_path"] = report_path

        progress_bar.progress(1.0, text="比對完成")

    except Exception as e:
        st.error(f"處理過程發生錯誤：{e}")

# ---------------- 顯示報告（若已存在於 session_state） ----------------
if "report_html" in st.session_state:
    st.subheader("比對報告")
    components.html(st.session_state["report_html"], height=800, scrolling=True)

    with open(st.session_state["report_path"], "rb") as f:
        st.download_button(
            label="下載 HTML 報告",
            data=f.read(),
            file_name="比對結果.html",
            mime="text/html",
        )
