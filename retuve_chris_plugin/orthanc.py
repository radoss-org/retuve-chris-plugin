import pydicom
from dotenv import load_dotenv
from pynetdicom import AE

load_dotenv()

# Orthanc upload configuration constants
ORTHANC_HOST = "orthanc"
ORTHANC_PORT = 4242
ORTHANC_AE_TITLE = "NIDUS"
CALLING_AE_TITLE = "RETUVE"  # Your local AE title
ENABLE_UPLOAD = True  # Set to False to disable uploading


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
