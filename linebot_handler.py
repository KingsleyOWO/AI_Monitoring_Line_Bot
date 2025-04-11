# linebot_handler.py (精簡版)
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage
from yolo_detector import SafetyViolationDetector
from core.search_laws import search_laws, generate_response
import os
from event_analyzer import parse_natural_language_time # 保留時間解析
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# --- Line Bot 初始化 (保持基本檢查) ---
line_bot_api = None
handler = None
try:
    line_channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    line_channel_secret = os.getenv('LINE_CHANNEL_SECRET')
    if not line_channel_access_token or not line_channel_secret:
        logging.error("環境變數 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_CHANNEL_SECRET 未設定！")
        exit()
    line_bot_api = LineBotApi(line_channel_access_token)
    handler = WebhookHandler(line_channel_secret)
    logging.info("Line Bot 初始化成功。")
except Exception as e:
    logging.error(f"Line Bot 初始化失敗: {e}")
    exit()

# --- YOLO 檢測器初始化 (保持基本檢查) ---
detector = None
try:
    # 假設 SafetyViolationDetector 的 __init__ 已記錄初始化成功或失敗
    detector = SafetyViolationDetector()
    if detector.model is None:
        logging.warning("YOLO Detector 初始化失敗或模型未載入。")
    else:
         logging.info("YOLO Detector 初始化成功。")
except Exception as e:
    logging.error(f"創建 SafetyViolationDetector 實例時出錯: {e}", exc_info=True)

# --- MySQL 配置 (保持) ---
db_config = {
    'host': os.getenv('MYSQL_HOST', 'mysql'),
    'user': os.getenv('MYSQL_USER', 'kingsley'),
    'password': os.getenv('MYSQL_PASSWORD', 'ji394djp4'),
    'database': os.getenv('MYSQL_DATABASE', 'kingsley_db'),
    'port': int(os.getenv('MYSQL_PORT', 3306))
}
logging.info(f"資料庫配置: {db_config['host']}:{db_config['port']}/{db_config['database']}")


# --- 資料庫操作函數 (精簡 Log) ---
def save_violation_record(violation_type, image_path):
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO violations (timestamp, violation_type, image_path) VALUES (%s, %s, %s)",
            (timestamp, violation_type, image_path)
        )
        conn.commit()
        logging.info(f"違規紀錄已儲存: {violation_type}")
    except mysql.connector.Error as err:
        logging.error(f"資料庫錯誤 (儲存違規紀錄): {err}")
    except Exception as e:
        logging.error(f"儲存違規紀錄時發生未知錯誤: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()

def get_violations_by_date(start_time_iso, end_time_iso):
    records = []
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT timestamp, violation_type FROM violations WHERE timestamp >= %s AND timestamp < %s ORDER BY timestamp DESC",
            (start_time_iso, end_time_iso)
        )
        records = cursor.fetchall()
        logging.info(f"查詢違規紀錄 ({start_time_iso[:10]} to {end_time_iso[:10]}): 找到 {len(records)} 筆")
    except mysql.connector.Error as err:
        logging.error(f"資料庫錯誤 (查詢違規紀錄): {err}")
    except Exception as e:
        logging.error(f"查詢違規紀錄時發生未知錯誤: {e}", exc_info=True)
    finally:
        if cursor: cursor.close()
        if conn and conn.is_connected(): conn.close()
    return records

# --- Webhook 入口 (精簡 Log) ---
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    # logging.info("收到 Line Webhook 請求") # 太頻繁，移除
    if handler is None:
         logging.error("Webhook Handler 未初始化!")
         abort(500)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.warning("Webhook 簽名驗證失敗。")
        abort(400)
    except LineBotApiError as e:
        logging.error(f"Line Bot API 錯誤: {e.status_code} {e.error.message}")
    except Exception as e:
        logging.error(f"處理 Webhook 時發生錯誤: {e}", exc_info=True)
    return 'OK'

# --- 處理照片訊息 (精簡 Log 和錯誤處理流程) ---
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    logging.info(f"收到來自使用者 {event.source.user_id} 的圖片訊息")
    message_id = event.message.id
    temp_dir = './temp'
    os.makedirs(temp_dir, exist_ok=True)
    image_path = os.path.join(temp_dir, f'{message_id}.jpg')
    response_text = "處理圖片時發生錯誤，請稍後再試。" # 預設錯誤訊息

    try:
        # 1. 儲存圖片
        if line_bot_api is None: raise Exception("Line Bot API 未初始化")
        message_content = line_bot_api.get_message_content(message_id)
        with open(image_path, 'wb') as f:
            for chunk in message_content.iter_content():
                f.write(chunk)
        logging.info(f"圖片已儲存: {image_path}")

        # 2. 執行檢測
        if detector is None or detector.model is None:
            logging.error("Detector 未初始化或失敗，無法分析圖片。")
            response_text = "抱歉，分析模組暫時無法使用。"
        else:
            # 使用一個 try-except 處理整個檢測到回覆的流程
            try:
                result_list = detector.detect(image_path)
                if not result_list: raise Exception("檢測器未返回有效結果")
                result = result_list[0] # 取第一個結果

                if result.get("violation_detected"):
                    violation_type = result.get("violation_type", "未知違規")
                    logging.info(f"偵測到違規: {violation_type}")

                    # 儲存紀錄 (如果失敗，不影響後續回覆)
                    try:
                         save_violation_record(violation_type, image_path)
                    except Exception as db_err:
                         logging.error(f"儲存違規紀錄失敗 (但不中斷): {db_err}")

                    # 查詢法規 & 生成回覆
                    context = search_laws(violation_type)
                    response_text = generate_response(violation_type, context)
                    logging.info("已生成違規分析回覆。")

                elif result.get("violation_type"): # Detector 返回了非違規的訊息 (通常是錯誤)
                    logging.warning(f"圖片分析時遇到問題: {result.get('violation_type')}")
                    response_text = f"圖片分析異常：{result.get('violation_type')}"
                else:
                    logging.info("未偵測到違規行為。")
                    response_text = "✅ 照片中未檢測到特定違規行為。"

            except Exception as analysis_err:
                logging.error(f"分析圖片或生成回覆時出錯: {analysis_err}", exc_info=True)
                # 使用預設的錯誤訊息
                response_text = "分析圖片時發生內部錯誤。"

    except Exception as e:
        # 捕捉儲存圖片或更早期的錯誤
        logging.error(f"處理圖片訊息時發生錯誤: {e}", exc_info=True)
        # 使用預設的錯誤訊息

    # --- 統一回覆 ---
    try:
        if line_bot_api:
            log_response_preview = response_text.replace('\n', ' ')[:80] # Log 短一點
            logging.info(f"準備回覆使用者: {log_response_preview}...")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response_text)
            )
        else:
             logging.error("Line Bot API 未初始化，無法回覆。")
    except Exception as reply_e:
        logging.error(f"回覆 Line 訊息時失敗: {reply_e}")


# --- 處理文字訊息 (精簡 Log) ---
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_text = event.message.text
    logging.info(f"收到來自使用者 {event.source.user_id} 的文字訊息: {user_text[:50]}...") # Log 短一點
    response = "請上傳照片進行違規檢測，或輸入 '查詢 [時間範圍] 違規' (例如: 查詢今天違規)。" # 預設回覆

    if "違規" in user_text and ("查詢" in user_text or "查看" in user_text):
        try:
            start_time, end_time = parse_natural_language_time(user_text)
            if start_time and end_time:
                logging.info(f"解析時間範圍: {start_time.isoformat()} 到 {end_time.isoformat()}")
                records = get_violations_by_date(start_time.isoformat(), end_time.isoformat())
                if records:
                    # 格式化回應 (保持基本邏輯，但減少 Log)
                    response = f"📊 查詢 {start_time.strftime('%Y-%m-%d %H:%M')} 至 {end_time.strftime('%Y-%m-%d %H:%M')} 的違規紀錄 ({len(records)} 筆):\n"
                    for record in records[:15]: # 最多顯示 15 筆，避免過長
                        try:
                            ts_str = str(record.get('timestamp', 'N/A'))
                            dt_obj = datetime.fromisoformat(ts_str)
                            formatted_time = dt_obj.strftime("%m-%d %H:%M") # 簡化時間格式
                            response += f"- {record.get('violation_type', 'N/A')} ({formatted_time})\n"
                        except Exception:
                            response += f"- {record.get('violation_type', 'N/A')} (時間格式錯誤)\n"
                    if len(records) > 15:
                        response += f"...等共 {len(records)} 筆紀錄。"
                else:
                    response = f"✅ 在指定時間範圍內無違規紀錄。"
            else:
                response = "⚠️ 無法解析時間範圍，請試試 '今天', '昨天', '本週' 等。"
        except Exception as query_e:
            logging.error(f"處理查詢指令時出錯: {query_e}", exc_info=True)
            response = "處理查詢時發生錯誤。"

    # --- 回覆文字訊息 ---
    try:
        if line_bot_api:
            log_response_preview = response.replace('\n', ' ')[:80]
            logging.info(f"準備回覆使用者: {log_response_preview}...")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=response)
            )
        else:
             logging.error("Line Bot API 未初始化，無法回覆。")
    except Exception as e:
        logging.error(f"回覆 Line 文字訊息時失敗: {e}")

# --- 啟動 Flask App (保持) ---
if __name__ == "__main__":
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 4040))
    host = '0.0.0.0'
    logging.info(f"啟動 Flask 應用程式於 http://{host}:{port}/ (Debug: {debug_mode})")
    if line_bot_api is None or handler is None:
         logging.error("Line Bot API 或 Handler 未初始化，無法啟動 Web Server！")
    else:
         # 開發時可以直接用 app.run，部署時應換成 Gunicorn 或 Waitress
         try:
             app.run(host=host, port=port, debug=debug_mode)
         except Exception as run_e:
              logging.error(f"啟動 Flask 伺服器失敗: {run_e}", exc_info=True)