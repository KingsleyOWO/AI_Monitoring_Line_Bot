# core/search_laws.py (精簡版)
import os
import openai
from dotenv import load_dotenv
import logging
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- 初始化 OpenAI Client (指向 Ollama) ---
client = None
try:
    client = openai.OpenAI(
        base_url=os.getenv('OLLAMA_BASE_URL', "http://ollama:11434/v1"),
        api_key=os.getenv('OLLAMA_API_KEY', "ollama"), # Ollama 不需要 key，但 client 需要此參數
    )
    logging.info(f"OpenAI client for Ollama configured: {client.base_url}")
except Exception as e:
    logging.error(f"Failed to configure OpenAI client for Ollama: {e}", exc_info=True)

# --- 初始化 ChromaDB ---
db = None
try:
    CHROMA_DB_PATH = "./chroma_db"
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2") # 可以保留常用模型
    db = Chroma(persist_directory=CHROMA_DB_PATH, embedding_function=embedding_function)
    logging.info("ChromaDB 連接成功.")
except Exception as e:
    logging.error(f"Failed to initialize ChromaDB: {e}", exc_info=True)

def search_laws(query, k=5):
    """
    在 ChromaDB 中搜尋與 query 相關的法規片段。
    """
    if db is None:
         logging.error("ChromaDB 未初始化，無法搜尋。")
         return ""
    try:
        logging.info(f"搜尋法規，關鍵字: {query}")
        results = db.similarity_search(query, k=k)
        context = ""
        count = 0
        processed_articles = set() # 保持過濾重複條文

        for doc in results:
             page_content = doc.page_content if hasattr(doc, 'page_content') else ''
             metadata = doc.metadata if hasattr(doc, 'metadata') else {}
             article_num = metadata.get('article_number', f'Unknown_{count}')

             # 過濾空內容和重複 (保持)
             if page_content and page_content.strip() and article_num not in processed_articles:
                  chapter = metadata.get('chapter', 'N/A')
                  count += 1
                  context += f"\n---\n"
                  context += f"法規片段 {count} (章節: {chapter}, 條號: {article_num}):\n"
                  context += f"{page_content.strip()}\n"
                  processed_articles.add(article_num)

        logging.info(f"法規搜尋完成，找到 {count} 個相關片段。")
        return context
    except Exception as e:
        logging.error(f"法規相似度搜尋時出錯: {e}", exc_info=True)
        return "" # 出錯時返回空字串

def generate_response(violation_type, context):
    """
    使用本地 Llama 3 模型生成回應。
    """
    if client is None:
         logging.error("Ollama client 未初始化，無法生成回應。")
         # 返回一個簡單的錯誤訊息模板
         return f"**偵測結果：發現違規**\n違規類型： {violation_type}\n\n**參考法規：**\n錯誤：摘要服務無法使用。"

    # Prompt 保持不變，它是功能核心
    prompt = f"""
    任務：你是一個工地安全法規助手。根據以下資訊，生成一個簡潔、專業的中文回覆。

    偵測到的違規行為： {violation_type}

    查詢到的相關法規片段：
    {context if context and context.strip() else "未找到相關法規條文。"}

    回覆要求：
    1.  語言：中文。
    2.  開頭：指出偵測到的違規是「{violation_type}」。
    3.  主體：若有法規，簡要說明最相關的1-2條規定及其關聯性。避免列出不相關或刪除的條文。
    4.  結尾：提醒參考條文編號（若有）。若無法規，提供通用安全建議。
    5.  風格：專業、簡潔。

    請生成回覆：
    """

    model_name = os.getenv('OLLAMA_MODEL', "llama3:8b") # 模型名稱從環境變數讀取

    try:
        logging.info(f"呼叫 Ollama Llama 3 (模型: {model_name}) 生成摘要...")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300, # 可以稍微縮短一點，節省資源
            temperature=0.5 # 溫度可以低一點，讓回答更穩定
        )
        generated_text = response.choices[0].message.content.strip()
        logging.info("Ollama Llama 3 摘要生成成功。")
        return generated_text
    except Exception as e:
        logging.error(f"呼叫 Ollama 或處理回應時出錯: {e}", exc_info=True)
        # 返回包含原始法規的模板 (備用方案)
        fallback_response = f"**偵測結果：發現違規**\n違規類型： {violation_type}\n"
        if context and context.strip():
            fallback_response += f"\n**參考法規（自動摘要失敗）：**\n{context.strip()}"
        else:
            fallback_response += "\n**參考法規：**\n未能自動查詢到相關法規條文，請遵守相關安全規範。"
        fallback_response += "\n\n*提醒：請依據最新法規及現場情況由專業人員判斷。*"
        return fallback_response