# Importation
from ultralytics import YOLO
import cv2 as cv
import cvzone
import math
import numpy as np
import argparse
from sort import *

# CLI params (moved up before initialization)
parser = argparse.ArgumentParser()
parser.add_argument("--mode", type=str, choices=["street", "roundabout-test"], default="street",
                    help="street: normal counting mode | roundabout-test: detection only for testing")
parser.add_argument("--video", type=str, default="assets/test_2.mp4",
                    help="Path to input video file")
parser.add_argument("--directions", type=int, choices=[1,2], default=2)
parser.add_argument("--line-y", dest="line_y", type=float, default=0.5)
parser.add_argument("--line-y2", dest="line_y2", type=float, default=None)
parser.add_argument("--tol", dest="tol", type=int, default=10)
parser.add_argument("--min-hits", dest="min_hits", type=int, default=2)
parser.add_argument("--conf-threshold", dest="conf_threshold", type=float, default=0.3,
                    help="Confidence threshold for detections (0.0-1.0). Lower = more detections")
parser.add_argument("--max-age", dest="max_age", type=int, default=30,
                    help="Max frames to keep alive a track without detections. Higher = more stable for small objects")
parser.add_argument("--iou-threshold", dest="iou_threshold", type=float, default=0.2,
                    help="IOU threshold for SORT tracker. Lower = better for small/distant objects")
args = parser.parse_args()

# Initialization and variable naming
model = YOLO("models/yolo/yolov11l.pt")
vid = cv.VideoCapture(args.video)

class_names = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck", "boat",
              "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
              "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
              "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
              "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
              "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
              "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa", "pottedplant", "bed",
              "diningtable", "toilet", "tvmonitor", "laptop", "mouse", "remote", "keyboard", "cell phone",
              "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
              "teddy bear", "hair drier", "toothbrush"]


# Tracker with optimized parameters for small objects from aerial footage
tracker = Sort(max_age=args.max_age, min_hits=args.min_hits, iou_threshold=args.iou_threshold)
line_up = None
line_down = None
count_up = []
count_down = []
total_count = []
id_to_class = {}
class_totals = {}
class_up = {}
class_down = {}
id_prev_cy = {}  # Track previous y position for direction detection
mask = cv.imread("assets/mask.png") # For blocking out noise
mask_resized = False

# Setting up video writer properties (for saving the output result)
width = int(vid.get(cv.CAP_PROP_FRAME_WIDTH))
height = int(vid.get(cv.CAP_PROP_FRAME_HEIGHT))
fps = vid.get(cv.CAP_PROP_FPS)
video_writer = cv.VideoWriter(("result.mp4"), cv.VideoWriter_fourcc("m", "p", "4", "v"),
                              fps, (width, height))

def iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter = inter_w * inter_h
    if inter == 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = area_a + area_b - inter
    if union <= 0:
        return 0.0
    return inter / union

while True:
    ref, frame = vid.read()
    if not ref or frame is None:
        break
    if not mask_resized:
        if mask is None:
            mask = np.ones_like(frame, dtype=np.uint8) * 255
        elif mask.shape[:2] != frame.shape[:2]:
            mask = cv.resize(mask, (frame.shape[1], frame.shape[0]))
        mask_resized = True

    frame_region = cv.bitwise_and(frame, mask)
    result = model(frame_region, stream=True)

    # Graphics overlay (only in street mode)
    if args.mode == "street":
        frame_graphics = cv.imread("assets/graphics.png", cv.IMREAD_UNCHANGED)
        frame = cvzone.overlayPNG(frame, frame_graphics, (0,0))
        frame_graphics1 = cv.imread("assets/graphics1.png", cv.IMREAD_UNCHANGED)
        frame = cvzone.overlayPNG(frame, frame_graphics1, (420,0))

    detections = np.empty((0, 5))
    det_classes = []

    for r in result:
        boxes = r.boxes
        for box in boxes:
            # Bounding boxes
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            w, h = (x2-x1), (y2-y1)

            #Detection confidence
            conf = math.floor(box.conf[0]*100)/100

            # Class names
            cls = int(box.cls[0])
            vehicle_names = class_names[cls]

            # Filter: only vehicles with sufficient confidence
            if vehicle_names in ["car", "truck", "bus", "motorbike"] and conf >= args.conf_threshold:
                current_detection = np.array([x1, y1, x2, y2, conf])
                detections = np.vstack((detections, current_detection))
                det_classes.append(vehicle_names)

    # Tracking codes
    tracker_updates = tracker.update(detections)

    # Compute dynamic lines based on video size (only in street mode)
    if args.mode == "street":
        if line_up is None:
            line_up = [0, int(height * args.line_y), width, int(height * args.line_y)]
        if line_down is None and args.directions == 2:
            if args.line_y2 is not None:
                line_down = [0, int(height * args.line_y2), width, int(height * args.line_y2)]
            else:
                line_down = [0, int(height * (1 - args.line_y)), width, int(height * (1 - args.line_y))]

        # Tracking lines
        if line_up is not None:
            cv.line(frame, (line_up[0], line_up[1]), (line_up[2], line_up[3]), (0, 0, 255), thickness = 3)
        if line_down is not None:
            cv.line(frame, (line_down[0] ,line_down[1]), (line_down[2], line_down[3]), (0, 0, 255), thickness = 3)

    # Geting bounding boxes points and vehicle ID
    for update in tracker_updates:
        x1, y1, x2, y2, id = update
        x1, y1, x2, y2, id = int(x1), int(y1), int(x2), int(y2), int(id)
        w, h = (x2-x1), (y2-y1)

        # Getting tracking marker
        cx, cy = (x1+w//2), (y1+h//2)
        cv.circle(frame, (cx, cy), 5, (255, 0, 255), cv.FILLED)
        
        # Track previous position for direction detection
        prev_cy = id_prev_cy.get(id, cy)
        id_prev_cy[id] = cy
        moving_down = cy > prev_cy
        moving_up = cy < prev_cy

        # Roundabout test mode: just track, no counting
        if args.mode == "roundabout-test":
            # Match class for this ID
            if id not in id_to_class:
                clsname = None
                for det_cls, det_box in zip(det_classes, detections):
                    if iou_xyxy(det_box[:4], [x1, y1, x2, y2]) > 0.5:
                        clsname = det_cls
                        break
                if clsname:
                    id_to_class[id] = clsname
                    if id not in total_count:
                        total_count.append(id)
                        print(f"🚗 Detected vehicle id={id} class={clsname} at ({cx},{cy})")
            
            # Draw bounding box and ID
            cvzone.cornerRect(frame, (x1, y1, w, h), l=5, colorR=(0, 255, 0), rt=2)
            cvzone.putTextRect(frame, f'{id}', (x1, y1-10), scale=1.5, thickness=2, colorR=(0,255,0))
            continue

        # Code for upper line (crossing detection with direction) - STREET MODE ONLY
        if line_up is not None and (line_up[0] <= cx <= line_up[2]) and (line_up[1] - args.tol <= cy <= line_up[3] + args.tol):
            # Check if crossing from top to bottom (moving down) or bottom to top (moving up)
            crossed_down = prev_cy < line_up[1] and cy >= line_up[1]
            crossed_up = prev_cy > line_up[1] and cy <= line_up[1]
            
            if (crossed_down or crossed_up) and total_count.count(id) == 0:
                total_count.append(id)
                cv.line(frame, (line_up[0], line_up[1]), (line_up[2], line_up[3]), (0, 255, 0), thickness = 3)
                if count_up.count(id) == 0:
                    count_up.append(id)
                clsname = None
                for det_cls, det_box in zip(det_classes, detections):
                    if iou_xyxy(det_box[:4], [x1, y1, x2, y2]) > 0.5:
                        clsname = det_cls
                        break
                id_to_class[id] = clsname
                class_totals[clsname] = class_totals.get(clsname, 0) + 1
                class_up[clsname] = class_up.get(clsname, 0) + 1
                direction = "DOWN" if crossed_down else "UP"
                print(f"✓ Counted id={id} class={clsname} direction={direction} at y={cy}")

        # Code for lower line (crossing detection with direction)
        if line_down is not None and (line_down[0] <= cx <= line_down[2]) and (line_down[1] - args.tol <= cy <= line_down[3] + args.tol):
            # Check if crossing from top to bottom or bottom to top
            crossed_down = prev_cy < line_down[1] and cy >= line_down[1]
            crossed_up = prev_cy > line_down[1] and cy <= line_down[1]
            
            if (crossed_down or crossed_up) and total_count.count(id) == 0:
                total_count.append(id)
                cv.line(frame, (line_down[0], line_down[1]), (line_down[2], line_down[3]), (0, 255, 0), thickness = 3)
                if count_down.count(id) == 0:
                    count_down.append(id)
                clsname = None
                for det_cls, det_box in zip(det_classes, detections):
                    if iou_xyxy(det_box[:4], [x1, y1, x2, y2]) > 0.5:
                        clsname = det_cls
                        break
                id_to_class[id] = clsname
                class_totals[clsname] = class_totals.get(clsname, 0) + 1
                class_down[clsname] = class_down.get(clsname, 0) + 1
                direction = "DOWN" if crossed_down else "UP"
                print(f"✓ Counted id={id} class={clsname} direction={direction} at y={cy}")

        # Adding rectangles and texts (street mode)
        cvzone.cornerRect(frame, (x1, y1, w, h), l=5, colorR=(255, 0, 255), rt=1)
        cvzone.putTextRect(frame, f'{id}', (x1, y1), scale=1, thickness=2)

    # Adding texts to graphics
    if args.mode == "street":
        cv.putText(frame, str(len(total_count)), (255, 100), cv.FONT_HERSHEY_PLAIN, 5, (200, 50, 200), thickness=7)
        cv.putText(frame, str(len(count_up)), (600, 85), cv.FONT_HERSHEY_PLAIN, 5, (200, 50, 200), thickness=7)
        cv.putText(frame, str(len(count_down)), (850, 85), cv.FONT_HERSHEY_PLAIN, 5, (200, 50, 200), thickness=7)
    elif args.mode == "roundabout-test":
        # Show detection stats for roundabout with tracking quality info
        info_text = f"Detected: {len(total_count)} vehicles | Active: {len(tracker_updates)}"
        cv.putText(frame, info_text, (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        # Show parameters being used
        params_text = f"conf>={args.conf_threshold} | max_age={args.max_age} | iou<={args.iou_threshold}"
        cv.putText(frame, params_text, (10, 60), cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

    cv.imshow("vid", frame)

    # Saving the video frame output
    video_writer.write(frame)

    cv.waitKey(1)

# Final console summary
def _sanitize_counts(d):
    out = {}
    for k, v in d.items():
        key = k if k is not None else 'unknown'
        out[key] = out.get(key, 0) + v
    return dict(sorted(out.items(), key=lambda x: (-x[1], x[0])))

print("\n===== SUMMARY =====")
print(f"Mode: {args.mode}")
print(f"Video: {args.video}")
print(f"\nDetection parameters:")
print(f"  Confidence threshold: {args.conf_threshold}")
print(f"  Min hits: {args.min_hits}")
print(f"  Max age: {args.max_age} frames")
print(f"  IOU threshold: {args.iou_threshold}")

if args.mode == "roundabout-test":
    print(f"\n🚗 Total vehicles detected: {len(total_count)}")
    totals_s = _sanitize_counts(id_to_class)
    if totals_s:
        print("\nVehicle types detected:")
        type_counts = {}
        for vehicle_type in totals_s.values():
            type_counts[vehicle_type] = type_counts.get(vehicle_type, 0) + 1
        for k, v in sorted(type_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {k}: {v}")
else:
    print(f"directions={args.directions} tol={args.tol}")
    if line_up is not None:
        print(f"line_up_y={line_up[1]} (rel={line_up[1]/height:.2f})")
    if line_down is not None:
        print(f"line_down_y={line_down[1]} (rel={line_down[1]/height:.2f})")

    print(f"Total counted: {len(total_count)}")
    print(f"Up: {len(count_up)}  Down: {len(count_down)}")

    totals_s = _sanitize_counts(class_totals)
    up_s = _sanitize_counts(class_up)
    down_s = _sanitize_counts(class_down)
    if totals_s:
        print("Per-class totals:")
        for k, v in totals_s.items():
            print(f"  {k}: {v}")
    if up_s:
        print("Per-class UP:")
        for k, v in up_s.items():
            print(f"  {k}: {v}")
    if down_s:
        print("Per-class DOWN:")
        for k, v in down_s.items():
            print(f"  {k}: {v}")

# Closing down everything
vid.release()
cv.destroyAllWindows()
video_writer.release()