import os

from misc_python_utils.file_utils.readwrite_files import read_file
from misc_python_utils.prefix_suffix import BASE_PATHES
from nested_dataclass_serialization.dataclass_serialization import deserialize_dataclass

ALMA_CLASS_KEY = "_alma_dataclass_"


def set_the_volums_prefixes_from_env() -> None:
    """
    this is a copy-paste from here: (just because I am too lazy to pip install this package within the docker-container)
    from ml_system_dockerization.dockerized_service_utils import \
    set_the_volums_prefixes_from_env, VOLUME_MOUNTS

    """
    VOLUME_MOUNTS = "VOLUME_MOUNTS_"  # arbitraty dir-name
    BIND_VOLUME = "BINDVOLUME_"

    env_prefixes = [VOLUME_MOUNTS, BIND_VOLUME]
    for envpref in env_prefixes:
        prefixkey_dirr = [
            (name.replace(envpref, ""), dirr)
            for name, dirr in os.environ.items()
            if name.startswith(envpref)
        ]
        for prefixkey, dirr in prefixkey_dirr:
            BASE_PATHES[prefixkey] = dirr


if __name__ == "__main__":
    set_the_volums_prefixes_from_env()
    file = f"{os.environ['CONFIG_DIR']}/alma.json"
    deserialize_dataclass(read_file(file), class_ref_key=ALMA_CLASS_KEY).build()
