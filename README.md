
## ✨ 主要功能

* **圖片違規偵測:** 上傳工地照片，自動使用 YOLOv5 模型偵測是否有人未戴安全帽。
* **法規關聯與摘要:** 若偵測到違規，自動從向量資料庫搜尋相關安全法規，並利用 LLM (Llama 3) 生成摘要回覆。
* **歷史紀錄查詢:** 可透過 Line 輸入自然語言指令 (如 "查詢今天違規") 來查詢指定時間範圍內的違規紀錄。
* **資料庫儲存:** 將偵測到的違規事件 (時間、類型、圖片路徑) 記錄於 MySQL 資料庫。
* **容器化部署:** 使用 Docker Compose 整合所有服務 (Flask App, YOLO, MySQL, ChromaDB, Ollama)，方便部署。

## 🛠️ 使用技術

* **後端:** Python, Flask
* **電腦視覺:** YOLOv5 (via PyTorch), OpenCV
* **自然語言處理/生成:** Ollama (Llama 3), LangChain, Hugging Face Sentence Transformers
* **資料庫:** MySQL, ChromaDB
* **通訊:** Line Bot SDK
* **部署/環境:** Docker, Docker Compose
* **其他:** Git, Ngrok (開發用)

## 🛠️ 操作
設置好環境變數後
docker-compose up -d --build                                                    建立容器環境
docker ps                                                                       檢查容器啟動是否正常
docker exec -it <flask_container_name_or_id> python core/scrape_clean_mysql.py  爬取法條
docker exec -it <flask_container_name_or_id> python core/vectorization.py       對資料做向量化
docker exec -it <ollama_container_name_or_id> ollama pull llama3:8b             下載ollama模型
docker logs ngrok_service                                                       找到URL 複製到LINE webhook上 然後貼上後面+上/callback
docker down                                                                     停止容器服務




## 🚀 Demo 演示

* **操作影片:** [點這裡觀看操作影片](https://youtu.be/R9Nou-espa4) <-- ⭐ 提供影片連結！
