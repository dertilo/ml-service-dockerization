import os
from pathlib import Path
from time import sleep

import pytest
import requests
from buildable_dataclasses.buildable_container import BuildableContainer
from misc_python_utils.prefix_suffix import BASE_PATHES, PrefixSuffix

from ml_system_dockerization.dc_system_with_volumes import (
    DCSYSTEMS_CACHE,
    DcSystemWithVolumes,
)
from ml_system_dockerization.docker_service_content import DockerServiceContent
from ml_system_dockerization.dockerized_service_utils import VOLUME_MOUNTS
from ml_system_dockerization.ml_docker_service import MlDockerService
from tests.conftest import DOCKER_REGISTRY_PREFIX, SOME_PREFIX_KEY, in_ci
from tests.fastapi_service_for_testing.some_service import (
    SomeResource,
    SomeService,
    wannabe_blob_content,
)


@pytest.mark.skipif(
    in_ci(),
    reason="don't run this test in ci -> this would need docker-in-docker",
)
def test_dc_system_with_datavolume(tmp_path: Path):  # noqa: ANN201
    # BASE_PATHES[SOME_PREFIX_KEY] = f"{Path.cwd()}/dc_resources_dir"
    # Path(BASE_PATHES[SOME_PREFIX_KEY]).mkdir(exist_ok=True)
    BASE_PATHES[SOME_PREFIX_KEY] = str(tmp_path)

    port = 8000
    whoohoo = "whoohoo"
    ds = MlDockerService(
        service_name="service-a",
        docker_registry_prefix=DOCKER_REGISTRY_PREFIX,
        service_content=DockerServiceContent(
            image="python:3.10-slim",
            command=f"python -m http.server {port}".split(" "),
            ports=[f"{port}:{port}"],
        ),
        alma=SomeService(some_resource=SomeResource(text=whoohoo)),
    )
    dc = DcSystemWithVolumes(
        name="dummy-name",
        docker_services=BuildableContainer(data=[ds]),
        cache_base=PrefixSuffix(
            SOME_PREFIX_KEY,
            DCSYSTEMS_CACHE,
        ),
        docker_registry_prefix=DOCKER_REGISTRY_PREFIX,
    )
    dc.build()
    os.system(f"tree {tmp_path}")  # noqa: S605
    expected = wannabe_blob_content(whoohoo)
    with dc:
        sleep(1.0)
        url = f"http://localhost:{port}/{VOLUME_MOUNTS}{SOME_PREFIX_KEY}/some_type_of_resource/some_resource/blob.txt"
        resp = requests.get(
            url,
            timeout=3.0,
        )
        # input("wait")
        assert resp.text == expected, f"{url=}"


# volumes = [f"{os.getcwd()}/fastapi_gateway/app:/code/app"]
