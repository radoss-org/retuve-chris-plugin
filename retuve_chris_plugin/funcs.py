import os
import tempfile
from argparse import ArgumentParser

from dotenv import load_dotenv
from radstract.visuals import ReportGenerator
from retuve.defaults.hip_configs import default_US
from retuve.funcs import analyse_hip_2DUS_sweep
from retuve_yolo_plugin.ultrasound import yolo_predict_dcm_us

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"

if os.getenv("DEV") == "True":
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

        metric_names = list(set([metric.name for metric in hip_data.metrics]))
        metric_names.sort()  # Sort for consistent ordering

        headers = ["Metric Name", "Value"]
        values = [
            [metric.name for metric in hip_data.metrics],
            [str(metric.value) for metric in hip_data.metrics],
        ]

        # values needs to be rotated 90 degrees
        values = list(zip(*values))

        r_gen = ReportGenerator(
            title="Hip Analysis Report",
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
