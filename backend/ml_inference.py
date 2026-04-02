import os
import cv2
import numpy as np
import onnxruntime as ort
import pkgutil
if not hasattr(pkgutil, 'find_loader'):
    from importlib.util import find_spec
    def find_loader(fullname):
        spec = find_spec(fullname)
        return spec.loader if spec else None
    pkgutil.find_loader = find_loader
import pytesseract

class ANPR_Model:
    def __init__(self, model_path):
        # We explicitly enforce the CPU execution provider to keep memory ultra low for Railway 512mb constraints
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        
        # Determine the dynamic input name assigned by ONNX export
        self.input_name = self.session.get_inputs()[0].name
        
    def preprocess_image(self, image_path):
        """ Read image and format it exactly how YOLO expects (640x640, normalized, NCHW) """
        img = cv2.imread(image_path)
        original_h, original_w = img.shape[:2]
        
        # Resize to 640x640 for YOLOv8n ONNX model input
        input_img = cv2.resize(img, (640, 640))
        input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
        
        # Normalize to 0-1 and rearrange dimensions to [batch, channel, height, width]
        input_img = input_img.astype(np.float32) / 255.0
        input_img = np.transpose(input_img, (2, 0, 1))
        input_img = np.expand_dims(input_img, axis=0)
        
        return input_img, img, original_w, original_h

    def infer(self, image_path):
        """ Run ONNX model against the locally stored image to get plate boxes """
        input_tensor, original_img, w, h = self.preprocess_image(image_path)
        
        outputs = self.session.run(None, {self.input_name: input_tensor})
        # Explicit type cast to avoid IDE list[str] complaints
        detections = np.array(outputs[0][0])
        
        best_box = None
        highest_conf = 0.0
        
        # Very rudimentary NMS/Parsing. Look across all 8400 anchors for highest confidence of class 0.
        for i in range(detections.shape[1]):
            # The structure for YOLOv8 ONNX: array of [cx, cy, w, h, class_0_conf, ...]
            box = detections[:, i]
            conf = float(box[4]) # Confidence of 'license_plate'
            
            if conf > highest_conf and conf > 0.4:
                highest_conf = conf
                
                # Scale box back up to original image specs
                cx, cy, bw, bh = box[0:4]
                rx, ry = cx / 640, cy / 640
                rw, rh = bw / 640, bh / 640
                
                xmin = int((rx - rw/2) * w)
                ymin = int((ry - rh/2) * h)
                xmax = int((rx + rw/2) * w)
                ymax = int((ry + rh/2) * h)
                
                # Ensure within image bounds
                xmin, ymin = max(0, xmin), max(0, ymin)
                xmax, ymax = min(w, xmax), min(h, ymax)
                
                best_box = (xmin, ymin, xmax, ymax)
                
        return best_box, highest_conf, original_img

    def extract_text(self, image, box):
        """ Given the bounding box coordinates, run Tesseract OCR on the cropped plate """
        if box is None:
            return "NO_PLATE_DETECTED"
            
        xmin, ymin, xmax, ymax = box
        plate_crop = image[ymin:ymax, xmin:xmax]
        
        # Preprocessing crop for better Tesseract OCR accuracy (Grayscale -> Threshold)
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Make sure to install tesseract-ocr binaries appropriately on Railway config
        text = pytesseract.image_to_string(thresh, config='--psm 8')
        return text.strip()

    def process_upload(self, image_path):
        """ Main orchestrator function """
        box, conf, img = self.infer(image_path)
        number_plate = self.extract_text(img, box)
        return number_plate, conf
