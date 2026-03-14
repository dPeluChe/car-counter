#!/usr/bin/env python3
"""Find optimal line position by analyzing first tracker appearances"""
from ultralytics import YOLO
import cv2 as cv
import numpy as np
from sort import Sort

model = YOLO("models/yolo/yolov8l.pt")
vid = cv.VideoCapture("assets/test_2.mp4")

height = int(vid.get(cv.CAP_PROP_FRAME_HEIGHT))
width = int(vid.get(cv.CAP_PROP_FRAME_WIDTH))

tracker = Sort(max_age=22, min_hits=2, iou_threshold=0.3)
first_appearances = {}

frame_count = 0
while frame_count < 200:  # Analyze first 200 frames
    ret, frame = vid.read()
    if not ret:
        break
    
    frame_count += 1
    result = model(frame, stream=True, verbose=False)
    
    detections = np.empty((0, 5))
    for r in result:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            
            class_names = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck"]
            if cls < len(class_names) and class_names[cls] in ["car", "truck", "bus", "motorbike"]:
                detections = np.vstack((detections, [x1, y1, x2, y2, conf]))
    
    tracker_updates = tracker.update(detections)
    
    for update in tracker_updates:
        x1, y1, x2, y2, id = update
        id = int(id)
        cy = int((y1 + y2) / 2)
        
        if id not in first_appearances:
            first_appearances[id] = cy
            print(f"Frame {frame_count}: Tracker id={id} first appeared at cy={cy} (rel={cy/height:.2f})")

vid.release()

if first_appearances:
    min_cy = min(first_appearances.values())
    max_cy = max(first_appearances.values())
    avg_cy = sum(first_appearances.values()) / len(first_appearances)
    
    print(f"\n=== ANALYSIS ===")
    print(f"Video height: {height}px")
    print(f"Trackers first appear between y={min_cy} (rel={min_cy/height:.2f}) and y={max_cy} (rel={max_cy/height:.2f})")
    print(f"Average first appearance: y={avg_cy:.0f} (rel={avg_cy/height:.2f})")
    print(f"\nRECOMMENDATION: Use --line-y {(min_cy-50)/height:.2f} to catch vehicles before they're tracked")
    print(f"OR: Use --min-hits 1 with current line position")
else:
    print("No trackers found in first 200 frames")
