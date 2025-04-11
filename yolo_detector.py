# yolo_detector.py (精簡版)
import cv2
import torch
import numpy as np
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def calculate_iou(box1, box2):
    # IoU 計算邏輯不變... (保持原樣)
    x1_inter = max(box1[0], box2[0])
    y1_inter = max(box1[1], box2[1])
    x2_inter = min(box1[2], box2[2])
    y2_inter = min(box1[3], box2[3])
    inter_area = max(0, x2_inter - x1_inter) * max(0, y2_inter - y1_inter)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    if union_area == 0:
        return 0.0
    iou = inter_area / union_area
    return iou

class SafetyViolationDetector:
    def __init__(self, model_path="best.pt"):
        self.model = None
        self.head_class_id = -1
        self.helmet_class_id = -1
        self.model_names = {}
        self.iou_threshold = 0.1 # IoU 閾值可以保留

        try:
            # 載入模型
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, trust_repo=True)
            logging.info(f"YOLOv5 模型載入成功: {model_path}")

            # 簡化類別 ID 查找 (假設 names 是字典或列表)
            if hasattr(self.model, 'names') and self.model.names:
                if isinstance(self.model.names, dict):
                    names_map = self.model.names
                elif isinstance(self.model.names, (list, tuple)):
                    names_map = {i: name for i, name in enumerate(self.model.names)}
                else:
                    names_map = {}
                    logging.warning("無法識別的 model.names 格式")

                self.model_names = names_map # 仍然保存以備不時之需
                for class_id, class_name in names_map.items():
                    if isinstance(class_name, str):
                        if class_name.lower() == 'head':
                            self.head_class_id = int(class_id)
                        elif class_name.lower() == 'helmet':
                            self.helmet_class_id = int(class_id)

                logging.info(f"Head class ID: {self.head_class_id}, Helmet class ID: {self.helmet_class_id}")
                if self.head_class_id == -1 or self.helmet_class_id == -1:
                    logging.warning("模型中未找到 'head' 或 'helmet' 類別，'no_helmet' 檢測可能無法運作。")
            else:
                logging.warning("模型缺少 'names' 屬性或 'names' 為空。")

        except Exception as e:
            logging.error(f"初始化 YOLO 檢測器失敗: {e}", exc_info=True)
            self.model = None # 標記失敗

    def detect(self, image_path):
        start_time = time.time()
        if self.model is None:
             logging.error("模型未初始化，無法進行檢測。")
             # 返回符合 linebot_handler 預期格式的錯誤
             return [{"violation_detected": False, "violation_type": "模型初始化失敗", "image_saved_path": None}]
        if self.head_class_id == -1 or self.helmet_class_id == -1:
            logging.error("模型缺少必要類別 (head 或 helmet)，無法進行檢測。")
            return [{"violation_detected": False, "violation_type": "模型缺少必要類別", "image_saved_path": None}]

        try:
            frame = cv2.imread(image_path)
            if frame is None:
                logging.error(f"無法讀取圖片: {image_path}")
                return [{"violation_detected": False, "violation_type": "圖片讀取失敗", "image_saved_path": None}]

            # 模型偵測
            detections = self.model(frame)
            processed_detections = detections.xyxy[0].cpu().numpy()

            detected_heads = []
            detected_helmets = []

            for det in processed_detections:
                x_min, y_min, x_max, y_max, conf, cls_id_float = det
                cls_id = int(cls_id_float)
                box = [x_min, y_min, x_max, y_max]
                if cls_id == self.head_class_id:
                    detected_heads.append({"box": box, "conf": conf})
                elif cls_id == self.helmet_class_id:
                    detected_helmets.append({"box": box, "conf": conf})

            # 核心檢查邏輯 (移除內部詳細 Log)
            found_no_helmet = False
            for head in detected_heads:
                has_associated_helmet = False
                for helmet in detected_helmets:
                    iou = calculate_iou(head["box"], helmet["box"])
                    if iou >= self.iou_threshold:
                        has_associated_helmet = True
                        break # 找到對應的頭盔，檢查下一個頭

                if not has_associated_helmet:
                    # 找到第一個未戴安全帽的就結束
                    logging.info(f"偵測到 'no_helmet' 違規 in {image_path}")
                    end_time = time.time()
                    logging.info(f"檢測耗時: {end_time - start_time:.2f} 秒")
                    return [{"violation_detected": True, "violation_type": "no_helmet", "image_saved_path": image_path}]

            # 如果循環結束都沒找到違規
            logging.info(f"未在圖片中偵測到 'no_helmet' 違規: {image_path}")
            end_time = time.time()
            logging.info(f"檢測耗時: {end_time - start_time:.2f} 秒")
            return [{"violation_detected": False, "violation_type": None, "image_saved_path": None}]

        except Exception as e:
            logging.error(f"執行檢測時發生錯誤: {e}", exc_info=True)
            return [{"violation_detected": False, "violation_type": f"檢測時發生錯誤", "image_saved_path": None}]