import kagglehub
import os
import shutil
import xml.etree.ElementTree as ET
from ultralytics import YOLO
import random

current_dir = os.path.dirname(os.path.abspath(__file__))
yolo_dir    = os.path.join(current_dir, "yolo_dataset")

# Ensure Kaggle finds your credentials
os.environ['KAGGLE_CONFIG_DIR'] = os.path.join(current_dir, "..", "kaggle")

# ─────────────────────────────────────────────────────────────────────
# IMPROVEMENT 1: Download 3 datasets instead of 1
#
# Old: andrewmvd/car-plate-detection → ~400 images, mostly European,
#      clean studio-style shots. Too small and too uniform.
#
# New: 3 datasets combined → 3,000+ images covering:
#   • Global plate styles (EU, US, Indian, Brazilian, Asian)
#   • Full car photos where plate is a small region
#   • Close-up plate shots
#   • Real-world lighting, angles, blur
# ─────────────────────────────────────────────────────────────────────
DATASETS = [
    "andrewmvd/car-plate-detection",          # ~400 images, XML annotations
    "aslanahmedov/number-plate-detection",     # ~1800 images, XML annotations
    "pkdarabi/carplate",                       # ~900 images, XML annotations
]

print("=" * 60)
print("Downloading datasets...")
print("=" * 60)

dataset_paths = []
for ds in DATASETS:
    try:
        path = kagglehub.dataset_download(ds)
        dataset_paths.append(path)
        print(f"  [OK] {ds}")
    except Exception as e:
        print(f"  [SKIP] {ds} — {e}")

if not dataset_paths:
    print("\n[ERROR] No datasets could be downloaded. Check your Kaggle credentials.")
    exit(1)

print(f"\nDownloaded {len(dataset_paths)} dataset(s).\n")

# ─────────────────────────────────────────────────────────────────────
# Setup YOLO directory structure
# ─────────────────────────────────────────────────────────────────────
for split in ["train", "val"]:
    os.makedirs(os.path.join(yolo_dir, "images", split), exist_ok=True)
    os.makedirs(os.path.join(yolo_dir, "labels", split), exist_ok=True)

# ─────────────────────────────────────────────────────────────────────
# XML → YOLO converter (handles Pascal VOC format used by all 3 datasets)
# ─────────────────────────────────────────────────────────────────────
def convert_xml_to_yolo(xml_file, width, height):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    boxes = []
    for obj in root.findall('object'):
        xmlbox = obj.find('bndbox')
        if xmlbox is None:
            continue
        try:
            xmin = float(xmlbox.find('xmin').text)
            xmax = float(xmlbox.find('xmax').text)
            ymin = float(xmlbox.find('ymin').text)
            ymax = float(xmlbox.find('ymax').text)
        except (AttributeError, TypeError, ValueError):
            continue

        # Skip degenerate boxes
        if xmax <= xmin or ymax <= ymin:
            continue

        # Clamp to image bounds
        xmin = max(0, min(xmin, width))
        xmax = max(0, min(xmax, width))
        ymin = max(0, min(ymin, height))
        ymax = max(0, min(ymax, height))

        x_center = (xmin + xmax) / 2.0 / width
        y_center = (ymin + ymax) / 2.0 / height
        box_w    = (xmax - xmin) / width
        box_h    = (ymax - ymin) / height

        boxes.append(f"0 {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}")
    return boxes


def find_images_and_annotations(dataset_path):
    """
    Auto-detect image and annotation folders regardless of dataset structure.
    Returns (images_dir, annotations_dir) or (None, None) if not found.
    """
    images_dir = annotations_dir = None

    # Common folder names to look for
    img_names  = {"images", "image", "imgs", "JPEGImages", "photos"}
    ann_names  = {"annotations", "annotation", "labels", "Annotations", "xmls"}

    for root, dirs, files in os.walk(dataset_path):
        folder = os.path.basename(root).lower()
        if folder in {n.lower() for n in img_names}:
            # Check it actually has images
            if any(f.endswith(('.jpg', '.jpeg', '.png')) for f in files):
                images_dir = root
        if folder in {n.lower() for n in ann_names}:
            if any(f.endswith('.xml') for f in files):
                annotations_dir = root

    return images_dir, annotations_dir


# ─────────────────────────────────────────────────────────────────────
# Collect all valid (image, annotation) pairs from all datasets
# ─────────────────────────────────────────────────────────────────────
all_pairs = []   # list of (img_path, xml_path)

for ds_path in dataset_paths:
    images_dir, annotations_dir = find_images_and_annotations(ds_path)

    if not images_dir or not annotations_dir:
        print(f"  [WARN] Could not find images/annotations in {ds_path}, skipping.")
        continue

    img_files = [f for f in os.listdir(images_dir)
                 if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    found = 0
    for img_file in img_files:
        base     = os.path.splitext(img_file)[0]
        xml_path = os.path.join(annotations_dir, base + ".xml")
        if os.path.exists(xml_path):
            all_pairs.append((os.path.join(images_dir, img_file), xml_path))
            found += 1

    print(f"  {ds_path}: found {found} valid image-annotation pairs")

print(f"\nTotal pairs across all datasets: {len(all_pairs)}")

if len(all_pairs) == 0:
    print("[ERROR] No valid image-annotation pairs found. Exiting.")
    exit(1)

# ─────────────────────────────────────────────────────────────────────
# 80/20 train/val split — reproducible via seed
# ─────────────────────────────────────────────────────────────────────
random.seed(42)
random.shuffle(all_pairs)

split_idx   = int(0.8 * len(all_pairs))
train_pairs = all_pairs[:split_idx]
val_pairs   = all_pairs[split_idx:]

print(f"Train: {len(train_pairs)} | Val: {len(val_pairs)}\n")


def process_pairs(pairs, split_name):
    skipped = 0
    for img_path, xml_path in pairs:
        img_file = os.path.basename(img_path)
        base     = os.path.splitext(img_file)[0]
        txt_name = base + ".txt"

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            size = root.find('size')

            if size is not None:
                w = int(float(size.find('width').text))
                h = int(float(size.find('height').text))
            else:
                # Fall back to reading actual image dimensions
                import cv2
                tmp = cv2.imread(img_path)
                if tmp is None:
                    skipped += 1
                    continue
                h, w = tmp.shape[:2]

            yolo_boxes = convert_xml_to_yolo(xml_path, w, h)
            if not yolo_boxes:
                skipped += 1
                continue

            # Write label file
            label_path = os.path.join(yolo_dir, "labels", split_name, txt_name)
            with open(label_path, "w") as lf:
                lf.write("\n".join(yolo_boxes))

            # Copy image — use unique name to avoid collisions across datasets
            dest_img = os.path.join(yolo_dir, "images", split_name, img_file)
            if os.path.exists(dest_img):
                # Prefix with dataset folder name to make it unique
                ds_prefix = os.path.basename(os.path.dirname(os.path.dirname(img_path)))
                img_file  = f"{ds_prefix}_{img_file}"
                txt_name  = f"{ds_prefix}_{txt_name}"
                dest_img  = os.path.join(yolo_dir, "images", split_name, img_file)
                label_path = os.path.join(yolo_dir, "labels", split_name, txt_name)
                with open(label_path, "w") as lf:
                    lf.write("\n".join(yolo_boxes))

            shutil.copy(img_path, dest_img)

        except Exception as e:
            skipped += 1
            continue

    print(f"  [{split_name}] Processed. Skipped {skipped} invalid entries.")


print("Converting annotations to YOLO format...")
process_pairs(train_pairs, "train")
process_pairs(val_pairs,   "val")
print("Conversion complete.\n")

# ─────────────────────────────────────────────────────────────────────
# Write data.yaml
# ─────────────────────────────────────────────────────────────────────
yaml_content = f"""path: {yolo_dir.replace(chr(92), '/')}
train: images/train
val:   images/val

names:
  0: license_plate
"""
yaml_path = os.path.join(yolo_dir, "data.yaml")
with open(yaml_path, "w") as f:
    f.write(yaml_content)

# ─────────────────────────────────────────────────────────────────────
# IMPROVEMENT 2: Upgrade from YOLOv8n → YOLOv8s
#
# Old: yolov8n (nano) — fastest but weakest feature extractor.
#      Fine for 400 images but underfits on 3000+ diverse images.
#
# New: yolov8s (small) — ~4x more parameters than nano, still fast
#      on CPU, much better at detecting small plates in full car photos.
#      File size: ~22MB vs ~6MB — totally acceptable for deployment.
# ─────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Starting Training with YOLOv8s...")
print("=" * 60)

model = YOLO('yolov8s.pt')

# ─────────────────────────────────────────────────────────────────────
# IMPROVEMENT 3: Better augmentation params
#
# Old issues:
#   • No degrees — model never saw rotated/angled plates
#   • No scale variation — model never saw plates at different distances
#   • No mosaic tuning — default was fine but not optimal
#   • patience=5 was too low, killed training too early
#
# New params explained:
#   degrees=10    → trains on ±10° rotation (real-world angled shots)
#   scale=0.5     → random zoom 50-150% (close-up AND far plates)
#   mosaic=1.0    → keeps mosaic augmentation at full strength
#   hsv_h/s/v     → color jitter for different lighting conditions
#   fliplr=0.5    → horizontal flip (plates look different mirrored)
#   epochs=60     → more epochs for larger dataset (was 30)
#   patience=15   → wait longer before early stopping (was 5)
# ─────────────────────────────────────────────────────────────────────
results = model.train(
    data=yaml_path,
    epochs=60,
    imgsz=640,
    batch=8,
    patience=15,
    augment=True,
    degrees=10,
    scale=0.5,
    mosaic=1.0,
    hsv_h=0.015,
    hsv_s=0.7,
    hsv_v=0.4,
    fliplr=0.5,
    project=os.path.join(current_dir, 'run'),
    name='anpr_model'
)

# ─────────────────────────────────────────────────────────────────────
# Export to ONNX and copy to backend folder automatically
# ─────────────────────────────────────────────────────────────────────
print("\nExporting to ONNX...")

# Handle re-runs — ultralytics appends a number if folder exists
weights_path = os.path.join(current_dir, 'run', 'anpr_model', 'weights', 'best.pt')
if not os.path.exists(weights_path):
    # Find the latest run folder
    run_dir = os.path.join(current_dir, 'run')
    candidates = sorted([
        d for d in os.listdir(run_dir) if d.startswith('anpr_model')
    ])
    if candidates:
        weights_path = os.path.join(run_dir, candidates[-1], 'weights', 'best.pt')

trained_model = YOLO(weights_path)
export_path   = trained_model.export(format='onnx', dynamic=False)

# Auto-copy to backend so you don't have to do it manually
backend_onnx = os.path.join(current_dir, '..', 'backend', 'best.onnx')
backend_onnx = os.path.normpath(backend_onnx)

if os.path.exists(os.path.dirname(backend_onnx)):
    shutil.copy(export_path, backend_onnx)
    print(f"  [OK] Copied to backend: {backend_onnx}")
else:
    print(f"  [INFO] Backend folder not found. Copy manually:")
    print(f"         {export_path}  →  your backend/best.onnx")

print(f"\n{'='*60}")
print("TRAINING COMPLETE!")
print(f"  ONNX model : {export_path}")
print(f"  Restart your Flask server to load the new model.")
print(f"{'='*60}\n")