# core/scrape_clean_mysql.py (已加入 import logging)
import re
from bs4 import BeautifulSoup
import mysql.connector
import os
from dotenv import load_dotenv
import logging # <--- ***在這裡加入了 import logging***

# --- LangChain 的導入 (使用你原本的，即使有警告) ---
from langchain.document_loaders import WebBaseLoader 
# --------------------------------------------------

load_dotenv()

# --- 基本的 logging 設定 (放在 import 後面) ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

# --- fetch_and_clean_data 函數 (假設內容如之前) ---
def fetch_and_clean_data(url):
    logging.info(f"Fetching and cleaning data from URL: {url}")
    loader = WebBaseLoader(url)
    try:
        documents = loader.load()
    except Exception as e:
        logging.error(f"Error loading URL {url}: {e}")
        return ""
    
    cleaned_documents = []
    for doc in documents:
        if hasattr(doc, 'page_content'):
            soup = BeautifulSoup(doc.page_content, "html.parser")
            text = soup.get_text(separator="\n")
            cleaned_documents.append(text)
    
    logging.info(f"Finished cleaning data from URL.")
    return "\n".join(cleaned_documents)

# --- extract_law_content 函數 (假設內容如之前) ---
def extract_law_content(content):
    pattern = r'(第\s*一\s*章\s*總則[\s\S]*?第\s*174\s*條[\s\S]*?一日施行。)' 
    logging.info("Extracting law content using regex...")
    match = re.search(pattern, content)
    if match:
        logging.info("Regex matched.")
        return match.group(1)
    logging.warning("Regex did not match content.")
    return ""

# --- format_law_content 函數 (使用之前修正過的版本) ---
def format_law_content(filtered_content):
    output_lines = []
    current_chapter = ""
    current_article = ""
    current_content = ""
    
    logging.info("Formatting extracted law content...")
    line_num = 0
    for line in filtered_content.splitlines():
        line_num += 1
        line = line.strip()
        if not line: continue

        if line.startswith("第") and "章" in line:
            content_to_check = current_content.strip()
            if current_article and content_to_check and content_to_check != "（刪除）":
                output_lines.append({'chapter': current_chapter, 'article_number': current_article, 'content': content_to_check})
            current_chapter = line
            current_article = "" 
            current_content = "" 

        elif line.startswith("第") and "條" in line:
            content_to_check = current_content.strip()
            if current_article and content_to_check and content_to_check != "（刪除）":
                output_lines.append({'chapter': current_chapter, 'article_number': current_article, 'content': content_to_check})
            current_article = line
            current_content = "" 
        
        elif current_article: 
            if current_content: current_content += " " + line 
            else: current_content += line

    content_to_check = current_content.strip()
    if current_article and content_to_check and content_to_check != "（刪除）":
        output_lines.append({'chapter': current_chapter, 'article_number': current_article, 'content': content_to_check})
    
    logging.info(f"    格式化完成，共找到 {len(output_lines)} 條有效條文。")
    return output_lines

# --- db_config (讀取環境變數) ---
db_config = {
    'host': os.getenv('MYSQL_HOST', 'mysql'), 
    'user': os.getenv('MYSQL_USER', 'kingsley'),
    'password': os.getenv('MYSQL_PASSWORD', 'ji394djp4'),
    'database': os.getenv('MYSQL_DATABASE', 'kingsley_db'),
    'port': int(os.getenv('MYSQL_PORT', 3306)) 
}
logging.info(f"資料庫設定 (scrape_clean): {db_config}")

# --- save_to_mysql 函數 (使用之前增強 Log 的版本) ---
def save_to_mysql(records):
    """將格式化後的條文數據儲存到 MySQL 資料庫中 (增加詳細 Debug Log)。"""
    logging.info(f"💾 收到 {len(records)} 筆記錄準備儲存到 MySQL...")
    if not records:
         logging.warning("  ⚠️ 沒有記錄需要儲存。")
         return

    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        logging.info("    ✅ 資料庫連接成功 (save_to_mysql)。")
        cursor = conn.cursor()

        logging.info("    檢查並創建 articles 表格...")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INT AUTO_INCREMENT PRIMARY KEY, chapter VARCHAR(255), article_number VARCHAR(255), content TEXT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        logging.info("    articles 表格已存在或已創建。")

        logging.info("    正在清空舊的 articles 資料 (TRUNCATE)...")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute("TRUNCATE TABLE articles")
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        logging.info("    舊資料已清空。")

        logging.info("    正在插入新記錄...")
        insert_count = 0
        error_count = 0
        processed_count = 0
        for record in records:
            processed_count += 1
            try:
                if record and all(k in record for k in ('chapter', 'article_number', 'content')):
                    if record['content'] and str(record['content']).strip():
                        cursor.execute("""
                        INSERT INTO articles (chapter, article_number, content)
                        VALUES (%s, %s, %s)
                        """, (record['chapter'], record['article_number'], record['content']))
                        insert_count += 1
                    else:
                         logging.warning(f"    第 {processed_count} 筆記錄內容為空，已跳過: {record.get('article_number')}")
                         error_count += 1
                else:
                    logging.warning(f"    第 {processed_count} 筆記錄缺少鍵值，已跳過")
                    error_count += 1
            except mysql.connector.Error as insert_err:
                logging.error(f"    ❌ 第 {processed_count} 筆 ({record.get('article_number')}) 插入時發生 DB 錯誤: {insert_err}")
                error_count += 1
            except Exception as general_err:
                logging.error(f"    ❌ 第 {processed_count} 筆 ({record.get('article_number')}) 插入時發生未知錯誤: {general_err}")
                error_count += 1

        logging.info(f"    迴圈完成。處理: {processed_count} 筆，嘗試插入: {insert_count} 筆，錯誤/跳過: {error_count} 筆。")

        # Commit Phase Logging
        if insert_count > 0:
             logging.info(f"    準備提交 (commit) {insert_count} 筆插入操作...")
             try:
                  conn.commit()
                  logging.info("    ✅✅✅ 資料庫提交 (commit) 成功！")

                  # Verification after commit
                  logging.info("    正在驗證寫入數量...")
                  cursor.execute("SELECT COUNT(*) FROM articles")
                  verify_count = cursor.fetchone()[0]
                  logging.info(f"    驗證：提交後 articles 表格實際數量: {verify_count}")
                  if verify_count == insert_count:
                       logging.info(f"    ✅ 驗證成功：實際數量 ({verify_count}) 與嘗試插入數量 ({insert_count}) 相符。")
                  else:
                       logging.error(f"    ❌❌❌ 驗證失敗：實際數量 ({verify_count}) 與嘗試插入數量 ({insert_count}) 不符！")

             except mysql.connector.Error as commit_err:
                  logging.error(f"    ❌❌❌ 資料庫提交 (commit) 失敗: {commit_err}", exc_info=True)
                  try: conn.rollback(); logging.info("    回滾成功。")
                  except Exception as rb_err: logging.error(f"    回滾時發生錯誤: {rb_err}")
             except Exception as commit_e:
                  logging.error(f"    ❌❌❌ 資料庫提交 (commit) 時發生非預期錯誤: {commit_e}", exc_info=True)
                  try: conn.rollback(); logging.info("    回滾成功。")
                  except Exception as rb_err: logging.error(f"    回滾時發生錯誤: {rb_err}")
        else:
             logging.warning("    沒有成功執行的插入操作，無需提交。")

    except mysql.connector.Error as err:
        logging.error(f"❌ MySQL 連接或準備階段錯誤 (save_to_mysql): {err}", exc_info=True)
    except Exception as e:
         logging.error(f"❌ 儲存到 MySQL 時發生未預期錯誤 (save_to_mysql): {e}", exc_info=True)
         if conn and conn.is_connected():
              try: conn.rollback(); logging.info("    主錯誤處理回滾成功。")
              except Exception as rb_err: logging.error(f"    主錯誤處理回滾時發生錯誤: {rb_err}")
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn and conn.is_connected():
            try: conn.close(); logging.info("    資料庫連接已關閉 (save_to_mysql)。")
            except: pass

# --- main 函數 (假設內容如之前) ---
def main():
    """
    主流程：爬取 -> 提取 -> 格式化 -> 儲存
    """
    logging.info("--- 開始執行 scrape_clean_mysql 腳本 ---")
    url = "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=N0060014"
    raw_content = fetch_and_clean_data(url)
    if raw_content:
        filtered_content = extract_law_content(raw_content)
        if filtered_content:
            records = format_law_content(filtered_content)
            if records:
                 save_to_mysql(records) # 呼叫修正後的 save_to_mysql
            else:
                 logging.warning("格式化後無有效記錄可儲存。")
        else:
            logging.warning("未能從原始內容中提取到法規內容。")
    else:
        logging.warning("未能獲取或清理網頁內容。")
    logging.info("--- scrape_clean_mysql 腳本執行完畢 ---")

if __name__ == "__main__":
    main()