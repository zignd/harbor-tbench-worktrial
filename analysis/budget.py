"""Budget guard: refuse new model work that would breach the authorization or reserve.

Reads live spend from OpenRouter (the larger of its two lagging counters, see
analysis/openrouter.py) and compares it with the limits in generator/config.py.
Call `check(expected_usd)` before starting anything that calls a model.
"""

from analysis.openrouter import Spend, current_spend
from generator.config import BUDGET_AUTHORIZED_USD, BUDGET_RESERVE_USD


class BudgetExceeded(RuntimeError):
    pass


def check(
    expected_usd: float,
    spend: Spend | None = None,
    authorized_usd: float = BUDGET_AUTHORIZED_USD,
    reserve_usd: float = BUDGET_RESERVE_USD,
) -> Spend:
    """Raise BudgetExceeded if spending `expected_usd` more would break a limit."""
    spend = spend or current_spend()
    after = spend.spent + expected_usd
    if after > authorized_usd:
        raise BudgetExceeded(
            f"would spend ${after:.2f} in total, over the ${authorized_usd:.2f} authorization "
            f"(spent ${spend.spent:.2f}, this step ~${expected_usd:.2f})"
        )
    if spend.limit is not None and spend.limit - after < reserve_usd:
        raise BudgetExceeded(
            f"remaining credit would drop to ${spend.limit - after:.2f}, "
            f"below the ${reserve_usd:.2f} reserve"
        )
    return spend
