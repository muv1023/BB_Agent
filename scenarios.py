from economics import Scenario

BASE_DEMAND = [5000,10000,11000,11500,12000,12500,13000,14000,15000,15500,16500,17500]
BASE_PROB = [.01,.02,.04,.09,.09,.11,.16,.21,.11,.10,.04,.02]

# Curated parameter sets. Codes can be assigned in Canvas; no institutional ID is required.
_RAW = [
('BBC-01',125,80,20,13000,1.00,35.0,100000),
('BBC-02',122,78,18,12750,.97,34.0,96000),
('BBC-03',128,82,22,13250,1.03,36.0,104000),
('BBC-04',120,77,17,12500,.94,33.5,93000),
('BBC-05',130,84,23,13500,1.06,37.0,108000),
('BBC-06',124,79,19,13000,1.01,34.5,99000),
('BBC-07',127,81,21,13250,1.04,35.5,102000),
('BBC-08',121,76,18,12500,.95,33.0,94000),
('BBC-09',129,83,22,13500,1.05,36.5,106000),
('BBC-10',126,80,20,13000,1.02,35.0,101000),
('BBC-11',123,78,19,12750,.98,34.0,97000),
('BBC-12',131,85,24,13750,1.07,37.5,110000),
('BBC-13',119,75,16,12250,.92,32.5,91000),
('BBC-14',128,81,21,13250,1.03,35.5,103000),
('BBC-15',125,79,20,13000,1.00,34.5,98000),
('BBC-16',132,86,24,13750,1.08,38.0,112000),
('BBC-17',122,77,18,12500,.96,33.5,95000),
('BBC-18',127,82,21,13250,1.04,36.0,105000),
('BBC-19',124,80,19,13000,1.01,35.0,100000),
('BBC-20',130,83,23,13500,1.06,36.5,107000),
('BBC-21',121,77,17,12500,.95,33.0,93000),
('BBC-22',129,84,22,13500,1.05,37.0,109000),
('BBC-23',126,81,20,13000,1.02,35.5,102000),
('BBC-24',123,79,18,12750,.98,34.5,98000),
('BBC-25',131,85,23,13750,1.07,37.5,111000),
]

def _scaled_demand(scale):
    return [int(round(x*scale/250.0)*250) for x in BASE_DEMAND]

def _make(row):
    code,p,w,salv,q,scale,c,f=row
    # Competitive intelligence is intentionally imperfect and somewhat conservative.
    best=c+2.5
    return Scenario(code,p,w,salv,q,_scaled_demand(scale),BASE_PROB,c,f,
                    max(1,c-1.0),best,c+5.0,
                    max(0,f-12000),f+5000,f+22000)

SCENARIOS={r[0]:_make(r) for r in _RAW}
for s in SCENARIOS.values(): s.validate()

def get_scenario(code: str) -> Scenario:
    key=(code or '').strip().upper()
    if key not in SCENARIOS:
        raise KeyError('Scenario code not recognized.')
    return SCENARIOS[key]
