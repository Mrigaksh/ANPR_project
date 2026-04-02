import kagglehub
import os
import shutil
import xml.etree.ElementTree as ET
from ultralytics import YOLO
import random

# Download dataset via kagglehub
print("Downloading dataset...")
path = kagglehub.dataset_download("andrewmvd/car-plate-detection")
print(f"Dataset downloaded to {path}")

# Setup YOLO destination directory
current_dir = os.path.dirname(os.path.abspath(__file__))
yolo_dir = os.path.join(current_dir, "yolo_dataset")
os.makedirs(os.path.join(yolo_dir, "images/train"), exist_ok=True)
os.makedirs(os.path.join(yolo_dir, "images/val"), exist_ok=True)
os.makedirs(os.path.join(yolo_dir, "labels/train"), exist_ok=True)
os.makedirs(os.path.join(yolo_dir, "labels/val"), exist_ok=True)

# XML to YOLO bounded-box converter
def convert_xml_to_yolo(xml_file, width, height):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    boxes = []
    # Kaggle dataset structure loop
    for obj in root.findall('object'):
        xmlbox = obj.find('bndbox')
        if xmlbox is None:
            continue
        xn, xx, yn, yx = xmlbox.find('xmin'), xmlbox.find('xmax'), xmlbox.find('ymin'), xmlbox.find('ymax')
        if xn is None or xn.text is None or xx is None or xx.text is None or yn is None or yn.text is None or yx is None or yx.text is None:
            continue
            
        xmin = float(xn.text)
        xmax = float(xx.text)
        ymin = float(yn.text)
        ymax = float(yx.text)
        
        # YOLO center-point offset formula
        x_center = (xmin + xmax) / 2.0 / width
        y_center = (ymin + ymax) / 2.0 / height
        box_w = (xmax - xmin) / width
        box_h = (ymax - ymin) / height
        # Appending format: CLASS_ID X_CENTER Y_CENTER WIDTH HEIGHT
        boxes.append(f"0 {x_center} {y_center} {box_w} {box_h}")
    return boxes

images_src = os.path.join(path, "images")
annotations_src = os.path.join(path, "annotations")
all_files = [f for f in os.listdir(images_src) if f.endswith(('.png', '.jpg', '.jpeg'))]

# Set a seed to make train/val splits reproducible and prevent data leakage
random.seed(42)
random.shuffle(all_files)

# Basic 80/20 train/validation split
split_idx = int(0.8 * len(all_files))
train_files = all_files[:split_idx]
val_files = all_files[split_idx:]

def process_files(files, split_name):
    for f in files:
        img_name = f
        base_name = os.path.splitext(f)[0]
        xml_name = base_name + ".xml"
        txt_name = base_name + ".txt"
        
        img_src_path = os.path.join(images_src, img_name)
        xml_src_path = os.path.join(annotations_src, xml_name)
        
        if not os.path.exists(xml_src_path):
            continue
            
        tree = ET.parse(xml_src_path)
        root = tree.getroot()
        size = root.find('size')
        if size is not None:
            w_elem = size.find('width')
            h_elem = size.find('height')
            if w_elem is not None and w_elem.text is not None and h_elem is not None and h_elem.text is not None:
                w = int(str(w_elem.text))
                h = int(str(h_elem.text))
                yolo_boxes = convert_xml_to_yolo(xml_src_path, w, h)
            
            with open(os.path.join(yolo_dir, "labels", split_name, txt_name), "w") as label_file:
                label_file.write("\n".join(yolo_boxes))
            
            shutil.copy(img_src_path, os.path.join(yolo_dir, "images", split_name, img_name))

print("Processing files: converting XML to localized YOLO TXT format...")
process_files(train_files, "train")
process_files(val_files, "val")
print("File processing complete.")

# Setting up dynamic path generation for the YAML config file
yaml_content = f"""path: {yolo_dir.replace('\\', '/')}
train: images/train
val: images/val

names:
  0: license_plate
"""
yaml_path = os.path.join(yolo_dir, "data.yaml")
with open(yaml_path, "w") as f:
    f.write(yaml_content)

print("Starting Local YOLO Model Training...")
# Initialize Nano Model (smallest / lightest parameters preventing overfitting on 400 images)
model = YOLO('yolov8n.pt')

# Training Params explicitly tuned to evade overfitting (augment on, low epochs, early stopping patience)
results = model.train(
    data=yaml_path,
    epochs=30,      
    imgsz=640,
    batch=16,
    patience=5,
    augment=True,
    project=os.path.join(current_dir, 'run'),
    name='anpr_model'
)

print("Training finished! Preparing to export local model to lightweight ONNX form.")
trained_weights_path = os.path.join(current_dir, 'run', 'anpr_model', 'weights', 'best.pt')
trained_model = YOLO(trained_weights_path)
export_path = trained_model.export(format='onnx', dynamic=False)

print(f"Success! Model completely packaged into single ONNX deployment binary at: {export_path}")
