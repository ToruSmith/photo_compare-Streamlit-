# -*- coding: utf-8 -*-
"""
libreoffice_test_app.py

最小驗證用：確認 Streamlit Community Cloud 上能不能透過 packages.txt
成功安裝 LibreOffice，並執行 .doc -> .docx 轉檔。

用法：
  1. 建一個「只放這支 app.py + packages.txt」的獨立測試 repo
  2. 把這支檔案改名成 app.py 上傳部署
  3. 上傳一個 .doc 檔測試，看轉檔會不會成功

確認過關後，再用完整版的 app.py（含完整 pipeline）取代即可。
"""

import os
import subprocess
import streamlit as st

st.title("LibreOffice 轉檔測試")

# 先確認 soffice 有沒有裝起來
which_result = subprocess.run(["which", "soffice"], capture_output=True, text=True)
if which_result.returncode == 0:
    st.success(f"✅ 找到 LibreOffice: {which_result.stdout.strip()}")
else:
    st.error("❌ 找不到 soffice 指令，代表 packages.txt 沒有成功安裝 LibreOffice")

uploaded = st.file_uploader("上傳一個 .doc 檔案測試轉檔", type=["doc"])

if uploaded and st.button("開始轉檔測試"):
    os.makedirs("test_input", exist_ok=True)
    os.makedirs("test_output", exist_ok=True)

    input_path = os.path.join("test_input", uploaded.name)
    with open(input_path, "wb") as f:
        f.write(uploaded.getbuffer())

    with st.spinner("轉檔中..."):
        result = subprocess.run(
            [
                "soffice", "--headless", "--norestore",
                "--convert-to", "docx",
                "--outdir", "test_output",
                input_path,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

    st.write("**Return code:**", result.returncode)
    st.write("**stdout:**")
    st.code(result.stdout or "(空)")
    st.write("**stderr:**")
    st.code(result.stderr or "(空)")

    output_files = os.listdir("test_output")
    if output_files:
        st.success(f"✅ 轉檔成功，產生檔案：{output_files}")
    else:
        st.error("❌ 轉檔失敗，test_output 資料夾內沒有任何檔案")
