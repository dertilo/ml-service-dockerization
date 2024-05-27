import logging
from collections.abc import Iterable
from dataclasses import dataclass

from buildable_dataclasses.buildable import Buildable
from buildable_dataclasses.buildable_data import BuildableData
from buildable_dataclasses.hashcached_data.hashcached_data import HashCachedData
from misc_python_utils.file_utils.readwrite_files import write_file
from misc_python_utils.prefix_suffix import PrefixSuffix

from ml_system_dockerization.docker_service_content import (
    DCBuildSubsection,
    DockerServiceContent,
)
from ml_system_dockerization.dockerized_service_utils import VOLUME_MOUNTS

logger = logging.getLogger(__name__)
DEFAULT_VOLUME_OPTION = {"external": False}  # only needed for yaml creation


@dataclass
class DcVolumeServiceWrapper:
    """
    Docker Compose Volume Service
    """

    service_name: str
    mount_prefix_key: str
    mount_suffix: str
    volume_name: str
    volume_options: dict
    dir_in_data_image: str
    content: DockerServiceContent

    @property
    def to_be_mounted_here(self) -> str:
        return f"/{self.mount_prefix_key}/{self.mount_suffix}"


def create_knowledge_volume_services(
    docker_registry_prefix: str,
    built_deps: Iterable[HashCachedData | BuildableData],  # noqa: UP007
) -> list[DcVolumeServiceWrapper]:
    """
    knowledge typically in form of a blob
    """
    dc_volume_services: list[DcVolumeServiceWrapper] = []

    tag = "latest"
    data_dirs = set()
    for dep in built_deps:
        assert dep._is_ready  # noqa: SLF001
        data_dir = get_knowledge_prefixsuffix(dep)
        if str(data_dir) not in data_dirs:
            data_dirs.add(str(data_dir))
            # register_knowledge_in_docker_volume(data_dir, docker_registry_prefix)
            volume = create_docker_volume_service(
                data_dir,
                regristry_prefix=docker_registry_prefix,
                tag=tag,
            )
            dc_volume_services.append(volume)

    return dc_volume_services


def get_knowledge_prefixsuffix(
    obj: Buildable,
) -> PrefixSuffix | None:
    if isinstance(obj, BuildableData):
        p = obj.data_dir_prefix_suffix
    elif isinstance(obj, HashCachedData):
        p = obj.cache_dir
    else:
        p = None
    return p


VOLUME_PROVIDER_IMAGE_PREFIX = "volume-provider_"


def create_docker_volume_service(
    data_dir: PrefixSuffix,
    regristry_prefix: str,
    tag: str = "latest",
) -> DcVolumeServiceWrapper:
    name_slug = data_dir.prefix_key + "-" + data_dir.suffix.replace("/", "-").lower()
    some_prefix = "volume-data"  # to make docker cp more convenient!
    dir_in_data_image = f"/{some_prefix}_{name_slug}"  # looks nicer in logs!
    dockerfile_content = f"""FROM alpine:latest
    RUN mkdir -p {dir_in_data_image}
    COPY . {dir_in_data_image}
    VOLUME ["{dir_in_data_image}"]
    """
    write_file(f"{data_dir}/Dockerfile_data", dockerfile_content)

    service_name = f"{VOLUME_PROVIDER_IMAGE_PREFIX}{name_slug}"
    volume_name = f"{name_slug}-volume"
    logger.warning(
        f"data-volume for: {name_slug},{data_dir=}",
    )
    return DcVolumeServiceWrapper(
        service_name=service_name,
        mount_prefix_key=f"{VOLUME_MOUNTS}{data_dir.prefix_key}",
        mount_suffix=data_dir.suffix,
        volume_name=volume_name,
        volume_options=DEFAULT_VOLUME_OPTION,
        dir_in_data_image=dir_in_data_image,
        content=DockerServiceContent(
            image=f"{regristry_prefix}/{service_name}:{tag}",
            build_subsection=DCBuildSubsection(
                context=f"{data_dir}",
                dockerfile="Dockerfile_data",
            ),
            volumes=[(f"{volume_name}:{dir_in_data_image}")],
        ),
    )
