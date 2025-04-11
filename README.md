
# 工地安全智慧監控系統 README

## 📝 專案簡介

本專案旨在利用 AI 技術提升工地安全管理效率。透過影像辨識技術自動偵測工人的安全裝備穿戴情況（初期以安全帽為主），並結合大型語言模型提供相關法規摘要，同時記錄違規事件以便追蹤管理。系統透過 Line Bot 進行互動，方便現場人員操作。

## ✨ 主要功能

* **AI 違規偵測 (AI Violation Detection):**
    * 使用者可透過 Line Bot 上傳工地現場照片。
    * 系統使用 YOLOv5 模型自動偵測照片中是否有人員未佩戴安全帽。
* **智慧法規關聯與摘要 (Intelligent Regulation Linking & Summarization):**
    * 自動從「全國法規資料庫」爬取相關安全法規。
    * 將法規條文進行向量化處理，儲存於 ChromaDB 向量資料庫。
    * 當偵測到違規事件（如未戴安全帽）時，系統會從向量資料庫中檢索最相關的法規條文。
    * 利用本地部署的 Llama 3 大型語言模型（透過 Ollama）生成相關法規的重點摘要，並回傳給使用者。
* **Line Bot 互動查詢 (Line Bot Interaction & Query):**
    * 使用者可以透過 Line 輸入自然語言指令查詢歷史違規紀錄。
    * 例如：輸入「查詢今天的違規紀錄」、「查詢本週未戴安全帽事件」。
* **歷史紀錄儲存 (History Logging):**
    * 所有偵測到的違規事件（包含時間戳、違規類型、關聯圖片路徑等資訊）將被記錄在 MySQL 資料庫中，方便後續查詢與分析。
* **容器化部署 (Containerized Deployment):**
    * 使用 Docker Compose 整合所有服務元件（Flask Web 應用、YOLOv5 偵測服務、MySQL 資料庫、ChromaDB 向量資料庫、Ollama LLM 服務）。
    * 簡化部署流程，確保環境一致性。
* **可擴展性 (Potential Enhancements):**
    * 目前的 YOLOv5 模型主要偵測安全帽，未來可透過訓練更進階或客製化的模型，擴展偵測能力至其他違規項目，例如：
        * 是否穿著反光背心。
        * 是否在工地飲用特定飲品（如：保力達 B、酒精飲料）。
        * 偵測其他危險行為或不合規物品。
        * 不再是上傳資料庫而是及時連接監視器
        * 爬取的法規可以變更

## 🛠️ 使用技術

* **後端框架:** Python, Flask
* **電腦視覺:** YOLOv5 (PyTorch), OpenCV
* **自然語言處理/生成:** Ollama (運行 Llama 3), LangChain, Hugging Face Sentence Transformers (用於向量化)
* **資料庫:**
    * 關聯式資料庫: MySQL (儲存違規紀錄)
    * 向量資料庫: ChromaDB (儲存法規向量)
* **通訊介面:** Line Bot SDK for Python
* **部署與環境:** Docker, Docker Compose
* **開發輔助:** Git (版本控制), Ngrok (開發階段用於建立公開網址以接收 Line Webhook)

## ⚙️ 環境準備 (Prerequisites)

在開始之前，請確保您的系統已安裝以下軟體：

* Git
* Docker
* Docker Compose

## 🚀 安裝與設定 (Installation & Setup)

1.  **下載專案程式碼 (Clone Repository):**
    ```bash
    git clone <你的專案 Git Repository URL>
    cd <專案目錄>
    ```

2.  **設定環境變數 (Configure Environment Variables):**
    * 專案根目錄下通常會有一個 `.env.example` 或類似的範例檔案。
    * 複製一份並命名為 `.env`。
    * ```bash
      cp .env.example .env
      ```
    * 編輯 `.env` 文件，填入必要的設定值，例如：
        * Line Bot 的 `Channel Access Token` 和 `Channel Secret`。
        * MySQL 資料庫的連線資訊（用戶名、密碼、資料庫名稱）。
        * (若有其他需要配置的 API 金鑰或參數)

3.  **建立並啟動 Docker 容器 (Build and Start Containers):**
    * 此指令會根據 `docker-compose.yml` 的設定，建立映像檔並在背景啟動所有服務容器。
    * ```bash
      docker-compose up -d --build
      ```
    * 初次建立映像檔可能需要一些時間，請耐心等候。

## ▶️ 首次執行與初始化 (First Run & Initialization)

容器啟動後，需要執行一些初始化步驟：

1.  **檢查容器狀態 (Check Container Status):**
    * 確認所有服務（Flask App, MySQL, ChromaDB, Ollama, Ngrok）是否都正常運行中 (狀態應為 `Up`)。
    * ```bash
      docker ps
      ```
    * 記下 Flask App 容器的名稱或 ID (例如：`yourproject_flask_app_1`) 以及 Ollama 容器的名稱或 ID (例如：`yourproject_ollama_1`)，後續指令會用到。

2.  **爬取法規資料並存入 MySQL (Scrape Regulations):**
    * 進入 Flask App 容器內執行爬蟲腳本。
    * 將 `<flask_container_name_or_id>` 替換為您在上一步記下的 Flask App 容器名稱或 ID。
    * ```bash
      docker exec -it <flask_container_name_or_id> python core/scrape_clean_mysql.py
      ```

3.  **向量化法規資料並存入 ChromaDB (Vectorize Regulations):**
    * 進入 Flask App 容器內執行向量化腳本。
    * ```bash
      docker exec -it <flask_container_name_or_id> python core/vectorization.py
      ```

4.  **下載 LLM 模型 (Download LLM Model):**
    * 進入 Ollama 容器內下載 Llama 3 模型。
    * 將 `<ollama_container_name_or_id>` 替換為您在上一步記下的 Ollama 容器名稱或 ID。
    * ```bash
      docker exec -it <ollama_container_name_or_id> ollama pull llama3:8b
      ```
    * (若您在 `docker-compose.yml` 或 Ollama 設定中指定了不同的模型，請下載對應模型)

5.  **設定 Line Webhook (Configure Line Webhook):**
    * Ngrok 服務會在 Docker 啟動時自動運行，並產生一個公開的 HTTPS 網址，用於接收 Line 平台傳來的訊息。
    * 查看 Ngrok 服務的日誌以取得該網址。
    * ```bash
      docker logs ngrok_service
      ```
    * 在日誌中找到類似 `Forwarding https://xxxx-xxxx-xxxx.ngrok-free.app -> http://flask_app:5000` 的訊息。
    * 複製 `https://xxxx-xxxx-xxxx.ngrok-free.app` 這個 HTTPS 網址。
    * 前往您的 Line Developer Console，找到您的 Line Bot 設定頁面。
    * 在 "Messaging API" 設定中，找到 "Webhook URL" 欄位。
    * 貼上您複製的 Ngrok HTTPS 網址，並在其後加上 `/callback` 路徑。
        * 完整 Webhook URL 應為：`https://xxxx-xxxx-xxxx.ngrok-free.app/callback`
    * 啟用 Webhook (`Use webhook` 開關)。

## 💡 日常使用 (Usage)

1.  **透過 Line Bot 上傳照片:** 將工地現場照片傳送給您的 Line Bot。系統會自動進行偵測。
2.  **接收偵測結果與法規摘要:** 若偵測到未戴安全帽等違規情況，Bot 會回傳標註後的圖片以及相關法規摘要。
3.  **查詢歷史紀錄:** 在 Line Bot 對話框中輸入自然語言指令，如：「查詢昨天違規」、「列出這週未戴安全帽的事件」。

## 🚀 Demo 演示

* **操作影片:** [點這裡觀看操作影片](在此處插入您的影片連結) <-- ⭐ 請務必提供實際的影片連結！
