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
 
# Windows: Set Tesseract path explicitly
_tesseract_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
]
for _path in _tesseract_paths:
    if os.path.exists(_path):
        pytesseract.pytesseract.tesseract_cmd = _path
        break
 
 
class ANPR_Model:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
 
    def _letterbox(self, img, new_shape=640, color=(114, 114, 114)):
        h, w = img.shape[:2]
        r = new_shape / max(h, w)
        new_w, new_h = int(round(w * r)), int(round(h * r))
        img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        pad_top    = (new_shape - new_h) // 2
        pad_bottom =  new_shape - new_h - pad_top
        pad_left   = (new_shape - new_w) // 2
        pad_right  =  new_shape - new_w - pad_left
        img_padded = cv2.copyMakeBorder(
            img_resized, pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT, value=color
        )
        return img_padded, r, pad_left, pad_top
 
    def preprocess_image(self, image_path):
        img = cv2.imread(image_path)
        if img is None:
            raise ValueError(f"Could not read image: {image_path}")
        original_h, original_w = img.shape[:2]
        img_lb, ratio, pad_x, pad_y = self._letterbox(img, new_shape=640)
        input_img = cv2.cvtColor(img_lb, cv2.COLOR_BGR2RGB)
        input_img = input_img.astype(np.float32) / 255.0
        input_img = np.transpose(input_img, (2, 0, 1))
        input_img = np.expand_dims(input_img, axis=0)
        return input_img, img, original_w, original_h, ratio, pad_x, pad_y
 
    def infer(self, image_path):
        input_tensor, original_img, w, h, ratio, pad_x, pad_y = self.preprocess_image(image_path)
        outputs    = self.session.run(None, {self.input_name: input_tensor})
        detections = np.array(outputs[0][0])
        all_confs  = detections[4, :]
 
        CONF_THRESHOLD = 0.25
        MIN_ASPECT     = 1.5
        MAX_ASPECT     = 8.0
 
        best_box  = None
        best_conf = 0.0
 
        for idx in np.argsort(all_confs)[::-1]:
            conf = float(all_confs[idx])
            if conf < CONF_THRESHOLD:
                break
 
            cx, cy, bw, bh = detections[0:4, idx]
            cx_orig = (cx - pad_x) / ratio
            cy_orig = (cy - pad_y) / ratio
            bw_orig = bw / ratio
            bh_orig = bh / ratio
 
            xmin = max(0, int(cx_orig - bw_orig / 2))
            ymin = max(0, int(cy_orig - bh_orig / 2))
            xmax = min(w,  int(cx_orig + bw_orig / 2))
            ymax = min(h,  int(cy_orig + bh_orig / 2))
 
            crop_w = xmax - xmin
            crop_h = ymax - ymin
            if crop_h == 0:
                continue
 
            aspect = crop_w / crop_h
            if MIN_ASPECT <= aspect <= MAX_ASPECT:
                best_box  = (xmin, ymin, xmax, ymax)
                best_conf = conf
                break
 
        return best_box, best_conf, original_img
 
    def _strip_side_badge(self, crop_bgr):
        """
        EU/GB plates have a blue strip on the LEFT (~15% of width) containing
        stars and country code (GB, D, F etc). Tesseract misreads this as
        '1', 'I', or 'B' — causing results like '10007' instead of '0007'.
 
        This method detects the coloured badge via HSV colour segmentation
        and crops it off BEFORE passing the image to Tesseract.
        Works for: EU blue badge, dark navy badge, yellow/green badges.
        """
        hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
 
        # EU blue badge range
        blue_mask = cv2.inRange(hsv,
                                np.array([100, 80,  50]),
                                np.array([140, 255, 255]))
        # Dark navy / black badge (older UK plates)
        dark_mask = cv2.inRange(hsv,
                                np.array([0,   0,   0]),
                                np.array([180, 50,  60]))
        # Green badge (some Asian plates)
        green_mask = cv2.inRange(hsv,
                                 np.array([40,  80,  50]),
                                 np.array([80,  255, 255]))
 
        badge_mask = cv2.bitwise_or(blue_mask, cv2.bitwise_or(dark_mask, green_mask))
 
        h, w = crop_bgr.shape[:2]
 
        # Only examine left 20% and right 20% — badges are always on edges
        left_region  = badge_mask[:, :int(w * 0.20)]
        right_region = badge_mask[:, int(w * 0.80):]
 
        left_ratio  = np.count_nonzero(left_region)  / (left_region.size  + 1e-5)
        right_ratio = np.count_nonzero(right_region) / (right_region.size + 1e-5)
 
        x_start = 0
        x_end   = w
 
        # If badge pixels cover >25% of that edge region — strip it
        if left_ratio > 0.25:
            x_start = int(w * 0.18)
        if right_ratio > 0.25:
            x_end = int(w * 0.82)
 
        if x_start > 0 or x_end < w:
            crop_bgr = crop_bgr[:, x_start:x_end]
 
        return crop_bgr
 
    def extract_text(self, image, box):
        if box is None:
            return "NO_PLATE_DETECTED"
 
        xmin, ymin, xmax, ymax = box
        plate_crop = image[ymin:ymax, xmin:xmax]
 
        if plate_crop.size == 0:
            return "NO_PLATE_DETECTED"
 
        # ── NEW: Strip EU/GB/other side badge before OCR ──────────────
        plate_crop = self._strip_side_badge(plate_crop)
 
        # Upscale to at least 200px tall for reliable OCR
        crop_h, crop_w = plate_crop.shape[:2]
        if crop_h < 200:
            scale = max(2, 200 // crop_h)
            plate_crop = cv2.resize(
                plate_crop, (crop_w * scale, crop_h * scale),
                interpolation=cv2.INTER_CUBIC
            )
 
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
 
        sharpen_kernel = np.array([[-1,-1,-1],
                                   [-1, 9,-1],
                                   [-1,-1,-1]])
        gray = cv2.filter2D(gray, -1, sharpen_kernel)
        gray = cv2.fastNlMeansDenoising(gray, h=10)
 
        _, thresh_normal = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY     + cv2.THRESH_OTSU)
        _, thresh_inv    = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
 
        whitelist = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
        best = ''
 
        for img_variant in [thresh_normal, thresh_inv, gray]:
            for psm in [8, 13, 7]:
                cfg     = f'--psm {psm} -c tessedit_char_whitelist={whitelist}'
                raw     = pytesseract.image_to_string(img_variant, config=cfg)
                # Strip ALL non-alphanumeric chars (spaces, newlines, dashes)
                # before comparing lengths — spaces must never affect result
                cleaned = ''.join(c for c in raw if c.isalnum())
                if len(cleaned) > len(best):
                    best = cleaned
 
        return best if best else "UNREADABLE"
 
    def process_upload(self, image_path):
        box, conf, img = self.infer(image_path)
        number_plate   = self.extract_text(img, box)
        return number_plate, conf
 
    def process_upload_bytes(self, image_bytes):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        try:
            box, conf, img = self.infer(tmp_path)
            number_plate   = self.extract_text(img, box)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        return number_plate, conf