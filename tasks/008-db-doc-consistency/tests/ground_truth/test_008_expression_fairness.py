from __future__ import annotations

import importlib.util
from pathlib import Path


OUTCOME_PATH = Path(__file__).resolve().parents[1] / "test_outcome.py"


def _outcome_module():
    spec = importlib.util.spec_from_file_location("task008_outcome", OUTCOME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_markdown_ready_decision_is_detected() -> None:
    module = _outcome_module()
    review = """
**Decision:** **READY**
This decision is for documentation only and does not authorize execution.
Before use, check the production ConfigMap and inventory freshness.
"""

    passed, failures = module._review_result(review, guide_ready=True)

    assert passed, failures


def test_named_region_distribution_is_a_multi_region_statement() -> None:
    module = _outcome_module()
    guide = """
| db-replica-01 | database | 16 | 32 | 1000 | us-west-2 |
| worker-01 | worker | 16 | 64 | 500 | us-west-2 |
| web-01 | web | 8 | 16 | 200 | us-east-1 |
Nodes are distributed across us-east-1 and us-west-2.
"""

    _, failures = module._topology_result(guide)

    assert "guide does not identify the multi-region topology" not in failures


def test_deployed_across_is_equivalent_but_a_bare_region_list_is_not() -> None:
    module = _outcome_module()
    guide = """
| db-replica-01 | database | 16 | 32 | 1000 | us-west-2 |
| worker-01 | worker | 16 | 64 | 500 | us-west-2 |
| web-01 | web | 8 | 16 | 200 | us-east-1 |
Nodes are deployed across us-east-1 and us-west-2.
"""

    _, failures = module._topology_result(guide)
    assert "guide does not identify the multi-region topology" not in failures

    bare = guide.replace(
        "Nodes are deployed across us-east-1 and us-west-2.",
        "Regions: us-east-1, us-west-2.",
    )
    _, failures = module._topology_result(bare)
    assert "guide does not identify the multi-region topology" in failures


def test_deployed_in_two_named_regions_is_equivalent() -> None:
    module = _outcome_module()
    guide = """
| db-replica-01 | database | 16 | 32 | 1000 | us-west-2 |
| worker-01 | worker | 16 | 64 | 500 | us-west-2 |
| web-01 | web | 8 | 16 | 200 | us-east-1 |
Nodes are deployed in the us-east-1 and us-west-2 regions.
"""

    _, failures = module._topology_result(guide)
    assert "guide does not identify the multi-region topology" not in failures
