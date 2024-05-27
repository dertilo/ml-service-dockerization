import logging
import os
from collections.abc import Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Annotated

import yaml
from beartype import beartype
from beartype.vale import Is
from buildable_dataclasses.hashcached_data.hashcached_data import HashCachedData
from misc_python_utils.beartypes import NeDict
from misc_python_utils.file_utils.readwrite_files import write_file, write_json
from misc_python_utils.prefix_suffix import BASE_PATHES, PrefixSuffix
from misc_python_utils.slugification import NameSlug, SlugStr

from ml_system_dockerization.docker_service_content import DockerServiceContent
from ml_system_dockerization.dockerized_service_utils import assign_or_append
from ml_system_dockerization.knowledge_volumes import (
    DEFAULT_VOLUME_OPTION,
    VOLUME_PROVIDER_IMAGE_PREFIX,
    DcVolumeServiceWrapper,
    create_docker_volume_service,
)
from ml_system_dockerization.ml_docker_service import (
    SYSTEM_CONFIG_DIR_IN_CONTAINER,
    MlDockerService,
    config_subdir_in_system_config_dir,
)

logger = logging.getLogger(__name__)


def create_docker_compose_yaml(  # noqa: PLR0913
    service2content: NeDict[str, DockerServiceContent],
    prod: bool,  # if True: build volumes
    volume_service2content: dict[str, DockerServiceContent] | None = None,
    toplevel_volume_declarations: dict[str, dict] | None = None,
    docker_compose_yaml_version: str = "3.3",  # cause thats what jina does
    networks: dict[str, dict] | None = None,
    exclude_volumes: bool = False,
) -> str:
    """
    # docker-compose.yaml
    version: "3.8" # docker_compose_yaml_version

    services:
      db:
        image: db
        volumes:
          - data-volume:/var/lib/db
      backup:
        image: backup-service
        volumes:
          - data-volume:/var/lib/backup/data

    volumes:  # toplevel_volume_declarations
      data-volume:

    """
    if volume_service2content is None:
        volume_service2content = {}
    d = {
        "version": docker_compose_yaml_version,
        "services": {
            name: service.prepare_for_dc_yaml(
                exclude_builds=prod,
                exclude_nonbind_volumes=exclude_volumes,
            )
            for name, service in (volume_service2content | service2content).items()
        },
        # "deploy": {
        #     "resources": {
        #         "limits": {
        #             # "cpus": "0.001",
        #             "memory": "50M"
        #         }
        #     }
        # },
    }
    if (
        toplevel_volume_declarations is not None
        and len(toplevel_volume_declarations) > 0
    ):
        d["volumes"] = toplevel_volume_declarations
    if networks:
        d["networks"] = networks
    return yaml.dump(
        d,
        default_flow_style=False,
        indent=2,
    )


AbsolutePath = Annotated[str, Is[lambda s: s.startswith("/")]]


@beartype
def add_system_config_dependency(
    content: DockerServiceContent,
    system_config_volume: DcVolumeServiceWrapper,
) -> None:
    assign_or_append(
        content,
        "depends_on",
        system_config_volume.service_name,
    )
    assign_or_append(
        content,
        "volumes",
        f"{system_config_volume.volume_name}:{SYSTEM_CONFIG_DIR_IN_CONTAINER}:ro",
    )


DCSYSTEMS_CACHE = "DC_SYSTEMS_CACHE"
DCSYSTEMS_CACHE_KEY = DCSYSTEMS_CACHE.lower().replace("_", "-")
DOCKER_COMPOSE_YAML_DEV = "docker-compose-dev.yml"


@dataclass(kw_only=True)
class DcSystemWithVolumes(HashCachedData, AbstractContextManager):
    """
    this is the ML-Ops part that creates+writes the docker-compose.yml
    it does:
    1. extract knowledge from almas
        a) puts them into volume-provider-services
        b) creates volumes
        c) create dependencies
    2. write docker-compose.yml files
    3. builds all image + in enter/exit does up/down (docker-compose)
    4. dumps all almas to its cache_dir!
    to ship everything to customer, this can be put into its own DockerVolumeImage!
    build + up in one step! looks like lazyness of developer but is actually a feature!
    cause it enforces that you cannot "simply" build the system without running it (docker-compose up)
    should be obvious that "running the system" in dev/ops context refers to testing/evaluating/benchmarking

    """

    name: SlugStr
    docker_services: Iterable[MlDockerService]
    docker_registry_prefix: str
    networks: dict | None = None
    cache_base: PrefixSuffix = field(
        default_factory=lambda: PrefixSuffix(
            BASE_PATHES[DCSYSTEMS_CACHE_KEY],
            DCSYSTEMS_CACHE,
        ),
    )
    docker_compose_yaml_version: str = "3.3"  # cause thats what jina does
    built_image_tag: str = field(init=False)
    manually_declared_volumes: list[str] = field(default_factory=list)
    env_file: str | None = None

    @property
    def docker_compose_context_dir(self) -> Path:
        return Path(str(self.cache_dir))

    def _build_cache(self) -> None:
        self._write_docker_compose_yamls()
        self._write_almas()

    def _write_docker_compose_yamls(self) -> None:
        timestamp = datetime.now().strftime("%d-%h-%H-%M-%S-%f")  # noqa: DTZ005
        self.built_image_tag = timestamp
        system_config_volume = create_docker_volume_service(
            self.cache_dir,
            regristry_prefix=self.docker_registry_prefix,
            tag=timestamp,
        )

        for ds in self.docker_services:
            if ds.alma is not None:
                add_system_config_dependency(ds.service_content, system_config_volume)

        service2content: dict[str, DockerServiceContent] = {
            ds.service_name: ds.service_content for ds in self.docker_services
        }

        volume_service2content: dict[str, DockerServiceContent] = {
            dep.service_name: dep.content
            for ds in self.docker_services
            for dep in ds.dependencies
        } | {system_config_volume.service_name: system_config_volume.content}

        toplevel_volume_declarations = (
            {
                dep.volume_name: dep.volume_options
                for ds in self.docker_services
                for dep in ds.dependencies
            }
            | {
                system_config_volume.volume_name: dict(
                    system_config_volume.volume_options,
                ),
            }
            | {mv: dict(DEFAULT_VOLUME_OPTION) for mv in self.manually_declared_volumes}
        )
        for service in (volume_service2content | service2content).values():
            if service.build_subsection is not None:
                service.tag_image(
                    tag=timestamp,
                )

        write_file(
            f"{self.docker_compose_context_dir}/docker-compose.yml",
            create_docker_compose_yaml(
                volume_service2content=volume_service2content,
                service2content=service2content,
                toplevel_volume_declarations=toplevel_volume_declarations,
                networks=self.networks,
                docker_compose_yaml_version=self.docker_compose_yaml_version,
                prod=True,
            ),
        )
        write_file(
            f"{self.docker_compose_context_dir}/{DOCKER_COMPOSE_YAML_DEV}",
            create_docker_compose_yaml(
                volume_service2content=volume_service2content,
                service2content=service2content,
                toplevel_volume_declarations=toplevel_volume_declarations,
                networks=self.networks,
                docker_compose_yaml_version=self.docker_compose_yaml_version,
                prod=False,
            ),
        )

    def _write_almas(self) -> None:
        """
        dataclass.json == config == alma
        """
        services_with_alma = [ds for ds in self.docker_services if ds.alma is not None]
        for ds in services_with_alma:
            write_alma_to_subdir(str(self.cache_dir), ds.service_name, ds.alma)

    def __enter__(self):
        docker_compose_up_build(
            self.name,
            docker_compose_context_dir=Path(self.docker_compose_context_dir),
            env_file=self.env_file,
        )
        # TODO: wait for some healthcheck here! to ensure that system is "up"
        return self

    def __exit__(self, exc_type, exc_value, trace):  # noqa: ANN001
        """
        TODO: can I write its evaluation scores/metrics into the volume-image?
        """
        logger.info(
            f"exiting: {self.name}:{self.__class__.__name__}:  via docker-compose down in: {self.docker_compose_context_dir}",
        )
        docker_compose_down(
            self.docker_compose_context_dir,
            DOCKER_COMPOSE_YAML_DEV,
            self.name,
        )


def docker_compose_down(
    context_dir: Path,
    docker_compose_yaml_name: str,
    project_name: str,
) -> None:
    if (
        o := os.system(
            f"cd {context_dir} && docker-compose -f {docker_compose_yaml_name} --project-name {project_name} down",  # noqa: S605
            # noqa: S605
        )
        != 0
    ):
        logger.error(o)

    format_ = "{{.Repository}}:{{.Tag}}"
    cmd = f'docker rmi $(docker images --format "{format_}" | grep {VOLUME_PROVIDER_IMAGE_PREFIX})'
    logger.info(cmd)
    os.system(cmd)  # noqa: S605
    #  --rmi local
    # stdout = subprocess.check_output(
    #     f"cd {self.docker_compose_context_dir} && docker-compose down",
    #     shell=True,
    #     stderr=subprocess.STDOUT,
    # )
    # print(f"{stdout=}")


def docker_compose_up_build(
    project_name: NameSlug,
    docker_compose_context_dir: Path,
    env_file: str | None = None,
) -> None:
    """
    TODO: separate build & up
    """
    maybe_input_dir = (
        f" export INPUT_DATA_DIR={BASE_PATHES['data_dir']} && "
        if "data_dir" in BASE_PATHES
        else ""
    )
    maybe_env_file = f" --env-file {env_file}" if env_file is not None else ""
    cmd = (
        f"{maybe_input_dir}"
        f" cd {docker_compose_context_dir}"
        f" && export DOCKER_BUILDKIT=1"
        f" && docker compose --file {DOCKER_COMPOSE_YAML_DEV} --project-name {project_name}{maybe_env_file}"
        f" up"
        f" --build --remove-orphans -d"
    )
    logger.info(f"{cmd=}")
    # up_cmd = (
    #     f"docker-compose --compatibility --file docker-compose.yml --project-name {self.name}"
    #     f" up"
    # )
    # write_file(f"{self.docker_compose_context_dir}/run.sh", f"\n{up_cmd}\n")
    # TODO: 2>&1 > {self.logs_dir}/docker-compose.logs
    # stdout = subprocess.check_output(
    #     cmd,
    #     shell=True,
    #     stderr=subprocess.STDOUT,
    # )
    # print(f"{cmd=}")
    # print(f"{stdout=}")
    os.system(cmd)  # noqa: S605


def write_alma_to_subdir(
    config_dir: str,
    service_name: NameSlug,
    alma: dict,
) -> None:  # noqa: ANN201
    config_dir = config_subdir_in_system_config_dir(
        system_config_dir=config_dir,
        service_name=service_name,
    )
    os.makedirs(config_dir, exist_ok=True)  # noqa: PTH103
    write_json(
        f"{config_dir}/alma.json",
        alma,
    )
