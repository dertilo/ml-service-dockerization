import os
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI
from misc_python_utils.colored_logs_formatter import prepare_logger
from misc_python_utils.file_utils.readwrite_files import read_json

from ml_system_dockerization.dockerized_service_utils import (
    set_the_volums_prefixes_from_env,
)
from ml_system_dockerization.ml_docker_service import decode_alma

prepare_logger(namespaces=["app"])

inferencer = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201, ARG001
    set_the_volums_prefixes_from_env()
    file = f"{os.environ['CONFIG_DIR']}/alma.json"
    global inferencer  # noqa: PLW0603
    inferencer = decode_alma(read_json(file)).build()
    yield


app = FastAPI(debug=True, lifespan=lifespan)


@app.get("/health")
async def health():  # noqa: ANN201
    global inferencer  # noqa: PLW0602
    return {"is_fine": inferencer is not None}


@app.post("/predict")
def predict(
    job: dict = Body(...),  # noqa: B008
) -> dict:
    global inferencer  # noqa: PLW0602
    # with lock:
    out = inferencer.predict(job["input"])
    return {"output": out}
