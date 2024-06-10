import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from buildable_dataclasses.hashcached_data.hashcached_data import HashCachedData
from misc_python_utils.dataclass_utils import UNDEFINED
from misc_python_utils.file_utils.readwrite_files import read_file, write_file
from misc_python_utils.prefix_suffix import BASE_PATHES, PrefixSuffix
from misc_python_utils.slugification import CasedNameSlug

from ml_system_dockerization.dc_system_with_volumes import (
    DCSYSTEMS_CACHE,
    DCSYSTEMS_CACHE_KEY,
    DOCKER_COMPOSE_YAML_DEV,
    add_system_config_dependency,
    create_docker_compose_yaml,
    docker_compose_down,
    docker_compose_up_build,
    write_alma_to_subdir,
)
from ml_system_dockerization.docker_service_content import (
    DCBuildSubsection,
    DockerServiceContent,
)
from ml_system_dockerization.dockerized_service_utils import (
    EnterExitService,
    wait_for_startup,
)
from ml_system_dockerization.knowledge_volumes import (
    DcVolumeServiceWrapper,
    create_docker_volume_service,
)
from ml_system_dockerization.ml_docker_service import (
    SYSTEM_CONFIG_DIR_IN_CONTAINER,
    MlDockerService,
)

logger = logging.getLogger(__name__)
DOCKERFILE_WITH_DATA = "Dockerfile_with_data"
DOCKER_COMPOSE_DEV = "docker-compose-dev.yml"
REPLACE_BY_COPY_STATEMENTS = "# <replace-me-by-COPY-from-statements>"
REPLACE_BY_CMD_STATEMENT = "# <replace-me-by-CMD-statement>"


@dataclass(kw_only=True)
class MlServiceStandaloneDocker(
    HashCachedData,
    EnterExitService,
):
    """
    uses docker-compose to build an image that contains service+data
    volumes only used at "built-time" to collect data
    """

    docker_service: MlDockerService
    health_endpoint: str | None = None
    cache_base: PrefixSuffix = field(
        default_factory=lambda: PrefixSuffix(
            BASE_PATHES[DCSYSTEMS_CACHE_KEY],
            DCSYSTEMS_CACHE,
        ),
    )
    docker_registry_prefix: str | None = None
    name: CasedNameSlug = field(init=False)

    def __post_init__(self):
        self.name = f"{self.docker_service.service_name}-standalone"

    @property
    def docker_compose_context_dir(self) -> Path:
        return Path(str(self.cache_dir))

    def _build_cache(self):  # noqa: ANN202
        self._write_docker_compose_yamls()
        if self.do_build_docker_image:
            self._write_almas()

    @property
    def do_build_docker_image(self) -> bool:
        build_it = self.docker_service.service_content.build_subsection is not None
        if build_it:
            assert self.docker_registry_prefix is not None
            assert self.docker_service.alma is not None
        return build_it

    def _write_docker_compose_yamls(self) -> None:
        timestamp = datetime.now().strftime("%d-%h-%H-%M-%S-%f")  # noqa: DTZ005
        self.built_image_tag = timestamp
        service2content: dict[str, DockerServiceContent] = {
            self.docker_service.service_name: self.docker_service.service_content,
        }

        if self.do_build_docker_image:
            volume_service2content = self._create_dockerfile_prepare_volumes(timestamp)
        else:
            volume_service2content = None

        write_file(
            f"{self.docker_compose_context_dir}/{DOCKER_COMPOSE_DEV}",
            create_docker_compose_yaml(
                service2content=service2content,
                volume_service2content=volume_service2content,
                prod=False,
                exclude_volumes=True,
            ),
        )
        for sc in service2content.values():
            sc.depends_on = UNDEFINED

        write_file(
            f"{self.docker_compose_context_dir}/docker-compose.yml",
            create_docker_compose_yaml(
                service2content=service2content,
                prod=True,
                exclude_volumes=True,
            ),
        )

    def _create_dockerfile_prepare_volumes(
        self,
        timestamp: str,
    ) -> dict[str, DockerServiceContent]:
        system_config_volume = create_docker_volume_service(
            self.cache_dir,
            regristry_prefix=self.docker_registry_prefix,
            tag=timestamp,
        )
        self.system_config_volume = system_config_volume
        for ds in [self.docker_service]:
            if ds.alma is not None:
                add_system_config_dependency(
                    ds.service_content,
                    system_config_volume,
                )
        volume_service2content = {
            dep.service_name: dep.content for dep in self.docker_service.dependencies
        }
        volume_service2content |= {
            system_config_volume.service_name: system_config_volume.content,
        }
        for service in [
            *list(volume_service2content.values()),
            self.docker_service.service_content,
        ]:
            if service.build_subsection is not None:
                service.tag_image(
                    tag=timestamp,
                )
        _create_dockerfile(self.docker_service, self.system_config_volume)
        self.docker_service.service_content.command = (
            UNDEFINED  # to force it to use the CMD from the Dockerfile_template
        )
        return volume_service2content

    def _write_almas(self) -> None:
        write_alma_to_subdir(
            str(self.cache_dir),
            self.docker_service.service_name,
            self.docker_service.alma,
        )

    def _enter_service(self) -> None:
        docker_compose_up_build(
            self.name,
            docker_compose_context_dir=Path(self.docker_compose_context_dir),
            env_file=None,
        )
        # input("wait")
        if self.health_endpoint is not None:
            wait_for_startup(url=self.health_endpoint, max_waits=60)

    def _exit_service(self) -> None:
        logger.info(
            f"exiting: {self.name}:{self.__class__.__name__}:  via docker-compose down in: {self.docker_compose_context_dir}",
        )
        docker_compose_down(
            self.docker_compose_context_dir,
            DOCKER_COMPOSE_YAML_DEV,
            self.name,
        )


def _create_dockerfile(
    docker_service: MlDockerService,
    system_config_volume: DcVolumeServiceWrapper,
) -> None:
    dbuild: DCBuildSubsection = docker_service.service_content.build_subsection
    dockerfile = f"{dbuild.context}/{dbuild.dockerfile}"
    dockerfile_data = f"{dbuild.context}/{DOCKERFILE_WITH_DATA}"
    dockerfile_content = read_file(dockerfile)
    assert (
        REPLACE_BY_COPY_STATEMENTS in dockerfile_content
    ), f"{dockerfile} does not contain {REPLACE_BY_COPY_STATEMENTS}"
    dbuild.dockerfile = DOCKERFILE_WITH_DATA
    env_vars = [f"ENV {e}" for e in docker_service.service_content.environment]
    misc_lines = (
        docker_service.misc_dockerfile_lines
        if docker_service.misc_dockerfile_lines is not None
        else []
    )
    dockerfile_content = dockerfile_content.replace(
        REPLACE_BY_COPY_STATEMENTS,
        "\n".join(
            env_vars
            + misc_lines
            + [
                f"COPY --from={vi.content.image} {vi.dir_in_data_image} {vi.to_be_mounted_here}"
                for vi in docker_service.dependencies
            ]
            + [
                f"COPY --from={system_config_volume.content.image} {system_config_volume.dir_in_data_image} {SYSTEM_CONFIG_DIR_IN_CONTAINER}",
            ],
        ),
    )
    envs = "\n".join(env_vars)
    dockerfile_content = dockerfile_content.replace(
        REPLACE_BY_CMD_STATEMENT,
        f"{envs}\nCMD {docker_service.service_content.command}".replace("'", '"'),
    )
    write_file(
        dockerfile_data,
        dockerfile_content,
    )
