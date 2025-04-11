# 1. 使用官方 Python 映像檔
FROM python:3.9-slim

# 2. 設定工作目錄
WORKDIR /app

# 3. 安裝系統依賴（例如 OpenCV 可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. 複製依賴文件
COPY requirements.txt .

# 5. 安裝 Python 依賴（使用 --no-cache-dir 減少映像檔大小）
RUN pip install --no-cache-dir -r requirements.txt
# 如果需要 CPU 版本的 torch/torchvision，可以取消下面這行的註解
# RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 6. 複製專案程式碼到映像檔中
COPY . .

# 7. 暴露 Flask App 的端口
EXPOSE 4040

# 8. 設定容器啟動時執行的命令
CMD ["python", "linebot_handler.py"]