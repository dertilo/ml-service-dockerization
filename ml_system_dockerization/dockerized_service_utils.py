import logging
import os
import types
from time import sleep
from typing import Any, final

from misc_python_utils.prefix_suffix import BASE_PATHES
from typing_extensions import Self

logger = logging.getLogger(__name__)
VOLUME_MOUNTS = "VOLUME_MOUNTS_"  # arbitraty dir-name
BIND_VOLUME = "BINDVOLUME_"


class EnterExitService:
    @final
    def __enter__(self) -> Self:
        self._enter_service()
        return self

    @final
    def __exit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_val: BaseException | None = None,
        exc_tb: types.TracebackType | None = None,
    ):
        self._exit_service()

    def _enter_service(self) -> None:
        """
        load model/data into memory or establish some connection
        """

    def _exit_service(self) -> None:
        """
        tear-down
        """


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


def set_the_volums_prefixes_from_env() -> None:
    env_prefixes = [VOLUME_MOUNTS, BIND_VOLUME]
    for envpref in env_prefixes:
        prefixkey_dirr = [
            (name.replace(envpref, ""), dirr)
            for name, dirr in os.environ.items()
            if name.startswith(envpref)
        ]
        for prefixkey, dirr in prefixkey_dirr:
            logger.debug(f"{prefixkey=} points to {dirr=}")
            BASE_PATHES[prefixkey] = dirr


# def set_pathes_for_jina_executor():
#     base_path = os.environ[BASE_DIR_KEY]
#     set_bind_volume_dirs()
#     BASE_PATHES[EMPTY_PREFIX] = ""
#     BASE_PATHES["base_path"] = base_path
#     if is_in_docker_container():
#         BASE_PATHES["cache_root"] = base_path
#     else:
#         BASE_PATHES["cache_root"] = f"{base_path}/data/cache"
#     hf_home = f"{base_path}/huggingface_cache"  # makes assumption that "all" services might use huggingface/transformers
#     os.environ["HF_HOME"] = hf_home
#     os.environ["TRANSFORMERS_CACHE"] = f"{hf_home}/transformers"


HasAttr = Any


def assign_or_append(
    obj: HasAttr,
    attr_name: str,
    value: Any,
) -> None:
    assert hasattr(obj, attr_name)
    if getattr(obj, attr_name) is not None:
        getattr(obj, attr_name).append(value)
    else:
        setattr(obj, attr_name, [value])


ONE_SECOND = 1.0


def wait_for_startup(
    port: int | None = None,
    host: str = "localhost",
    url: str | None = None,
    max_waits: int = 6,
) -> None:
    import requests

    for k in range(max_waits):
        try:  # noqa: WPS229
            resp = requests.get(  # noqa: S113
                f"http://{host}:{port}/health" if url is None else url,
            )
            assert resp.status_code == 200  # noqa: PLR2004
            assert resp.json()["is_fine"]
            return  # noqa: TRY300
        except (requests.exceptions.ConnectionError, AssertionError):
            logger.info(f"waiting for {k*ONE_SECOND} seconds")
            sleep(ONE_SECOND)
    raise RuntimeError(  # noqa: TRY003
        f"waited for {max_waits} seconds, startup didn't work!",  # noqa: EM102
    )  # noqa: EM102, TRY003
