import os
from argparse import Namespace

import pydicom
from chris_plugin import PathMapper, chris_plugin
from dotenv import load_dotenv
from retuve_yolo_plugin.ultrasound import get_yolo_model_us

from retuve_chris_plugin.config import apply_config, parser
from retuve_chris_plugin.funcs import get_retuve_report
from retuve_chris_plugin.orthanc import upload_dicom_to_orthanc
from retuve_chris_plugin.schedule import wait_for_cpu_drop

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"
ENABLE_UPLOAD = True


@chris_plugin(parser=parser, title=DISPLAY_TITLE)
def main(options: Namespace, inputdir, outputdir):

    default_US = apply_config(options, inputdir, outputdir)

    if options.github_secret is not None:
        os.environ["GITHUB_PAT"] = options.github_secret
    model = get_yolo_model_us(default_US, options.model_url)

    mapper = PathMapper.file_mapper(inputdir, outputdir, glob="**/*.dcm")
    for input_file, output_file in mapper:
        dicom = pydicom.dcmread(input_file)

        if ENABLE_UPLOAD:
            # Upload the original output file (processed DICOM)
            upload_success = upload_dicom_to_orthanc(input_file)
            if upload_success:
                print(f"Successfully uploaded output file: {output_file}")
            else:
                print(f"Failed to upload output file: {output_file}")

        wait_for_cpu_drop()

        r_gen = get_retuve_report(dicom, model)

        r_gen.save_pdf(str(output_file).replace(".dcm", ".pdf"))

        report_file = str(output_file).replace(".dcm", "-report.dcm")

        r_gen.save_to_dicom_study(
            output_path=report_file,
            dicom_tags=dicom,
            series_number=999,
            series_description="Hip Analysis Report",
            hide_videos=True,
        )

        # Upload files to Orthanc if enabled
        if ENABLE_UPLOAD:
            # Upload the report file
            report_upload_success = upload_dicom_to_orthanc(
                str(report_file), original_dicom=dicom
            )
            if report_upload_success:
                print(f"Successfully uploaded report file: {report_file}")
            else:
                print(f"Failed to upload report file: {report_file}")
        else:
            print("Upload disabled - files saved locally only")
