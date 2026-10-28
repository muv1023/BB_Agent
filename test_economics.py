from scenarios import get_scenario
from economics import *

s=get_scenario('BBC-01')
assert abs(distributor_no_contract(s)-532500) < 1e-6
assert abs(supplier_no_contract(s)-485000) < 1e-6
m=buyback_metrics(s,80,40,14000)
assert abs(m['distributor_profit']-543300) < 1e-6
assert abs(m['supplier_profit']-489200) < 1e-6
assert abs(m['supply_chain_profit']-1032500) < 1e-6
assert abs(concession_target(s,1)-533500) < 1e-6
assert abs(concession_target(s,10)-485000) < 1e-6
print('Base workbook checks passed.')
