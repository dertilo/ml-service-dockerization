import os

DOCKER_REGISTRY_PREFIX = "some-prefix-just-for-testing"

SOME_PREFIX_KEY = "some_prefix_key"


def in_ci() -> bool:
    try:
        os.getlogin()
        o = False
    except OSError:
        o = True
    return o
