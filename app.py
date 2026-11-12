import hashlib
import hmac
import io
import json
import os
import re
from datetime import datetime, timezone
from html import escape

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

st.set_page_config(page_title="Buy-Back Contract | BAN 517", page_icon="🤝", layout="wide")

# Course case: lecture probabilities extended with explicit high-demand outcomes.
DEMAND = [(5000,.01),(10000,.02),(11000,.04),(11500,.09),(12000,.09),
          (12500,.11),(13000,.16),(14000,.20),(15000,.15),(16000,.13)]
assert abs(sum(p for _,p in DEMAND)-1)<1e-10
SELLING_PRICE=125.0
SALVAGE=20.0
Q=15000
BASE_Q=13000
BASE_W=80.0
BASE_BUYBACK=0.0
BASELINE_BUYER_PROFIT=532500.0
BASELINE_LOW_PROFIT=-255000.0
MAX_PROMPTS=10
MIN_W,MAX_W=40.0,120.0
MIN_B,MAX_B=0.0,100.0

st.markdown('''<style>
.block-container{max-width:1450px;padding-top:1.4rem;padding-bottom:3rem}
.hero{background:linear-gradient(115deg,#003b5c,#006c67);border-radius:16px;padding:23px 27px;color:white;margin-bottom:16px}
.hero h1{color:white;margin:4px 0 7px;font-size:2rem}.hero p{margin:0;color:#e5f5f4}
.small{font-size:.85rem;color:#536476}.kpi{border:1px solid #dce5ea;border-radius:12px;padding:12px}
</style>''',unsafe_allow_html=True)

def cfg(key, default=None):
    try: return st.secrets[key]
    except Exception: return os.getenv(key.upper(),default)

SECRET=str(cfg('scenario_secret',''))
GEMINI_KEY=str(cfg('gemini_api_key',''))
GEMINI_MODEL=str(cfg('gemini_model','gemini-2.5-flash'))

def scenario_cost(student_id):
    if not SECRET:
        return 35.0  # demo mode only; not suitable for private individualized assessment
    digest=hmac.new(SECRET.encode(),student_id.strip().upper().encode(),hashlib.sha256).digest()
    return 32.0 + (int.from_bytes(digest[:4],'big')%601)/100.0

def expected_unsold(q):
    return sum(prob*max(q-demand,0) for demand,prob in DEMAND)

def buyer_profit(w,b,q=Q):
    # Contract: all unsold units are returned at b; there is no separate salvage payment.
    return sum(prob*(SELLING_PRICE*min(demand,q)-w*q+b*max(q-demand,0)) for demand,prob in DEMAND)

def low_profit(w,b,q=Q):
    return SELLING_PRICE*min(DEMAND[0][0],q)-w*q+b*max(q-DEMAND[0][0],0)

def supplier_profit(w,b,c,q=Q):
    return (w-c)*q-b*expected_unsold(q)-100000.0

def supplier_baseline(c):
    return (BASE_W-c)*BASE_Q-100000.0

def evaluate(w,b,c):
    valid=MIN_W<=w<=MAX_W and MIN_B<=b<=MAX_B and b<=w
    if not valid: return {'decision':'invalid','reason':'outside_allowed_terms'}
    ok=supplier_profit(w,b,c)>=supplier_baseline(c)-1e-7
    return {'decision':'accept' if ok else 'reject','reason':'none' if ok else 'terms_unacceptable'}

def extract_number(pattern, message):
    m=re.search(pattern,message,re.I)
    return float(m.group(1).replace(',','')) if m else None

def parse_message(message):
    t=message.strip()
    low=t.lower()
    w=extract_number(r'(?:wholesale(?:\s+price)?|\bw\b)\s*(?:=|:|of|to|at|is)?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)',t)
    b=extract_number(r'(?:buy[ -]?back(?:\s+price)?|\bb\b)\s*(?:=|:|of|to|at|is)?\s*\$?\s*(\d+(?:,\d{3})*(?:\.\d+)?)',t)
    q=extract_number(r'(?:order\s+quantity|quantity|\bq\b)\s*(?:=|:|of|to|at|is)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)',t)
    # Recognize plain paired prices: "offer $80 and $40" only if both clearly labeled; otherwise ask for clarity.
    if 'lock in' in low or 'finalize' in low: intent='lock_in'
    elif 'accept last' in low or 'accept your offer' in low: intent='accept_last'
    elif w is not None or b is not None or q is not None: intent='offer'
    elif '?' in t or any(x in low for x in ('explain','why','what','how','can you','could you')): intent='question'
    else: intent='other'
    return {'intent':intent,'wholesale_price':w,'buyback_price':b,'order_quantity':q}

def supplier_words(decision, prompt_count, offer=None, carry=None):
    if decision=='accept': return 'I can accept these contract terms. You may lock in this agreement or continue negotiating.'
    if decision=='reject': return 'I cannot accept these contract terms. Please revise your offer.'
    if decision=='invalid': return f'Please provide valid terms: wholesale ${MIN_W:.0f}-${MAX_W:.0f}, buy-back ${MIN_B:.0f}-${MAX_B:.0f}, and buy-back no greater than wholesale.'
    if decision=='fixed': return 'The order quantity is fixed at 15,000 units. Please submit your wholesale and buy-back prices.'
    if decision=='question': return 'The wholesale and buy-back prices are negotiable. I can evaluate a specific offer, but I cannot disclose my private financial information.'
    return 'Please submit an offer by stating the wholesale price and buy-back price.'

# AI handles wording only. Python decision and numerical terms are authoritative.
def ai_supplier_wording(decision, prompt_count):
    if not GEMINI_KEY: return supplier_words(decision,prompt_count)
    try:
        import urllib.request
        url=f'https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}'
        instruction=('You are a concise professional supplier in a teaching negotiation. '
            'Write one or two short sentences. No numerical counteroffers, no hints, no cost or profit information. '
            'Do not reverse the decision. Decision: '+decision+'. '
            'If accept, confirm acceptance. If reject, say terms cannot be accepted. '
            'If question, invite a specific offer without revealing private finances.')
        data=json.dumps({'contents':[{'parts':[{'text':instruction}]}],'generationConfig':{'temperature':0.2,'maxOutputTokens':100}}).encode()
        req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(req,timeout=8) as response: payload=json.loads(response.read())
        text=payload['candidates'][0]['content']['parts'][0]['text'].strip()
        # Only use generated prose when it respects the deterministic decision and no digits leak.
        if not text or re.search(r'\d|\$|cost|profit|threshold|margin',text,re.I): return supplier_words(decision,prompt_count)
        if decision=='accept' and not re.search(r'accept|agree',text,re.I): return supplier_words(decision,prompt_count)
        if decision=='reject' and not re.search(r'cannot|unable|reject|not accept',text,re.I): return supplier_words(decision,prompt_count)
        return text
    except Exception: return supplier_words(decision,prompt_count)

def reset():
    for key in list(st.session_state):
        if key.startswith('bb_'): del st.session_state[key]

def start(student_id):
    st.session_state.bb_id=student_id.strip()
    st.session_state.bb_cost=scenario_cost(student_id)
    st.session_state.bb_messages=[{'role':'assistant','content':'Welcome. I am ready to review your wholesale and buy-back price proposals. The order quantity is fixed at 15,000 units.'}]
    st.session_state.bb_log=[]
    st.session_state.bb_accepted=[]
    st.session_state.bb_last=(80.0,0.0)
    st.session_state.bb_final=None
    st.session_state.bb_started=datetime.now(timezone.utc).isoformat()


def finalize():
    accepted=st.session_state.bb_accepted
    st.session_state.bb_final=max(accepted,key=lambda x:x['buyer_profit']) if accepted else None
    st.session_state.bb_finished=datetime.now(timezone.utc).isoformat()


def report_payload():
    final=st.session_state.bb_final
    return {'course':'BAN 517 Supply Chain Analytics','student_id':st.session_state.bb_id,
        'started_utc':st.session_state.bb_started,'completed_utc':st.session_state.bb_finished,
        'prompts_used':len(st.session_state.bb_log),
        'rejections':sum(x.get('decision')=='reject' for x in st.session_state.bb_log),
        'outcome':'agreement' if final else 'no_agreement',
        'final_contract':({'wholesale_price':final['wholesale_price'],'buyback_price':final['buyback_price'],'order_quantity':Q} if final else None),
        'buyer_expected_profit':round(final['buyer_profit'],2) if final else None,
        'gain_over_baseline':round(final['buyer_profit']-BASELINE_BUYER_PROFIT,2) if final else 0,
        'buyer_low_demand_profit':round(low_profit(final['wholesale_price'],final['buyback_price']),2) if final else None,
        'baseline':{'order_quantity':BASE_Q,'wholesale_price':BASE_W,'buyback_price':0,'expected_buyer_profit':BASELINE_BUYER_PROFIT,'low_demand_buyer_profit':BASELINE_LOW_PROFIT},
        'offers_and_messages':st.session_state.bb_log}

def make_pdf(payload):
    buff=io.BytesIO()
    doc=SimpleDocTemplate(buff,pagesize=letter,leftMargin=46,rightMargin=46,topMargin=48,bottomMargin=46)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BBtitle',parent=styles['Title'],textColor=colors.HexColor('#003b5c'),fontSize=17))
    styles.add(ParagraphStyle(name='BBsection',parent=styles['Heading2'],textColor=colors.HexColor('#006c67'),spaceBefore=12))
    story=[Paragraph('Buy-Back Contract Negotiation',styles['BBtitle']),
           Paragraph('BAN 517 | Final Negotiation Record',styles['Normal']),Spacer(1,12)]
    rows=[['Student ID',payload['student_id']],['Outcome',payload['outcome'].replace('_',' ').title()],
          ['Prompts used',str(payload['prompts_used'])],['Rejections',str(payload['rejections'])],
          ['Completed (UTC)',payload['completed_utc']]]
    if payload['final_contract']:
        f=payload['final_contract']
        rows.extend([['Wholesale price',f"${f['wholesale_price']:,.2f}"],['Buy-back price',f"${f['buyback_price']:,.2f}"],
                     ['Order quantity',f'{Q:,} units'],['Buyer expected profit',f"${payload['buyer_expected_profit']:,.2f}"],
                     ['Gain over baseline',f"${payload['gain_over_baseline']:,.2f}"],
                     ['Buyer profit at demand 5,000',f"${payload['buyer_low_demand_profit']:,.2f}"]])
    else: rows.append(['Result','No agreement reached; baseline remains the reference outcome.'])
    rows.extend([['Baseline expected buyer profit',f'${BASELINE_BUYER_PROFIT:,.2f}'],
                 ['Baseline low-demand profit',f'${BASELINE_LOW_PROFIT:,.2f}']])
    t=Table([[Paragraph(escape(str(a)),styles['Normal']),Paragraph(escape(str(b)),styles['Normal'])] for a,b in rows],colWidths=[205,315])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.35,colors.HexColor('#d7e1e7')),
        ('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef5f7')),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),6)]))
    story.append(t)
    story.append(Paragraph('Negotiation history',styles['BBsection']))
    for entry in payload['offers_and_messages']:
        n=entry['prompt']
        story.append(Paragraph(f"<b>Prompt {n}:</b> {escape(entry['message'])}",styles['BodyText']))
        if entry.get('wholesale_price') is not None:
            story.append(Paragraph(f"Effective offer: w = ${entry['wholesale_price']:.2f}; b = ${entry['buyback_price']:.2f}; Q = {Q:,}",styles['Normal']))
        story.append(Paragraph('Supplier: '+escape(entry['response']),styles['Normal']))
        story.append(Spacer(1,6))
    story.append(Spacer(1,10))
    story.append(Paragraph('Prepared for BAN 517, Dr. Manoj Vanajakumari.',styles['Normal']))
    doc.build(story)
    return buff.getvalue()

st.markdown('''<div class="hero"><div style="font-size:.8rem;letter-spacing:1px">BAN 517 · FINAL DECISION LAB</div>
<h1>The Buy-Back Negotiation</h1><p>Two prices. One agreement. Every concession has a cost.</p></div>''',unsafe_allow_html=True)

if 'bb_id' not in st.session_state:
    st.subheader('Begin your negotiation')
    st.write('You are a retailer negotiating a buy-back contract with a supplier. The order quantity is fixed at **15,000 units**. You may negotiate the wholesale price and buy-back price, but the supplier must find the agreement acceptable. You have ten messages. Analyze the contract economics before you make an offer.')
    sid=st.text_input('Student ID',placeholder='Enter your student ID')
    if st.button('Start negotiation',type='primary',disabled=not sid.strip()):
        start(sid)
        st.rerun()
    st.caption('Developed for BAN 517 · Dr. Manoj Vanajakumari')
    st.stop()

with st.sidebar:
    st.header('Case information')
    st.metric('Selling price',f'${SELLING_PRICE:.0f}')
    st.metric('Salvage value (baseline only)',f'${SALVAGE:.0f}')
    st.metric('Negotiated order quantity',f'{Q:,} units')
    st.markdown('**Demand distribution**')
    st.dataframe(pd.DataFrame(DEMAND,columns=['Demand','Probability']).style.format({'Demand':'{:,.0f}','Probability':'{:.0%}'}),hide_index=True,use_container_width=True)
    st.markdown('**Existing baseline (no buy-back)**')
    st.write(f'Order: {BASE_Q:,} · Wholesale: ${BASE_W:.0f}')
    st.metric('Expected buyer profit',f'${BASELINE_BUYER_PROFIT:,.0f}')
    st.metric('Profit at demand 5,000',f'${BASELINE_LOW_PROFIT:,.0f}')
    st.caption('In the negotiated contract, all unsold units are returned at the buy-back price. The baseline uses $20 salvage on unsold units.')
    if not SECRET: st.warning('Demo configuration: set scenario_secret in Streamlit Secrets before graded use.')

chat_tab,calc_tab=st.tabs(['Supplier negotiation','Buyer calculator'])
with calc_tab:
    st.subheader('Evaluate your own position')
    st.caption('This calculator does not use a prompt and does not predict supplier acceptance.')
    a,b=st.columns(2)
    with a: cw=st.number_input('Wholesale price ($)',min_value=MIN_W,max_value=MAX_W,value=80.0,step=1.0,key='bb_calc_w')
    with b: cb=st.number_input('Buy-back price ($)',min_value=MIN_B,max_value=MAX_B,value=40.0,step=1.0,key='bb_calc_b')
    if cb>cw: st.error('Buy-back price cannot exceed wholesale price.')
    else:
        c1,c2,c3=st.columns(3)
        c1.metric('Expected buyer profit',f'${buyer_profit(cw,cb):,.0f}')
        c2.metric('Gain vs. baseline',f'${buyer_profit(cw,cb)-BASELINE_BUYER_PROFIT:,.0f}')
        c3.metric('Profit at demand 5,000',f'${low_profit(cw,cb):,.0f}')
        st.caption('Calculator results describe buyer economics only; they do not indicate whether the supplier will accept.')

with chat_tab:
    left,right=st.columns([1.8,1],gap='large')
    with left:
        count=len(st.session_state.bb_log)
        st.progress(count/MAX_PROMPTS,text=f'Prompt {min(count+1,MAX_PROMPTS)} of {MAX_PROMPTS}' if count<MAX_PROMPTS else '10 of 10 prompts used')
        for m in st.session_state.bb_messages:
            with st.chat_message(m['role']): st.write(m['content'])
        if st.session_state.bb_final is None and not hasattr(st.session_state,'bb_finished') and count<MAX_PROMPTS:
            message=st.chat_input('Propose wholesale $80, buyback $40; or ask a question')
            if message:
                parsed=parse_message(message)
                decision='other'; offer=None; carry=[]
                if parsed['order_quantity'] is not None and parsed['order_quantity']!=Q:
                    decision='fixed'
                elif parsed['intent']=='offer':
                    lastw,lastb=st.session_state.bb_last
                    w=parsed['wholesale_price'] if parsed['wholesale_price'] is not None else lastw
                    b=parsed['buyback_price'] if parsed['buyback_price'] is not None else lastb
                    if parsed['wholesale_price'] is None: carry.append(f'Wholesale ${w:.2f} carried forward.')
                    if parsed['buyback_price'] is None: carry.append(f'Buy-back ${b:.2f} carried forward.')
                    offer={'wholesale_price':w,'buyback_price':b}
                    decision=evaluate(w,b,st.session_state.bb_cost)['decision']
                    if decision!='invalid':
                        st.session_state.bb_last=(w,b)
                        if decision=='accept':
                            st.session_state.bb_accepted.append({**offer,'buyer_profit':buyer_profit(w,b),'prompt':count+1})
                elif parsed['intent']=='question': decision='question'
                else: decision='other'
                reply=supplier_words(decision,count+1) if decision in ('invalid','fixed','other') else ai_supplier_wording(decision,count+1)
                if carry and offer: reply=' '.join(carry)+' '+reply
                entry={'prompt':count+1,'message':message,'intent':parsed['intent'],
                       'wholesale_price':offer['wholesale_price'] if offer else None,
                       'buyback_price':offer['buyback_price'] if offer else None,
                       'decision':decision,'response':reply}
                st.session_state.bb_log.append(entry)
                st.session_state.bb_messages.extend([{'role':'user','content':message},{'role':'assistant','content':reply}])
                if len(st.session_state.bb_log)>=MAX_PROMPTS: finalize()
                st.rerun()
        if not hasattr(st.session_state,'bb_finished'):
            if st.session_state.bb_accepted:
                st.info('You have an accepted contract. You may lock it in or continue negotiating.')
                if st.button('Lock in best accepted contract',type='primary'):
                    finalize();st.rerun()
            else: st.caption('No contract has been accepted yet.')
        else:
            st.success('Negotiation completed.' if st.session_state.bb_final else 'Negotiation ended without an accepted contract.')
    with right:
        st.subheader('Offer log')
        if not st.session_state.bb_log: st.caption('Your offers and supplier responses will appear here.')
        else:
            log=[]
            for e in st.session_state.bb_log:
                log.append({'Prompt':e['prompt'],'Wholesale':f"${e['wholesale_price']:.2f}" if e['wholesale_price'] is not None else '-',
                    'Buy-back':f"${e['buyback_price']:.2f}" if e['buyback_price'] is not None else '-',
                    'Response':e['decision'].replace('_',' ').title()})
            st.dataframe(pd.DataFrame(log),hide_index=True,use_container_width=True)
        st.caption('Supplier costs and acceptance thresholds are never shown.')

if hasattr(st.session_state,'bb_finished'):
    st.divider()
    st.header('Your final contract')
    f=st.session_state.bb_final
    if f:
        c1,c2,c3=st.columns(3)
        c1.metric('Wholesale price',f"${f['wholesale_price']:.2f}")
        c2.metric('Buy-back price',f"${f['buyback_price']:.2f}")
        c3.metric('Order quantity',f'{Q:,}')
        a,b,c=st.columns(3)
        a.metric('Expected buyer profit',f"${f['buyer_profit']:,.0f}")
        b.metric('Gain vs. baseline',f"${f['buyer_profit']-BASELINE_BUYER_PROFIT:,.0f}")
        c.metric('Profit at demand 5,000',f"${low_profit(f['wholesale_price'],f['buyback_price']):,.0f}")
    else: st.warning('No agreement reached. The baseline is shown for comparison, not as an accepted new contract.')
    st.write(f"**Prompts used:** {len(st.session_state.bb_log)} · **Rejections:** {sum(e['decision']=='reject' for e in st.session_state.bb_log)}")
    offers=[{'Prompt':e['prompt'],'Expected buyer profit':buyer_profit(e['wholesale_price'],e['buyback_price'])} for e in st.session_state.bb_log if e['wholesale_price'] is not None and e['decision'] in ('accept','reject')]
    if offers:
        st.subheader('Buyer profit across your offers')
        st.line_chart(pd.DataFrame(offers).set_index('Prompt'))
    payload=report_payload()
    raw=json.dumps(payload,indent=2).encode()
    code=hashlib.sha256(raw).hexdigest()[:16].upper()
    st.caption('Submission verification: '+code+' · Keep your PDF and JSON together.')
    d1,d2=st.columns(2)
    d1.download_button('Download final PDF',make_pdf(payload),file_name=f"BAN517_Buyback_{st.session_state.bb_id}.pdf",mime='application/pdf',use_container_width=True)
    d2.download_button('Download JSON negotiation log',raw,file_name=f"BAN517_Buyback_{st.session_state.bb_id}.json",mime='application/json',use_container_width=True)
    st.caption('Final course challenge · Dr. Manoj Vanajakumari')
