from dataclasses import dataclass
from typing import List, Dict

@dataclass(frozen=True)
class Scenario:
    code: str
    retail_price: float
    baseline_wholesale: float
    salvage_value: float
    baseline_q: int
    demand: List[int]
    probabilities: List[float]
    supplier_unit_cost: float
    supplier_fixed_cost: float
    intel_unit_cost_low: float
    intel_unit_cost_best: float
    intel_unit_cost_high: float
    intel_fixed_cost_low: float
    intel_fixed_cost_best: float
    intel_fixed_cost_high: float

    def validate(self):
        if len(self.demand) != len(self.probabilities):
            raise ValueError('Demand/probability length mismatch')
        if abs(sum(self.probabilities)-1.0) > 1e-8:
            raise ValueError('Probabilities must sum to 1')
        if not (0 <= self.salvage_value < self.baseline_wholesale < self.retail_price):
            raise ValueError('Expected salvage < wholesale < retail')


def expected_units(s: Scenario, q: int) -> Dict[str, float]:
    sold = sum(p * min(d, q) for d, p in zip(s.demand, s.probabilities))
    leftover = sum(p * max(q-d, 0) for d, p in zip(s.demand, s.probabilities))
    return {'sold': sold, 'leftover': leftover}


def distributor_no_contract(s: Scenario, q: int | None = None) -> float:
    q = s.baseline_q if q is None else int(q)
    u = expected_units(s, q)
    return s.retail_price*u['sold'] + s.salvage_value*u['leftover'] - s.baseline_wholesale*q


def supplier_no_contract(s: Scenario, q: int | None = None) -> float:
    q = s.baseline_q if q is None else int(q)
    return s.baseline_wholesale*q - s.supplier_unit_cost*q - s.supplier_fixed_cost


def buyback_metrics(s: Scenario, wholesale: float, buyback: float, q: int,
                    supplier_unit_cost: float | None = None,
                    supplier_fixed_cost: float | None = None) -> Dict[str, float]:
    q = int(q)
    if q <= 0:
        raise ValueError('Order quantity must be positive')
    if wholesale <= 0 or wholesale >= s.retail_price:
        raise ValueError('Wholesale price must be between 0 and retail price')
    if buyback < 0 or buyback >= wholesale:
        raise ValueError('Buy-back price must be nonnegative and below wholesale price')
    u = expected_units(s, q)
    distributor_profit = s.retail_price*u['sold'] + buyback*u['leftover'] - wholesale*q
    c = s.supplier_unit_cost if supplier_unit_cost is None else supplier_unit_cost
    f = s.supplier_fixed_cost if supplier_fixed_cost is None else supplier_fixed_cost
    supplier_profit = wholesale*q - c*q - f - buyback*u['leftover']
    return {
        'expected_sold': u['sold'],
        'expected_returns': u['leftover'],
        'distributor_profit': distributor_profit,
        'supplier_profit': supplier_profit,
        'supply_chain_profit': distributor_profit + supplier_profit,
    }


def intel_supplier_profit(s: Scenario, wholesale: float, buyback: float, q: int, case='best') -> float:
    c = getattr(s, f'intel_unit_cost_{case}')
    f = getattr(s, f'intel_fixed_cost_{case}')
    return buyback_metrics(s, wholesale, buyback, q, c, f)['supplier_profit']


def concession_target(s: Scenario, offer_number: int, window: float = 0.10) -> float:
    """Linear concession from +10% of reservation profit on offer 1 to reservation on offer 10."""
    reservation = supplier_no_contract(s)
    n = max(1, min(10, int(offer_number)))
    premium = window * (10-n) / 9.0
    return reservation * (1.0 + premium)


def evaluate_offer(s: Scenario, wholesale: float, buyback: float, q: int, offer_number: int) -> Dict[str, float | str | bool]:
    m = buyback_metrics(s, wholesale, buyback, q)
    reservation = supplier_no_contract(s)
    target = concession_target(s, offer_number)
    acceptable = m['supplier_profit'] >= target
    if acceptable:
        reason = 'acceptable'
    else:
        gap = target - m['supplier_profit']
        ratio = gap / max(abs(target), 1.0)
        if ratio > .08:
            reason = 'far_below_target'
        elif ratio > .03:
            reason = 'below_target'
        else:
            reason = 'close_to_target'
    return {**m, 'reservation_profit': reservation, 'target_profit': target,
            'accepted': acceptable, 'reason': reason}
