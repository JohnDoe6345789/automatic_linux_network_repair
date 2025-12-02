"""Packaged systemd schema resources for demonstration and testing.

The bundled schema captures both active settings and commented defaults so it
can be round-tripped into a cat-config-style dump for demos or tests.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_sample_schema() -> dict[str, dict[str, Any]]:
    """Return the packaged sample systemd schema as a dictionary."""

    schema_resource = resources.files(__name__).joinpath("systemd_schema_sample.json")
    with resources.as_file(schema_resource) as schema_path:
        with schema_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
