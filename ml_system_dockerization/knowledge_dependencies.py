import logging
from collections.abc import Iterable, Iterator
from dataclasses import fields, is_dataclass
from typing import Any

from buildable_dataclasses.buildable_data import BuildableData
from buildable_dataclasses.hashcached_data.hashcached_data import HashCachedData
from misc_python_utils.beartypes import Dataclass

logger = logging.getLogger(__name__)


def find_knowledge_by_visiting_the_dag(
    dag: list[Dataclass] | tuple[Dataclass] | dict[str, Dataclass] | Dataclass,
) -> list[BuildableData | HashCachedData]:
    identitiers = set()
    knowledge = []
    for obj in recursively_traverse_dag_to_find_knowledge(dag):
        if isinstance(obj, HashCachedData):
            if obj.dataclass_json not in identitiers:
                knowledge.append(obj)
                identitiers.add(obj.dataclass_json)
        else:  # noqa: PLR5501
            if obj.name not in identitiers:
                knowledge.append(obj)
                identitiers.add(obj.name)

    return knowledge


def recursively_traverse_dag_to_find_knowledge(
    dc: list[Dataclass] | tuple[Dataclass] | dict[str, Dataclass] | Dataclass,
) -> Iterator[BuildableData | HashCachedData]:  # noqa: UP007
    """
    TODO: with "new" sparse/flat dag there should be not need to recursively search
        # also this might alleviate the redundancy problem! currently same dep can be emmitted multiple times!
    collects knowledge (BuildableData or CachedData)
    """

    for obj in shallow_unpack_containers(dc):
        does_contain_knowledge = isinstance(obj, BuildableData | HashCachedData)
        if does_contain_knowledge:
            yield obj
        else:
            yield from recursively_traverse_dag_to_find_knowledge(obj)


def shallow_unpack_containers(obj: Any) -> Iterable[Dataclass]:
    """
    NOT going deep into nested containers!
    """
    if is_dataclass(obj):
        g = [
            getattr(obj, f.name) for f in fields(obj) if f.init and hasattr(obj, f.name)
        ]
    elif isinstance(obj, (list, tuple)):  # noqa: UP038
        g = (x for x in obj)
    elif isinstance(obj, dict):
        g = (v for v in obj.values())
    else:
        g = []

    return [
        d for d in g if is_dataclass(d) or isinstance(d, dict) and has_dataclasses(d)
    ]


def has_dataclasses(d: dict) -> bool:
    return any(is_dataclass(v) for v in d.values())


# removed: GenericPredictorBuildProdJanus -> I maybe wanting this somewhen in future?
