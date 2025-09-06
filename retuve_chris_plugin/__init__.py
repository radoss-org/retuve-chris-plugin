import inspect
import os
import tempfile
from argparse import ArgumentParser, Namespace
from typing import Any

import pydicom
from chris_plugin import PathMapper, chris_plugin
from dotenv import load_dotenv
from pynetdicom import AE
from pynetdicom.sop_class import *
from radstract.visuals import ReportGenerator
from retuve.defaults.hip_configs import default_US
from retuve.funcs import analyse_hip_2DUS_sweep
from retuve.keyphrases.enums import Colors, HipMode
from retuve_yolo_plugin.ultrasound import (
    get_yolo_model_us,
    yolo_predict_dcm_us,
)

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"

# Orthanc upload configuration constants
ORTHANC_HOST = "orthanc"
ORTHANC_PORT = 4242
ORTHANC_AE_TITLE = "NIDUS"
CALLING_AE_TITLE = "RETUVE"  # Your local AE titl
ENABLE_UPLOAD = True  # Set to False to disable uploading


if os.getenv("DEV") == "True":
    IMAGE_DIR = "."
else:
    IMAGE_DIR = "/home/chris"

parser = ArgumentParser(description=DISPLAY_TITLE)


def add_config_args_to_parser(
    parser: ArgumentParser, config: Any, prefix: str = ""
) -> None:
    """
    Add command line arguments from a config object's constructor parameters.

    Args:
        parser: The ArgumentParser to add arguments to
        config: The config object to extract arguments from
        prefix: Prefix for argument names (for nested configs)
    """
    # Get the constructor signature to understand the parameters
    init_signature = inspect.signature(config.__class__.__init__)

    # Iterate through the constructor parameters
    for param_name, param_obj in init_signature.parameters.items():
        # Skip 'self' parameter
        if param_name == "self":
            continue
        if "subconfig" in param_name:
            continue

        # Create argument name with prefix
        arg_name = f"--{prefix}{param_name}" if prefix else f"--{param_name}"

        # Get the default value
        default_value = (
            param_obj.default
            if param_obj.default != inspect.Parameter.empty
            else None
        )

        # Get the current value from the instance
        current_value = getattr(config, param_name, default_value)

        # Handle different types of values
        if isinstance(current_value, bool) or isinstance(
            current_value, type(None)
        ):
            parser.add_argument(
                arg_name,
                type=bool,
                default=bool(current_value),
                metavar="",
                help=f"Boolean flag for {param_name}",
            )
        elif isinstance(current_value, int):
            parser.add_argument(
                arg_name,
                type=int,
                default=current_value,
                metavar="",
                help=f"Integer value for {param_name}",
            )
        elif isinstance(current_value, float):
            parser.add_argument(
                arg_name,
                type=float,
                default=current_value,
                metavar="",
                help=f"Float value for {param_name}",
            )
        elif (
            isinstance(current_value, str)
            or isinstance(current_value, type(None))
            or isinstance(current_value, Colors)
        ):
            if isinstance(current_value, Colors):
                current_value = (
                    str(current_value)
                    .replace("Color(", "")
                    .replace(")", "")
                    .replace("(", "")
                    .replace(" ", "")
                )
            elif isinstance(current_value, list):
                current_value = (
                    str(current_value).replace("[", "").replace("]", "")
                )
            else:
                current_value = str(current_value)
            parser.add_argument(
                arg_name,
                type=str,
                default=current_value,
                metavar="",
                help=f"String value for {param_name}",
            )
        else:
            print(
                f"Unsupported type for argument {param_name}: {type(current_value)}"
            )


def apply_args_to_config(
    config: Any, args: Namespace, prefix: str = ""
) -> None:
    """
    Apply command line arguments back to the config object.

    Args:
        config: The config object to update
        args: The parsed arguments
        prefix: Prefix for argument names (for nested configs)
    """
    init_signature = inspect.signature(config.__class__.__init__)

    for param_name, param_obj in init_signature.parameters.items():
        if param_name == "self":
            continue

        # Create argument name with prefix
        arg_name = f"{prefix}{param_name}" if prefix else param_name

        # Check if this argument was provided
        if hasattr(args, arg_name):
            new_value = getattr(args, arg_name)
            current_value = getattr(config, param_name, None)

            # Handle type conversion
            if isinstance(current_value, bool):
                setattr(config, param_name, bool(new_value))
            elif isinstance(current_value, int):
                setattr(config, param_name, int(new_value))
            elif isinstance(current_value, float):
                setattr(config, param_name, float(new_value))
            elif isinstance(current_value, str):
                setattr(config, param_name, str(new_value))
            elif isinstance(current_value, type(None)):
                setattr(config, param_name, None)
            elif isinstance(current_value, Colors):
                as_int_list = [int(x) for x in new_value.split(",")]
                setattr(config, param_name, Colors(as_int_list))
            else:
                print(
                    f"Unsupported type for config and {param_name}: {type(current_value)}"
                )


def upload_dicom_to_orthanc(dicom_file_path: str, original_dicom=None) -> bool:
    """
    Upload a DICOM file to Orthanc server.

    Args:
        dicom_file_path: Path to the DICOM file to upload
        original_dicom: Original DICOM dataset to copy metadata from (optional)

    Returns:
        bool: True if upload successful, False otherwise
    """
    if not ENABLE_UPLOAD:
        print("Upload disabled by configuration")
        return False

    try:
        # Read the DICOM file
        dataset = pydicom.dcmread(dicom_file_path)

        # If we have an original DICOM, copy some metadata
        if original_dicom:
            # Copy study-level information from original
            if hasattr(original_dicom, "StudyDate"):
                dataset.StudyDate = original_dicom.StudyDate
            if hasattr(original_dicom, "StudyInstanceUID"):
                dataset.StudyInstanceUID = original_dicom.StudyInstanceUID
            if hasattr(original_dicom, "PatientID"):
                dataset.PatientID = original_dicom.PatientID
            if hasattr(original_dicom, "PatientName"):
                dataset.PatientName = original_dicom.PatientName
            if hasattr(original_dicom, "StationName"):
                dataset.StationName = original_dicom.StationName

        # Create Application Entity with calling AE title
        ae = AE(ae_title=CALLING_AE_TITLE)

        # Define the requested contexts for different DICOM types
        requested_contexts = [
            "1.2.840.10008.5.1.4.1.1.1",  # CR Image Storage
            "1.2.840.10008.5.1.4.1.1.4",  # MR Image Storage
            "1.2.840.10008.5.1.4.1.1.3.1",  # Ultrasound Multi-frame Image Storage
            "1.2.840.10008.5.1.4.1.1.1.1",  # Digital X-Ray Image Storage
            "1.2.840.10008.5.1.4.1.1.104.1",  # Encapsulated PDF Storage
        ]

        transfer_syntaxes = [
            "1.2.840.10008.1.2.4.91",
            "1.2.840.10008.1.2.5",
            "1.2.840.10008.1.2.1",
            "1.2.840.10008.1.2.4.50",
        ]

        # Add requested contexts
        for context in requested_contexts:
            for ts in transfer_syntaxes:
                ae.add_requested_context(context, transfer_syntax=ts)

        # Establish association with Orthanc
        assoc = ae.associate(
            addr=ORTHANC_HOST,
            port=ORTHANC_PORT,
            ae_title=ORTHANC_AE_TITLE,
        )

        if assoc and assoc.is_established:
            # Send the DICOM file via C-STORE
            status = assoc.send_c_store(dataset)

            if status:
                print(f"C-STORE request status: 0x{status.Status:04X}")
                if status.Status == 0x0000:
                    print(
                        f"DICOM file successfully uploaded via DICOM networking: {dicom_file_path}"
                    )
                    success = True
                else:
                    print(f"Error uploading DICOM file: {status}")
                    success = False
            else:
                print("Failed to send the DICOM file.")
                success = False

            # Release the association
            assoc.release()
        else:
            print("Failed to establish association with Orthanc.")
            success = False

        return success

    except Exception as e:
        print(f"Error uploading DICOM file {dicom_file_path}: {str(e)}")
        return False


# Add arguments for the main config
add_config_args_to_parser(parser, default_US)

# Add arguments for subconfigs explicitly
add_config_args_to_parser(parser, default_US.hip, "hip.")
add_config_args_to_parser(parser, default_US.trak, "trak.")
add_config_args_to_parser(parser, default_US.visuals, "visuals.")
add_config_args_to_parser(parser, default_US.api, "api.")
add_config_args_to_parser(parser, default_US.batch, "batch.")

parser.add_argument(
    "--github-secret",
    type=str,
    default=None,
    metavar="",
    help="Github secret for the Retuve API",
)
parser.add_argument(
    "--model-url",
    type=str,
    default=None,
    metavar="",
    help="URL for a custom Retuve model",
)


@chris_plugin(parser=parser, title=DISPLAY_TITLE)
def main(options: Namespace, inputdir, outputdir):

    # Apply command line arguments to the config
    apply_args_to_config(default_US, options)
    apply_args_to_config(default_US.hip, options, "hip.")
    apply_args_to_config(default_US.trak, options, "trak.")
    apply_args_to_config(default_US.visuals, options, "visuals.")
    apply_args_to_config(default_US.api, options, "api.")
    apply_args_to_config(default_US.batch, options, "batch.")

    # Override with input/output directories
    default_US.batch.datasets = [inputdir]
    default_US.api.savedir = outputdir

    # TODO: Add support for mode_func and hip_mode string mapping
    # For now, keep the hardcoded values
    default_US.batch.mode_func = yolo_predict_dcm_us
    default_US.batch.hip_mode = HipMode.US3D
    default_US.visuals.display_segs = False
    default_US.visuals.display_full_metric_names = True

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
            "A infant at 16 weeks can have an alpha angle on average 5 degrees higher than at 1-8 weeks (Hareendranathan et al., 2022 - Normal variation)"
        )

        r_gen.add_warning(
            "For this version, we recommend a Alpha Threshold of 50 and a Coverage Threshold of 50."
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
