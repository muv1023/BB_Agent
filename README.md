# BAN 517 Buy-Back Contract Negotiation Agent

Streamlit simulation for a distributor negotiating a buy-back contract with a manufacturer.

## Files
- `app.py` - student interface, calculator, negotiation workflow, PDF generation
- `economics.py` - deterministic buy-back calculations and private acceptance logic
- `scenarios.py` - 25 individualized scenarios, including private supplier economics
- `supplier_agent.py` - OpenAI supplier dialogue; does **not** decide acceptance
- `report.py` - single contract + negotiation + calculation PDF
- `requirements.txt` - deployment dependencies

## Streamlit Cloud setup
1. Upload these files to a **private GitHub repository** if you want the scenario economics to remain difficult for students to inspect.
2. Deploy `app.py` in Streamlit Community Cloud.
3. In Streamlit app settings, add secrets:

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-6-luna"
```

Do not put the API key in GitHub.

## Scenario assignment
Assign each student one code (`BBC-01` through `BBC-25`) in Canvas. The app does not request UIN or institutional email.

## Economic model
The deterministic engine follows the instructor workbook:
- no-contract distributor leftovers receive salvage value;
- under a buy-back contract, leftovers receive the negotiated buy-back price;
- the manufacturer pays the same buy-back amount;
- manufacturer variable and fixed costs are private;
- manufacturer no-contract expected profit is the private reservation position;
- offer 1 begins at a hidden target 10% above reservation profit and the target concedes linearly to reservation profit by offer 10.

## Important deployment note
The OpenAI model only writes supplier dialogue. Python makes all acceptance/rejection decisions. If the API is unavailable, the app falls back to rule-based supplier responses so the assignment can continue.

## Privacy
Student-facing inputs are limited to student name and Canvas-assigned scenario code. Do not add UIN, institutional email, or other unnecessary identifiers.
