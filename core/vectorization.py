import mysql.connector
# --- Langchain v0.2+ 建議的 import 方式 ---
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
# from langchain.embeddings import HuggingFaceEmbeddings # 舊方式
# from langchain.vectorstores import Chroma # 舊方式
# ----------------------------------------
from langchain.schema import Document
import os
from dotenv import load_dotenv
import logging # 引入 logging

load_dotenv()

# --- 設定基本 logging ---
# (與 linebot_handler.py 類似，方便統一查看)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# --- 全域的 db_config (從環境變數讀取) ---
# 這是正確的，fetch_data_from_mysql 應該要用這個
db_config = {
    'host': os.getenv('MYSQL_HOST', 'mysql'), # 在容器內執行時用服務名
    'user': os.getenv('MYSQL_USER', 'kingsley'),
    'password': os.getenv('MYSQL_PASSWORD', 'ji394djp4'),
    'database': os.getenv('MYSQL_DATABASE', 'kingsley_db'),
    # 從環境變數讀取 Port，並轉成整數，預設 3306
    'port': int(os.getenv('MYSQL_PORT', 3306)) 
}
logging.info(f"資料庫設定 (vectorization): {db_config}")


# ✅ 1️⃣ **從 MySQL 中讀取數據 (修正版)**
def fetch_data_from_mysql():
    """
    從 MySQL 資料庫中讀取條文數據。
    使用全域的 db_config 設定。
    """
    logging.info("🔍 正在從 MySQL 中讀取數據...")
    # ***【修正】*** 不再重新定義區域的 db_config，直接使用全域的
    # print(f"    連接資訊: {db_config}") # 可以取消註解再次確認
    
    conn = None  # 初始化 conn
    cursor = None # 初始化 cursor
    try:
        # 使用全域的 db_config 連接
        conn = mysql.connector.connect(**db_config) 
        logging.info("    ✅ 資料庫連接成功。")
        cursor = conn.cursor(dictionary=True)
        logging.info("    執行查詢: SELECT id, chapter, article_number, content FROM articles")
        cursor.execute("SELECT id, chapter, article_number, content FROM articles")
        
        # --- 加入更詳細的檢查 ---
        row_count = cursor.rowcount # rowcount 可能返回 -1，表示無法確定
        logging.info(f"    查詢執行完成。 cursor.rowcount = {row_count}")
        
        rows = cursor.fetchall() # 讀取所有結果
        
        logging.info(f"    fetchall() 完成。實際讀取到的記錄數: {len(rows)}")
        # --- 結束詳細檢查 ---
        
        logging.info(f"✅ 成功讀取 {len(rows)} 條記錄。")
        return rows

    except mysql.connector.Error as err:
        logging.error(f"❌ MySQL 錯誤 (fetch_data_from_mysql): {err}")
        return [] # 出錯時返回空列表
    except Exception as e: # 捕捉其他可能的錯誤
        logging.error(f"❌ 讀取 MySQL 時發生非預期錯誤: {e}", exc_info=True) # 顯示詳細錯誤追蹤
        return []
    finally:
        # ***【修正】*** 關閉前先檢查是否存在
        if cursor:
            try:
                cursor.close()
            except Exception as cur_e:
                 logging.warning(f"關閉 cursor 時發生錯誤: {cur_e}")
        if conn and conn.is_connected():
            try:
                conn.close()
                logging.info("    資料庫連接已關閉 (fetch)。")
            except Exception as conn_e:
                 logging.warning(f"關閉 connection 時發生錯誤: {conn_e}")

# ✅ 2️⃣ **向量化數據並存入 Chroma**
def vectorize_and_store(rows):
    """
    將 MySQL 中的數據向量化，並存入 Chroma 向量資料庫。
    """
    logging.info("🔍 正在向量化數據並存入 Chroma...")
    
    if not rows:
        logging.warning("⚠️ 沒有可向量化的數據。")
        return
    
    try:
        # 初始化 HuggingFaceEmbeddings
        # 確保模型名稱正確
        model_name = "all-MiniLM-L6-v2" 
        logging.info(f"    初始化嵌入模型: {model_name}")
        embeddings_model = HuggingFaceEmbeddings(model_name=model_name)
        
        # 將數據格式化為 LangChain Document
        logging.info("    正在格式化數據為 LangChain Documents...")
        documents = []
        skipped_count = 0
        for row in rows:
            # 確保 content 存在且不為空
            if row and row.get('content') and str(row.get('content')).strip():
                # 確保 metadata 的值是字串且做長度限制 (ChromaDB 可能對 metadata 有限制)
                metadata = {
                    "id": str(row.get('id', '')), # 轉成字串
                    "chapter": str(row.get('chapter', ''))[:255], # 轉字串並限制長度
                    "article_number": str(row.get('article_number', ''))[:255] # 轉字串並限制長度
                }
                documents.append(
                    Document(
                        page_content=str(row['content']), # 確保是字串
                        metadata=metadata
                    )
                )
            else:
                skipped_count += 1
        
        if skipped_count > 0:
            logging.warning(f"    因缺少內容，跳過了 {skipped_count} 條記錄。")
        logging.info(f"    共準備了 {len(documents)} 個有效 Documents。")

        # 將文檔存入 Chroma 向量資料庫
        persist_dir = "./chroma_db"
        logging.info(f"    準備將 Documents 存入 ChromaDB (路徑: {persist_dir})...")
        # 使用 from_documents 會覆蓋舊數據還是追加？預設是覆蓋同 ID。
        # 如果希望完全重建，可以先刪除 persist_dir
        # import shutil
        # if os.path.exists(persist_dir):
        #     logging.warning(f"    刪除舊的 ChromaDB 目錄: {persist_dir}")
        #     shutil.rmtree(persist_dir)
        
        db = Chroma.from_documents(
            documents=documents, 
            embedding=embeddings_model, 
            persist_directory=persist_dir
        )
        # db.persist() # from_documents 創建時通常已包含持久化，但再調用一次更保險
        logging.info(f"✅ 成功向量化並存入 {len(documents)} 條記錄到 Chroma 資料庫。")

    except Exception as e:
        logging.error(f"❌ 向量化或存儲到 ChromaDB 時發生錯誤: {e}", exc_info=True)


# ✅ 3️⃣ **主程式**
def main():
    """
    執行流程：從 MySQL 讀取數據 → 向量化 → 存入 Chroma。
    """
    logging.info("--- 開始執行 vectorization 腳本 ---")
    rows = fetch_data_from_mysql()
    vectorize_and_store(rows)
    logging.info("--- vectorization 腳本執行完畢 ---")


# ✅ 4️⃣ **腳本啟動點**
if __name__ == "__main__":
    main()