import inspect
from argparse import ArgumentParser, Namespace
from typing import Any

from dotenv import load_dotenv
from retuve.defaults.hip_configs import default_US
from retuve.keyphrases.enums import Colors, HipMode

load_dotenv()

DISPLAY_TITLE = "Retuve ChRIS Plugin"

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


def apply_config(options, inputdir, outputdir):
    from retuve_yolo_plugin.ultrasound import yolo_predict_dcm_us

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
    default_US.worker_device = "cpu"

    return default_US


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
parser.add_argument(
    "--chris-api-url",
    type=str,
    default="https://chris-api.nidusai.ca/api/v1",
    metavar="",
    help="URL for a custom Cube",
)
parser.add_argument(
    "--token",
    type=str,
    default="",
    metavar="",
    help="Login Token for a custom Cube",
)
