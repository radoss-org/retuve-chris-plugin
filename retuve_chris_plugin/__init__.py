from retuve_chris_plugin.utils import suppress_fonttools_logs

suppress_fonttools_logs()

import os
from argparse import Namespace
from datetime import datetime, timezone

import pydicom
from chris_plugin import PathMapper, chris_plugin
from dotenv import load_dotenv

from retuve_chris_plugin.config import parser
from retuve_chris_plugin.schedule import login, place_lock, release_lock

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"
ENABLE_UPLOAD = True

DEV = os.getenv("DEV")


@chris_plugin(parser=parser, title=DISPLAY_TITLE)
def main(options: Namespace, inputdir, outputdir):
    token = options.token
    url = options.chris_api_url
    login(url, token=token)
    my_iso = (datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not DEV:
        place_lock(url, my_iso)

    from retuve_yolo_plugin.ultrasound import get_yolo_model_us

    from retuve_chris_plugin.config import apply_config
    from retuve_chris_plugin.funcs import get_retuve_report
    from retuve_chris_plugin.orthanc import upload_dicom_to_orthanc

    url = options.chris_api_url

    default_US = apply_config(options, inputdir, outputdir)

    if options.github_secret is not None:
        os.environ["GITHUB_PAT"] = options.github_secret
    model = get_yolo_model_us(default_US, options.model_url)

    mapper = PathMapper.file_mapper(inputdir, outputdir, glob="**/*.dcm")
    store_mapper = []
    for input_file, output_file in mapper:
        dicom = pydicom.dcmread(input_file)

        if ENABLE_UPLOAD:
            # Upload the original output file (processed DICOM)
            upload_success = upload_dicom_to_orthanc(input_file)
            if upload_success:
                print(f"Successfully uploaded output file: {output_file}")
            else:
                print(f"Failed to upload output file: {output_file}")

        store_mapper.append((input_file, output_file))

    try:
        for input_file, output_file in store_mapper:
            dicom = pydicom.dcmread(input_file)

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
    except Exception as e:
        print(e)
    finally:
        if not DEV:
            release_lock(url, my_iso)
