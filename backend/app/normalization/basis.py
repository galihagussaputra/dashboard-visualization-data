from collections import defaultdict
from typing import Iterable


def assert_same_basis(basis: str, inputs: Iterable[tuple[str, str]]) -> list[str]:
    by_basis: dict[str, list[str]] = defaultdict(list)
    for role, value in inputs:
        by_basis[value].append(role)
    if len(by_basis) <= 1:
        return []
    return [
        f"BASIS_MISMATCH:{':'.join(sorted(roles))}"
        for roles in by_basis.values()
        if roles
    ]


def publication_basis_is_explicit(basis: str) -> bool:
    return basis in {"consolidated", "separate"}


def fact_group_key(company_id: int, period_id: int, basis: str) -> tuple[int, int, str]:
    return company_id, period_id, basis
