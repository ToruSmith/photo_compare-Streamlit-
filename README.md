# 佐證照片比對系統（Streamlit Community Cloud 版）

## 檔案說明

| 檔案 | 用途 |
|---|---|
| `app.py` | 正式版主程式（完整 pipeline，Streamlit 介面） |
| `pipeline.py` | 核心比對邏輯（分類/轉檔/抽圖/pHash/SSIM），與 Gradio 版共用不變 |
| `html_report.py` | HTML 報告產生器，與 Gradio 版共用不變 |
| `requirements.txt` | Python 套件（給 Community Cloud 自動安裝） |
| `packages.txt` | 系統套件，含 LibreOffice（給 Community Cloud 用 apt 安裝） |
| `libreoffice_test_app.py` | **建議先用這支測試** LibreOffice 能否在 Community Cloud 環境正常轉檔 |

## 建議部署順序

### 第一步：先驗證 LibreOffice 能不能裝成功（強烈建議）

1. 開一個新的 GitHub repo（可以先設 private，測完再決定要不要留著）
2. 只放兩個檔案：`libreoffice_test_app.py`（記得改名成 `app.py`）+ `packages.txt`
3. 到 https://share.streamlit.io 部署這個測試 repo
4. 上傳一個 `.doc` 檔案，按「開始轉檔測試」
5. 看畫面顯示轉檔是否成功

如果失敗，畫面上的 stderr 訊息會告訴你是缺套件還是權限問題，可以再調整 `packages.txt`。

### 第二步：確認過關後，部署正式版

1. 把 `app.py`、`pipeline.py`、`html_report.py`、`requirements.txt`、`packages.txt` 這 5 個檔案放進 repo（不需要 `libreoffice_test_app.py`）
2. 到 share.streamlit.io 部署
3. **設定 Private**：部署完成後，在 App 右上角選單找到隱私設定，切換成 Private，並把需要使用的同事 email 加進 viewer 清單

## 跟 Gradio/HF 版本的差異

- 介面元件從 `gr.*` 換成 `st.*`
- 用 `st.session_state` 保留比對結果，避免使用者點下載按鈕時畫面因 Streamlit 重跑機制而消失
- 系統依賴改用 `packages.txt`（apt 套件清單），不再用 Dockerfile
- `pipeline.py` 和 `html_report.py` 完全沒有變動，兩個版本共用同一份核心邏輯

## 已知限制（免費層）

- 記憶體約 1GB，大量或大尺寸照片同時處理可能吃緊
- 閒置 12 小時會休眠，下次開啟需等待喚醒
- 免費層只能設 1 個 Private App，其餘只能公開
- 沒有自訂網域，網址固定為 `你的專案名.streamlit.app`
