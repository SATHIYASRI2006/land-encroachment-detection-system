from __future__ import annotations

import os

import cv2
import numpy as np


def validate_plot_id(plot_id) -> bool:
    return plot_id is not None and str(plot_id).strip() != ""


def safe_imread(path: str):
    if not os.path.exists(path):
        raise ValueError(f"Missing image file: {path}")

    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img


def get_risk_level(change_percent: float) -> str:
    if change_percent >= 16:
        return "High"
    if change_percent >= 10:
        return "Medium"
    return "Low"


def _edge_change_ratio(before_gray, after_gray, roi_mask) -> float:
    before_edges = cv2.Canny(before_gray, 60, 150)
    after_edges = cv2.Canny(after_gray, 60, 150)
    edge_delta = cv2.absdiff(before_edges, after_edges)
    active = np.count_nonzero(cv2.bitwise_and(edge_delta, roi_mask))
    roi_pixels = max(np.count_nonzero(roi_mask), 1)
    return (active / roi_pixels) * 100


def _cluster_shift_score(before_bgr, after_bgr, roi_mask) -> float:
    masked_pixels = roi_mask > 0
    before_pixels = before_bgr[masked_pixels].reshape(-1, 3).astype(np.float32)
    after_pixels = after_bgr[masked_pixels].reshape(-1, 3).astype(np.float32)

    if len(before_pixels) < 32 or len(after_pixels) < 32:
        return 0.0

    criteria = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        12,
        1.0,
    )
    cluster_count = min(4, len(before_pixels), len(after_pixels))
    _, _, before_centers = cv2.kmeans(
        before_pixels,
        cluster_count,
        None,
        criteria,
        4,
        cv2.KMEANS_PP_CENTERS,
    )
    _, _, after_centers = cv2.kmeans(
        after_pixels,
        cluster_count,
        None,
        criteria,
        4,
        cv2.KMEANS_PP_CENTERS,
    )

    before_centers = before_centers[np.argsort(before_centers.mean(axis=1))]
    after_centers = after_centers[np.argsort(after_centers.mean(axis=1))]
    center_shift = np.linalg.norm(after_centers - before_centers, axis=1).mean()
    return float(center_shift / 6.0)


def analyze_satellite(before_path: str, after_path: str, image_size: tuple[int, int]):
    before = cv2.resize(safe_imread(before_path), image_size)
    after = cv2.resize(safe_imread(after_path), image_size)

    before_gray = cv2.cvtColor(before, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY)

    # Ignore border overlays and labels that create false positives.
    margin_y = max(24, int(image_size[1] * 0.08))
    margin_x = max(24, int(image_size[0] * 0.08))
    roi = np.zeros_like(before_gray, dtype=np.uint8)
    roi[margin_y : image_size[1] - margin_y, margin_x : image_size[0] - margin_x] = 255

    before_gray = cv2.GaussianBlur(before_gray, (7, 7), 0)
    after_gray = cv2.GaussianBlur(after_gray, (7, 7), 0)

    diff = cv2.absdiff(before_gray, after_gray)
    diff = cv2.bitwise_and(diff, roi)

    _, thresh = cv2.threshold(diff, 32, 255, cv2.THRESH_BINARY)

    kernel_small = np.ones((3, 3), np.uint8)
    kernel_large = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_small)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel_large)
    thresh = cv2.dilate(thresh, kernel_small, iterations=1)

    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    filtered_thresh = np.zeros_like(thresh)
    contour_areas = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 120:
            continue
        contour_areas.append(area)
        cv2.drawContours(filtered_thresh, [contour], -1, 255, thickness=cv2.FILLED)

    roi_pixels = max(np.count_nonzero(roi), 1)
    active_pixels = np.count_nonzero(filtered_thresh)
    raw_change_percent = (active_pixels / roi_pixels) * 100
    mean_diff = float(diff[roi > 0].mean()) if np.count_nonzero(roi) else 0.0
    edge_change = _edge_change_ratio(before_gray, after_gray, roi)
    cluster_shift = _cluster_shift_score(before, after, roi)

    # Hybrid score: blends classic differencing, structural edge movement,
    # and unsupervised cluster drift to reduce false positives from lighting.
    change_percent = (
        (mean_diff / 4.6)
        + (raw_change_percent * 0.05)
        + (edge_change * 0.6)
        + cluster_shift
    )
    normalized_regions = min(len(contour_areas), 10) / 10
    normalized_edges = min(edge_change / 8, 1)
    normalized_change = min(change_percent / 18, 1)
    confidence = (
        56
        + (normalized_change * 20)
        + (normalized_regions * 12)
        + (normalized_edges * 10)
    )

    return round(change_percent, 2), round(min(confidence, 99.0), 2), filtered_thresh


def draw_changes(after_path: str, thresh, plot_id: str, data_folder: str, image_size: tuple[int, int]):
    img = cv2.resize(safe_imread(after_path), image_size)
    overlay = img.copy()
    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    for contour in contours:
        if cv2.contourArea(contour) < 120:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), -1)
        cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 3)
        cv2.putText(
            img,
            "Encroachment",
            (x, max(y - 8, 22)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )

    img = cv2.addWeighted(overlay, 0.22, img, 0.78, 0)

    output_name = f"{plot_id}_output.png"
    output_path = os.path.join(data_folder, output_name)
    cv2.imwrite(output_path, img)
    return output_name
