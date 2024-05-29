import dataclasses
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from buildable_dataclasses.buildable import Buildable
from misc_python_utils.beartypes import Dataclass
from misc_python_utils.dataclass_utils import UNDEFINED, Undefined
from misc_python_utils.slugification import NameSlug
from nested_dataclass_serialization.dataclass_serialization import (
    decode_dataclass,
    encode_dataclass,
)

from ml_system_dockerization.docker_service_content import (
    DockerServiceContent,
    set_or_update,
)
from ml_system_dockerization.dockerized_service_utils import VOLUME_MOUNTS
from ml_system_dockerization.knowledge_dependencies import (
    recursively_traverse_dag_to_find_knowledge,
)
from ml_system_dockerization.knowledge_volumes import (
    DcVolumeServiceWrapper,
    create_knowledge_volume_services,
)

logger = logging.getLogger(__name__)
dc_base_folder = "docker_compose_dir"  # TODO: why is that named like this?

SYSTEM_CONFIG_DIR_IN_CONTAINER = f"/{VOLUME_MOUNTS}{dc_base_folder}/system-config"


def add_config_dir_to_environment(
    content: DockerServiceContent,
    system_config_dir_in_container: str,
    service_name: str,
) -> DockerServiceContent:
    """
    we cannot mount a subdir of a volume to a service, see: https://stackoverflow.com/questions/38164939/can-we-mount-sub-directories-of-a-named-volume-in-docker
    so we mount the root-folder and give the full-path to the services config directory as an environment variable
    """
    the_services_config_dir = config_subdir_in_system_config_dir(
        system_config_dir=system_config_dir_in_container,
        service_name=service_name,
    )
    content.environment = set_or_update(
        content.environment,
        [f"CONFIG_DIR={the_services_config_dir}"],
    )

    return content


def config_subdir_in_system_config_dir(
    system_config_dir: str,
    service_name: str,
) -> str:
    return f"{system_config_dir}/{service_name}"


TIMESTAMP = datetime.now().strftime(  # noqa: DTZ005
    "%d-%h-%H-%M-%S-%f",
)  # could be git-hash or some version in future


ALMA_CLASS_KEY = "_alma_dataclass_"


@dataclass
class MlDockerService(Buildable):
    """
    cuerpo -> docker-image + code
    alma -> some (deeply) nested Dataclass holding the inferencers-logic
    mente -> knowledge that might get "extracted from the alma"
    """

    alma: dict[str, Any] | Dataclass | None = field(
        init=True,
        repr=True,
        default=None,  # TODO: why was this optional?
    )  # TODO: why was is repr=False? need it for hash calculation!
    service_name: NameSlug | Undefined = UNDEFINED
    service_content: DockerServiceContent = UNDEFINED
    dependencies: list[DcVolumeServiceWrapper] = field(init=False, default_factory=list)
    docker_registry_prefix: str | None = None
    misc_dockerfile_lines: list[
        str
    ] | None = None  # supposed to be used for prototyping/debugging

    def __post_init__(self):
        if (
            not isinstance(self.alma, dict) and self.alma is not None
        ):  # TODO: do this after the build?
            self.alma = encode_alma(self.alma)  # is this to prevent building it?

    def _build_self(self) -> Any:
        """
        gets resource dependencies get collected in this DEPENDENCIES global-var
        SYSTEM_CONFIG is a "special" dependency, it contains the entire systems config
        """
        alma = decode_alma(self.alma) if self.alma is not None else None
        if dataclasses.is_dataclass(alma):
            volume_services = create_knowledge_volume_services(
                self.docker_registry_prefix,
                built_deps=(
                    dep.build()
                    for dep in recursively_traverse_dag_to_find_knowledge([alma])
                ),
            )
            # assignment here because cache_dir get determined in _register_knowledge_dependencies_in_docker_volumes
            self.alma = encode_alma(alma)

            self.service_content.depends_on = list(
                {volservice.service_name for volservice in volume_services},
            )
            volumes = [
                self.volume_mount_register_in_env_var(volservice)
                for volservice in volume_services
            ]
            self.service_content.volumes = (
                volumes
                if self.service_content.volumes is None
                else self.service_content.volumes + volumes
            )
            add_config_dir_to_environment(
                self.service_content,
                SYSTEM_CONFIG_DIR_IN_CONTAINER,
                self.service_name,
            )
            self.dependencies = volume_services
        return self

    def volume_mount_register_in_env_var(
        self,
        volservice: DcVolumeServiceWrapper,
    ) -> str:
        mount = f"{volservice.volume_name}:{volservice.to_be_mounted_here}:ro"
        self.service_content.environment = set_or_update(
            self.service_content.environment,
            [f"{volservice.mount_prefix_key}=/{volservice.mount_prefix_key}"],
        )
        return mount


def encode_alma(d: Dataclass) -> dict[str, Any]:
    return encode_dataclass(d, class_reference_key=ALMA_CLASS_KEY)


def decode_alma(d: dict[str, Any]) -> Dataclass:
    return decode_dataclass(d, class_ref_key=ALMA_CLASS_KEY)
