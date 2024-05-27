import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from buildable_dataclasses.buildable import Buildable
from buildable_dataclasses.buildable_data import BuildableData
from misc_python_utils.file_utils.readwrite_files import read_file, write_file
from misc_python_utils.prefix_suffix import PrefixSuffix
from misc_python_utils.slugification import SlugStr

logger = logging.getLogger(__name__)
SOME_PREFIX_KEY = "some_prefix_key"


@dataclass
class SomeResource(BuildableData):
    text: str = "bar"
    base_dir: PrefixSuffix = PrefixSuffix(  # noqa: RUF009
        SOME_PREFIX_KEY,
        "some_type_of_resource",
    )  # noqa: RUF009
    name: SlugStr = field(init=False, default="some_resource")

    @property
    def _is_data_valid(self) -> bool:
        return self.blob_file.is_file()

    @property
    def blob_file(self) -> Path:
        return Path(f"{self.data_dir}/blob.txt")

    def _build_data(self) -> Any:
        assert (
            not is_in_docker_container()
        )  # just to show-case that the resource is NOT built within the docker-container! but simply "loaded"
        os.makedirs(self.data_dir, exist_ok=True)  # noqa: PTH103
        assert self.text != "bar"
        write_file(self.blob_file, wannabe_blob_content(self.text))


def is_in_docker_container() -> bool:
    """
    https://stackoverflow.com/questions/43878953/how-does-one-detect-if-one-is-running-within-a-docker-container-within-python
    """
    path = "/proc/self/cgroup"
    return (
        os.path.exists("/.dockerenv")  # noqa: PTH110
        or os.path.isfile(path)  # noqa: PTH113
        and any("docker" in line for line in open(path))  # noqa: SIM115, PTH123
    )


SOME_CACHE_ENV_VAR = "SOME_CACHE"


@dataclass
class SomeService(Buildable):
    """
    TODO: maybe somewhen in future I might want to prepare some cache during a prepare-docker-stage
    """

    some_resource: SomeResource
    foo: str = "bar"

    # def _build_self(self) -> None:
    #     self._pretend_to_write_to_some_cache()
    #
    # @property
    # def _is_ready(self) -> bool:
    #     return Path(self.some_cache_file).is_file()

    # @property
    # def some_cache_file(self) -> str:
    #     return f"{os.environ[SOME_CACHE_ENV_VAR]}/some_cached_data.txt"
    #
    # def _pretend_to_write_to_some_cache(self):
    #     Path(os.environ[SOME_CACHE_ENV_VAR]).mkdir()
    #     write_file(self.some_cache_file, "some_cached_data")

    def predict(self, data: str) -> str:
        blob_content = read_file(str(self.some_resource.blob_file))
        # self._pretend_to_need_some_cached_file()
        return predict_output(blob_content, data)

    # def _pretend_to_need_some_cached_file(self):
    #     assert read_file(self.some_cache_file) == "some_cached_data"


def wannabe_blob_content(text: str) -> str:
    return f"I am a wannabe blob: {text}"


def predict_output(blob_content: str, data: str) -> str:
    return f"{blob_content}, your-input: {data}"
