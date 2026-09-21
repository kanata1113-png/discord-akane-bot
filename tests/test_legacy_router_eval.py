from tools.evaluate_legacy_router import CASES
from services.routing_policy import RoutingPolicy


def test_legacy_router_evaluation_cases_match():
    for text, expected in CASES:
        assert RoutingPolicy.legacy_route(text) == expected
