[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![bear-ified](https://raw.githubusercontent.com/beartype/beartype-assets/main/badge/bear-ified.svg)](https://beartype.readthedocs.io)
[![Ruff-ified](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/dertilo/python-linters/blob/master/python_linters/ruff.toml)
# ml-service-dockerization
poormans python helper scripts to create docker(-compose) yaml-files and volumes etc.
* this module answers the question: `how to create a docker-compose.yml from python-code defined services?`
* multiple ml-services == `ml-system` -> multiple `service-containers`
* `service-containers` contain code+configuration but __NO__ data/blobs
* blobs get put in `docker-volume-images` -> poormans artifacts
* docker-compose ties everything together

#### what about `test-containers`?
