"""A :obj:`~nipype.interfaces.utility.base.IdentityInterface` with a grafted Datalad getter."""

from pathlib import Path
from pydra.engine.specs import (
    File,
    Directory,
    SpecInfo,
    BaseSpec,
)
from pydra.engine.task import FunctionTask

import os
import logging

logger = logging.getLogger("pydra.tasks.datalad")

input_fields = [
    (
        "in_file",
        str,
        {
            "help_string": "Path to the data to be downloaded through datalad",
            "mandatory": True,
        },
    ),
    (
        "dataset_path",
        Directory,
        {
            "help_string": "Path to the dataset that will be used to get data",
            "mandatory": True,
        },
    ),
    (
        "dataset_url",
        str,
        {
            "help_string": "URL to the dataset that will be used to get data",
        },
    ),
]

Datalad_input_spec = SpecInfo(
    name="DataladInputSpec",
    fields=input_fields,
    bases=(BaseSpec,),
)

output_fields = [
    (
        "out_file",
        File,
        {
            "help_string": "file downloaded through datalad",
            "requires": ["in_file"],
            "output_file_template": "{in_file}",
        },
    )
]

Datalad_output_spec = SpecInfo(
    name="DataladOutputSpec",
    fields=output_fields,
    bases=(BaseSpec,),
)


class DataladInterface(FunctionTask):

    input_spec = Datalad_input_spec
    output_spec = Datalad_output_spec

    def _run_interface(self, runtime):
        import attr

        inputs = self.inputs.get()
        dataset_path = inputs.pop("dataset_path")

        _dl_found = False
        try:
            import datalad.api as dl

            _dl_found = True
        except:
            raise ImportError("Datalad is not installed.")

        if not (Path(dataset_path) / ".datalad").exists():
            logger.info("Datalad interface without dataset path defined.")
            try:
                dataset_url = inputs.pop("dataset_url")
                os.makedirs(dataset_path, exist_ok=True)
                dl.install(source=dataset_url, path=dataset_path)
            except Exception as e:
                logger.error(e)

        dataset_path = Path(dataset_path)
        # check the in_file is in the dataset
        for field, value in inputs.items():
            if value in [None, attr.NOTHING]:
                continue

            _pth = Path(value)
            if not _pth.is_absolute():
                _pth = dataset_path / _pth

            _datalad_candidate = _pth.is_symlink() and not _pth.exists()
            if not _datalad_candidate:
                logger.warning("datalad was required but not found")
                return runtime

            if _datalad_candidate:
                try:
                    result = dl.get(_pth, dataset=dataset_path)
                except Exception as exc:
                    logger.warning(f"datalad get on {_pth} failed.")
                    ## discussed with @djarecka, we keep it commented here for now
                    ## do we still need it for pydra?
                    # if (
                    #     config.environment.exec_env == "docker"
                    #     and ("This repository is not initialized for use by git-annex, "
                    #          "but .git/annex/objects/ exists") in f"{exc}"
                    # ):
                    #     logger.warning(
                    #         "Execution seems containerirzed with Docker, please make sure "
                    #         "you are not running as root. To do so, please add the argument "
                    #         "``-u $(id -u):$(id -g)`` to your command line."
                    #     )
                    # else:
                    #     logger.warning(str(exc))
            else:
                if result[0]["status"] == "error":
                    logger.warning(f"datalad get failed: {result}")

        return runtime
