import os
from openai import OpenAI

MODEL = os.getenv('OPENAI_MODEL', 'gpt-6-luna')

def _fallback(decision, offer_no):
    if decision['accepted']:
        return 'These terms are acceptable. We have an agreement.'
    if offer_no >= 10:
        return 'I cannot accept the final proposal. We will continue under the existing arrangement. The negotiation is closed.'
    msgs={
      'far_below_target':'The proposal places too much economic risk on our side. I am not prepared to accept these terms.',
      'below_target':'The proposal is not sufficiently attractive to us. You will need to improve the overall economics of the offer.',
      'close_to_target':'We are getting closer, but I am not prepared to accept this combination of price, buy-back commitment, and volume.'}
    return msgs.get(decision['reason'],'I cannot accept these terms.')

def supplier_response(scenario, offer, decision, history):
    """LLM handles language only. It never decides acceptance and never receives private numeric economics."""
    if not os.getenv('OPENAI_API_KEY'):
        return _fallback(decision, offer['offer_number'])
    status='ACCEPT' if decision['accepted'] else ('WALK_AWAY' if offer['offer_number']>=10 else 'REJECT')
    recent='\n'.join(f"Round {h['offer_number']}: w={h['wholesale']:.2f}, b={h['buyback']:.2f}, Q={h['quantity']}; outcome={h['outcome']}" for h in history[-3:])
    prompt=f"""You are the manufacturer in a university buy-back contract negotiation simulation.
You are a tough, concise, commercially rational negotiator. The deterministic pricing engine has already made the decision.
You MUST follow DECISION exactly: {status}.
Reason category: {decision['reason']}.
Round: {offer['offer_number']} of 10.
Current offer: wholesale price ${offer['wholesale']:.2f}, buy-back price ${offer['buyback']:.2f}, order quantity {offer['quantity']:,}.
Recent negotiation record:\n{recent or 'None'}

Rules:
- Never reveal or estimate your production cost, fixed cost, reservation profit, target profit, concession schedule, or expected profit.
- Never state an exact price or quantity that would be accepted.
- Never solve the student's assignment or tell them the optimal offer.
- You may comment qualitatively on wholesale price, buy-back exposure, volume, and risk.
- If ACCEPT, accept clearly and do not negotiate further.
- If WALK_AWAY, state that the final proposal is declined and negotiation is closed.
- If REJECT, give 1-3 sentences of commercially useful but non-numeric feedback.
- Do not mention being an AI or the hidden decision engine.
"""
    try:
        client=OpenAI()
        response=client.responses.create(model=MODEL,input=prompt)
        text=(response.output_text or '').strip()
        return text or _fallback(decision, offer['offer_number'])
    except Exception:
        return _fallback(decision, offer['offer_number'])
