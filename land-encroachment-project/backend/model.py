import cv2
import numpy as np
import uuid
import os

def detect_encroachment(before_path, after_path):

    before = cv2.imread(before_path)
    after = cv2.imread(after_path)

    before = cv2.resize(before, (500, 500))
    after = cv2.resize(after, (500, 500))

    diff = cv2.absdiff(before, after)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)

    _, thresh = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)

    change_pixels = np.sum(thresh > 0)
    total_pixels = thresh.size

    percentage = round((change_pixels / total_pixels) * 100, 2)

    if percentage < 5:
        risk = "Low"
    elif percentage < 15:
        risk = "Medium"
    else:
        risk = "High"

    after[thresh > 0] = [0, 0, 255]

    filename = f"{uuid.uuid4().hex}.png"
    output_path = os.path.join("data", filename)

    cv2.imwrite(output_path, after)

    return percentage, risk, filename