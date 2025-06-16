from argparse import ArgumentParser

from chris_plugin import chris_plugin
from retuve.batch import run_batch
from retuve.defaults.hip_configs import default_US
from retuve.keyphrases.enums import HipMode
from retuve_yolo_plugin.ultrasound import (
    get_yolo_model_us,
    yolo_predict_dcm_us,
)

parser = ArgumentParser()


@chris_plugin(parser=parser)
def main(options, inputdir, outputdir):
    default_US.batch.datasets = [inputdir]
    default_US.api.savedir = outputdir

    default_US.batch.mode_func = yolo_predict_dcm_us
    default_US.batch.hip_mode = HipMode.US3D
    default_US.batch.mode_func_kwargs = {
        "model": get_yolo_model_us(default_US)
    }

    run_batch(default_US)
