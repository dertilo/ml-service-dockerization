import os
from pathlib import Path

import pytest
import requests
from misc_python_utils.prefix_suffix import BASE_PATHES, PrefixSuffix

from ml_system_dockerization.dc_system_with_volumes import DCSYSTEMS_CACHE
from ml_system_dockerization.docker_service_content import (
    GITLAB_CREDENTIALS,
    DCBuildSubsection,
    DockerServiceContent,
)
from ml_system_dockerization.dockerized_service_utils import wait_for_startup
from ml_system_dockerization.ml_docker_service import MlDockerService
from ml_system_dockerization.ml_service_standalone_docker import (
    MlServiceStandaloneDocker,
)
from tests.conftest import DOCKER_REGISTRY_PREFIX, SOME_PREFIX_KEY, in_ci
from tests.fastapi_service_for_testing.some_service import (
    SOME_CACHE_ENV_VAR,
    SomeResource,
    SomeService,
    predict_output,
    wannabe_blob_content,
)


@pytest.mark.skipif(
    in_ci(),
    reason="don't run this test in ci -> this would need docker-in-docker",
)
def test_service_with_data(tmp_path: Path):  # noqa: ANN201
    # BASE_PATHES[SOME_PREFIX_KEY] = f"{Path.cwd()}/dc_resources_dir" # for debugging only
    # Path(BASE_PATHES[SOME_PREFIX_KEY]).mkdir(exist_ok=True)
    BASE_PATHES[SOME_PREFIX_KEY] = str(tmp_path)

    os.environ[SOME_CACHE_ENV_VAR] = f"{BASE_PATHES[SOME_PREFIX_KEY]}/cache"
    Path(os.environ[SOME_CACHE_ENV_VAR]).mkdir(exist_ok=True)

    port = 8989
    whoohoo = "whoohoo"
    ds = MlDockerService(
        service_name="service-a",
        docker_registry_prefix=DOCKER_REGISTRY_PREFIX,
        service_content=DockerServiceContent(
            image=DOCKER_REGISTRY_PREFIX,
            build_subsection=DCBuildSubsection(
                context=f"{os.getcwd()}/tests/fastapi_service_for_testing",  # noqa: PTH109
                args=GITLAB_CREDENTIALS,
                # + ([f"CACHEBUST={self.cache_bust}"] if self.cache_bust else []),
            ),
            volumes=[
                f"{os.getcwd()}/tests:/code/tests",  # those mounts are just for testing! cause I am too lazy to pip install this package within the container!  # noqa: PTH109
                f"{os.getcwd()}/ml_system_dockerization:/code/ml_system_dockerization",  # noqa: PTH109
            ],
            command=f"uvicorn app.main:app --host 0.0.0.0 --port {port}".split(" "),
            ports=[f"{port}:{port}"],
            environment=[f"{SOME_CACHE_ENV_VAR}=/cache"],
        ),
        alma=SomeService(some_resource=SomeResource(text=whoohoo)),
    )
    dc = MlServiceStandaloneDocker(
        docker_service=ds,
        cache_base=PrefixSuffix(
            SOME_PREFIX_KEY,
            DCSYSTEMS_CACHE,
        ),
        docker_registry_prefix=DOCKER_REGISTRY_PREFIX,
    )
    dc.build()
    # os.system(f"tree {tmp_path}")
    INPUT = "hello"
    expected = predict_output(wannabe_blob_content(whoohoo), INPUT)
    with dc:
        # input("wait")
        wait_for_startup(port)
        resp = requests.post(
            f"http://localhost:{port}/predict",
            json={"input": INPUT},
            timeout=3.0,
        )
        assert resp.status_code == 200  # noqa: PLR2004
        assert resp.json()["output"] == expected
        # input("wait")


# volumes = [f"{os.getcwd()}/fastapi_gateway/app:/code/app"]
