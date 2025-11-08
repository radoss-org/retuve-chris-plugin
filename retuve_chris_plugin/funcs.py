import math
import os
import statistics
import tempfile
from argparse import ArgumentParser
from typing import Tuple

import numpy as np
from dotenv import load_dotenv
from radstract.math import smart_find_intersection
from radstract.visuals import ReportGenerator
from retuve.batch import run_batch
from retuve.classes.draw import DrawTypes, Overlay
from retuve.defaults.hip_configs import default_US
from retuve.draw import resize_points_for_display
from retuve.funcs import analyse_hip_2DUS_sweep
from retuve.hip_us.classes.general import LandmarksUS
from retuve.hip_us.multiframe import find_graf_plane_manual_features
from retuve.hip_xray.utils import extend_line
from retuve.keyphrases.enums import Colors, HipMode, MetricUS
from retuve_yolo_plugin.ultrasound import (
    get_yolo_model_us,
    yolo_predict_dcm_us,
    yolo_predict_us,
)


def find_alpha_landmarks(
    ilium,
    landmarks,
    config=None,
    max_samples_per_side: int = 50,
    min_ratio: float = 0.40,
) -> Tuple:
    if ilium is None or getattr(ilium, "midline_moved", None) is None:
        raise ValueError("Ilium or ilium.midline_moved is invalid.")
    if not getattr(landmarks, "apex", None):
        raise ValueError("Landmarks.apex is required.")

    midline = np.asarray(ilium.midline_moved, dtype=float)
    if midline.ndim != 2 or midline.shape[1] != 2 or len(midline) < 4:
        raise ValueError("Ilium midline must be an (N, 2) array with N >= 4.")

    apex0_x, apex0_y = float(landmarks.apex[0]), float(landmarks.apex[1])
    landmarks.apexr = None
    landmarks.mid_cov_point_new = None

    if not (
        landmarks
        and landmarks.left
        and landmarks.right
        and landmarks.apex
        and landmarks.point_d
        and landmarks.point_D
    ):
        return landmarks, 0

    def distance(point1, point2):
        if len(point1) != len(point2):
            raise ValueError("Points must have the same dimensions")
        return math.sqrt(sum((p2 - p1) ** 2 for p1, p2 in zip(point1, point2)))

    def equal_sample(arr: np.ndarray, k: int) -> np.ndarray:
        n = len(arr)
        if n <= k:
            return arr
        idx = np.linspace(0, n - 1, k).round().astype(int)
        idx = np.unique(idx)
        return arr[idx]

    xs = midline[:, 1]
    left_side = midline[xs <= apex0_x]
    right_side = midline[xs >= apex0_x]

    if len(left_side) < 2 or len(right_side) < 2:
        raise ValueError("Not enough points on one side of apex.")

    left_smpl = equal_sample(left_side, max_samples_per_side)
    right_smpl = equal_sample(right_side, max_samples_per_side)

    if len(left_smpl) < 2 or len(right_smpl) < 2:
        raise ValueError("Insufficient sampled points after downsampling.")

    def build_valid_pairs(
        smpl: np.ndarray, min_dist: float
    ) -> Tuple[np.ndarray, np.ndarray]:
        n = len(smpl)
        smpl_xy = smpl[:, [1, 0]].astype(float)

        diff = smpl_xy[np.newaxis, :, :] - smpl_xy[:, np.newaxis, :]
        dists = np.linalg.norm(diff, axis=2)

        mask = (dists >= min_dist) & (~np.eye(n, dtype=bool))
        i_idx, j_idx = np.where(mask)

        if len(i_idx) == 0:
            return (
                np.array([], dtype=float).reshape(0, 2),
                np.array([], dtype=float).reshape(0, 2),
            )

        first_points = smpl_xy[i_idx]
        second_points = smpl_xy[j_idx]
        return first_points, second_points

    min_left_dist = distance(landmarks.left, landmarks.apex) * min_ratio
    min_right_dist = distance(landmarks.right, landmarks.apex) * min_ratio

    left_first, left_second = build_valid_pairs(left_smpl, min_left_dist)
    right_first, right_second = build_valid_pairs(right_smpl, min_right_dist)

    if len(left_first) == 0 or len(right_first) == 0:
        raise ValueError("No valid side pairs found.")

    def compute_all_angles(
        left_first: np.ndarray,
        left_second: np.ndarray,
        right_first: np.ndarray,
        right_second: np.ndarray,
    ) -> np.ndarray:
        A_xy = left_first[:, np.newaxis, :]
        B_xy = left_second[:, np.newaxis, :]
        R1_xy = right_first[np.newaxis, :, :]
        R2_xy = right_second[np.newaxis, :, :]

        BA = A_xy - B_xy
        dvec = R2_xy - R1_xy

        nBA = np.linalg.norm(BA, axis=2, keepdims=True)
        nd = np.linalg.norm(dvec, axis=2, keepdims=True)

        nBA = np.where(nBA == 0, 1.0, nBA)
        nd = np.where(nd == 0, 1.0, nd)

        u = dvec / nd
        BC = u

        cos_t = np.sum(BA * BC, axis=2) / (nBA[:, :, 0] * 1.0)
        cos_t = np.clip(cos_t, -1.0, 1.0)

        theta = np.degrees(np.arccos(cos_t))
        theta = np.where(theta > 90.0, 180.0 - theta, theta)
        return theta

    angles = compute_all_angles(
        left_first, left_second, right_first, right_second
    )

    valid_mask = np.isfinite(angles)
    valid_angles = angles[valid_mask]

    if len(valid_angles) == 0:
        raise ValueError("No valid angles for filtering.")

    mean_angle = np.mean(valid_angles)
    std_angle = np.std(valid_angles)
    lower_bound = mean_angle - std_angle * 2
    upper_bound = mean_angle + std_angle * 2

    filtered_mask = (angles >= lower_bound) & (angles <= upper_bound)
    filtered_angles = np.where(filtered_mask, angles, np.nan)

    if np.all(np.isnan(filtered_angles)):
        raise ValueError(
            "All landmark configurations filtered out by std bounds."
        )

    best_idx = np.unravel_index(
        np.nanargmax(filtered_angles), filtered_angles.shape
    )
    best_angle = float(filtered_angles[best_idx])

    if best_angle <= 0.0:
        raise ValueError("Best angle computation failed.")

    i_left, i_right = best_idx
    A_xy = left_first[i_left]
    B_xy = left_second[i_left]
    R1_xy = right_first[i_right]
    R2_xy = right_second[i_right]

    left_new = (float(A_xy[0]), float(A_xy[1]))
    apexl = (float(B_xy[0]), float(B_xy[1]))
    apexr = (float(R1_xy[0]), float(R1_xy[1]))
    right_new = (float(R2_xy[0]), float(R2_xy[1]))

    if left_new[0] > apexl[0]:
        left_new, apexl = apexl, left_new

    if right_new[0] < apexr[0]:
        right_new, apexr = apexr, right_new

    landmarks.left_new = left_new
    landmarks.apexl = apexl
    landmarks.apexr = apexr
    landmarks.right_new = right_new

    landmarks.mid_cov_point_new = smart_find_intersection(
        landmarks.apexl,
        landmarks.left_new,
        landmarks.point_d,
        landmarks.point_D,
    )

    return landmarks, round(best_angle, 2)


def find_alpha_angle(points: LandmarksUS) -> float:
    if not (
        points
        and points.apexr
        and points.left_new
        and points.apexl
        and points.right_new
    ):
        return 0.0

    A = np.array(points.left_new, dtype=float)
    B = np.array(points.apexl, dtype=float)
    C = np.array(points.right_new, dtype=float)

    AB = A - B
    BC = C - np.array(points.apexr, dtype=float)

    norm_AB = np.linalg.norm(AB)
    norm_BC = np.linalg.norm(BC)

    if norm_AB == 0 or norm_BC == 0:
        return 0.0

    cos_theta = np.dot(AB, BC) / (norm_AB * norm_BC)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)

    theta_deg = np.degrees(np.arccos(cos_theta))

    if theta_deg > 90.0:
        theta_deg = 180.0 - theta_deg

    if theta_deg > 89.9:
        theta_deg = 0

    return round(theta_deg, 2)


def find_coverage(landmarks: LandmarksUS) -> float:
    if not (
        landmarks
        and landmarks.mid_cov_point_new
        and landmarks.point_D
        and landmarks.point_d
        and landmarks.point_D[1] > landmarks.point_d[1]
    ):
        return 0

    coverage = abs(
        landmarks.mid_cov_point_new[1] - landmarks.point_D[1]
    ) / abs(landmarks.point_D[1] - landmarks.point_d[1])

    if landmarks.mid_cov_point_new[1] > landmarks.point_D[1]:
        coverage = 0

    if coverage > 1:
        coverage = 0

    return round(coverage, 3)


def replace_alpha(hip, seg_frame_objs, config):
    ilium = None
    for obj in seg_frame_objs:
        if obj.empty:
            continue
        if obj.cls.value == 0:
            ilium = obj
            break

    if not ilium:
        return None, None

    hip.landmarks, _ = find_alpha_landmarks(ilium, hip.landmarks, config)
    alpha_angle = find_alpha_angle(hip.landmarks)
    coverage = find_coverage(hip.landmarks)

    org = None
    for metric in hip.metrics:
        if metric.name == "alpha" and metric.value > 0:
            org = metric.value
            if alpha_angle is not None:
                metric.value = alpha_angle
        if metric.name == "coverage" and metric.value > 0:
            if coverage is not None:
                metric.value = coverage

    return org, None


def alpha_landmarks(hip, seg_frame_objs, overlay: Overlay, config):
    ilium = None
    for obj in seg_frame_objs:
        if obj.empty:
            continue
        if obj.cls.value == 0:
            ilium = obj
            break

    if not ilium or not hip.landmarks:
        return None, None

    if hip.landmarks.apexr is None:
        return None, None

    overlay.operations[DrawTypes.POINTS] = []

    landmarks = resize_points_for_display(
        [
            hip.landmarks.apexr,
            hip.landmarks.apexl,
            hip.landmarks.left_new,
            hip.landmarks.right_new,
            hip.landmarks.mid_cov_point_new,
        ],
        seg_frame_objs,
    )

    overlay.operations[DrawTypes.LINES] = []

    intersection_point = smart_find_intersection(
        landmarks[2], landmarks[4], landmarks[0], landmarks[3]
    )

    line3 = [hip.landmarks.point_d, hip.landmarks.point_D]

    line1 = list(extend_line(landmarks[2], landmarks[4], scale=1.5))
    line2 = list(extend_line(intersection_point, landmarks[3], scale=1.5))

    # overlay.draw_skeleton(ilium.midline_moved)

    overlay.draw_lines([list(line1), list(line2), list(line3)])

    return overlay


def scan_quality_graf(hip_datas, results, config):
    graf_confs, graf_frame = find_graf_plane_manual_features(
        hip_datas, results, config, just_graf_confs=True
    )
    for metric in hip_datas[graf_frame].metrics:
        if metric.name == "alpha" and metric.value > 0:
            alpha = metric.value
    if graf_confs is None:
        return 0

    value = min(10, round((graf_confs[graf_frame] - alpha) / 60, 2))
    return value


default_US.hip.per_frame_metric_functions = [("original_alpha", replace_alpha)]
default_US.hip.post_draw_functions = [("alpha_landmarks", alpha_landmarks)]
# default_US.hip.full_metric_functions = [
#     ("Scan Quality (Out of 10)", scan_quality_graf),
# ]

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"

if os.getenv("DEV"):
    IMAGE_DIR = "."
else:
    IMAGE_DIR = "/home/chris"

parser = ArgumentParser(description=DISPLAY_TITLE)


def get_retuve_report(dicom, model):
    try:
        hip_data, hip_image, dev_metrics, video_clip = analyse_hip_2DUS_sweep(
            image=dicom,
            keyphrase=default_US,  # Adjust based on your config keyphrase
            modes_func=yolo_predict_dcm_us,
            modes_func_kwargs_dict={"model": model},
        )

        metric_names = list(
            set([metric.name.capitalize() for metric in hip_data.metrics])
        )
        metric_names.sort()  # Sort for consistent ordering

        headers = ["Metric Name", "Value"]
        values = [
            [
                metric.name
                for metric in hip_data.metrics
                if metric.name != "original_alpha"
            ],
            [
                str(metric.value)
                for metric in hip_data.metrics
                if metric.name != "original_alpha"
            ],
        ]

        # values needs to be rotated 90 degrees
        values = list(zip(*values))

        r_gen = ReportGenerator(
            title=f"Hip Analysis Report - {dicom.PatientID} - {dicom.InstanceNumber}",
            footer_text="Test/Example report created by https://github.com/radoss-org/radstract",
            footer_website="https://radoss.org",
            footer_email="info@radoss.org",
            logo_path=f"{IMAGE_DIR}/images/logo.png",
        )

        r_gen.add_subtitle("Ultrasound DDH Analysis", level=1)

        r_gen.add_paragraph(
            "This report contains the results of a graf analysis of a 2DUS image of a hip."
        )

        r_gen.add_warning(
            "Over 50% of hips can go from moderately dysplastic to normal and vice-versa purely with probe tilt (Jaremko et al., 2014 - Probe Orientation)"
        )

        r_gen.add_warning(
            "Alpha angle is expected to increase with age. At 16 weeks, alpha angle is on average 5 degrees higher than at 1-8 weeks. (Hareendranathan et al., 2022 - Normal variation))"
        )

        r_gen.add_highlights(
            report_success=None,
            status_text="Research Only!",
            highlight1=f"{values[0][1]}",
            highlight1_label="Alpha Angle",
            highlight2=f"{values[1][1]}",
            highlight2_label="Coverage",
        )

        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".png"
        ) as temp_file:
            hip_image.save(temp_file.name)

            r_gen.add_image(
                image_path=temp_file.name,
                caption="Hip Image",
                max_width="90%",
            )

        r_gen.add_page_break()
        r_gen.add_subtitle("Metric Analysis", level=1)
        r_gen.add_table(data=values, headers=headers)

    except Exception as e:
        # Generate a minimal error report
        r_gen = ReportGenerator(
            title="Hip Analysis Report - Error",
            footer_text="For assistance, contact amcarth1@ualberta.ca",
            footer_website="https://radoss.org",
            footer_email="amcarth1@ualberta.ca",
            logo_path=f"{IMAGE_DIR}/images/logo.png",
        )

        r_gen.add_subtitle("Ultrasound DDH Analysis - Error", level=1)
        r_gen.add_paragraph(
            "An error occurred while generating the report. "
            "Please contact amcarth1@ualberta.ca for assistance."
        )

        r_gen.add_highlights(
            report_success=False,
            status_text="Research Only!",
            highlight1=f"Nan",
            highlight1_label="Alpha Angle",
            highlight2=f"Nan",
            highlight2_label="Coverage",
        )

    return r_gen
