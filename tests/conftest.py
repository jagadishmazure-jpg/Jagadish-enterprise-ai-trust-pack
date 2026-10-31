import copy
from datetime import datetime, timezone

import pytest

from trustpack.residency import load_config

AS_OF = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def as_of():
    return AS_OF


@pytest.fixture
def eu_cfg():
    return copy.deepcopy(load_config("fernhollow-bank-eu"))


@pytest.fixture
def us_cfg():
    return copy.deepcopy(load_config("marlowe-freight-us"))
