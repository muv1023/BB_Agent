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

# v3: Workbook-derived case. Baseline salvage is an external sale, NOT a supplier payment.
DEMAND = [(12000,.071),(13000,.071),(14000,.143),(15000,.143),
          (16000,.214),(17000,.070),(18000,.143),(19000,.145)]
assert abs(sum(prob for _, prob in DEMAND)-1) < 1e-9
P, SALVAGE, Q, BASE_Q, BASE_W = 95., 42., 15000, 13000, 55.
FIXED_SUPPLIER_COST = 100000.
MAX_PROMPTS = 10
MIN_W, MAX_W, MIN_B, MAX_B = 35., 90., 0., 75.
TOL = .51

st.markdown('''<style>
.block-container{max-width:1460px;padding-top:1.25rem;padding-bottom:3rem}
.hero{background:linear-gradient(115deg,#003b5c,#006c67);border-radius:15px;padding:24px 28px;color:white;margin-bottom:17px}
.hero h1{color:white;margin:4px 0 6px;font-size:2rem}.hero p{color:#e5f5f4;margin:0}
</style>''', unsafe_allow_html=True)

def setting(key, default=None):
    try: return st.secrets[key]
    except Exception: return os.getenv(key.upper(), default)

SECRET = str(setting("scenario_secret", ""))
OPENAI_KEY = str(setting("OPENAI_API_KEY", ""))
OPENAI_MODEL = str(setting("openai_model", "gpt-6-luna"))


def unsold(q):
    return sum(prob * max(q-demand, 0) for demand, prob in DEMAND)


def buyer_profit(w, b, q=Q, baseline=False):
    return sum(prob * (P*min(demand,q) - w*q + (SALVAGE if baseline else b)*max(q-demand,0))
               for demand,prob in DEMAND)


def downside(w,b,q=Q,baseline=False):
    return P*min(DEMAND[0][0],q)-w*q+(SALVAGE if baseline else b)*max(q-DEMAND[0][0],0)

BASE_PROFIT = buyer_profit(BASE_W,0,BASE_Q,baseline=True)
BASE_LOW = downside(BASE_W,0,BASE_Q,baseline=True)


def private_cost(name):
    # Demo mode is blocked below; never use an unkeyed public hash for graded scenarios.
    digest=hmac.new(SECRET.encode(),name.strip().casefold().encode(),hashlib.sha256).digest()
    return 35 + (int.from_bytes(digest[:4],"big")%1101)/100


def supplier_profit(w,b,c):
    return (w-c)*Q-b*unsold(Q)-FIXED_SUPPLIER_COST


def supplier_baseline(c):
    return (BASE_W-c)*BASE_Q-FIXED_SUPPLIER_COST


def supplier_decision(w,b,c):
    return "accept" if (supplier_profit(w,b,c)>supplier_baseline(c)+.01 and buyer_profit(w,b)>BASE_PROFIT+.01) else "reject"


def supplier_reply(decision):
    fallback={
        "accept":"I can accept these terms. You may lock in the agreement or continue negotiating.",
        "reject":"I cannot accept these terms. Please reconsider your proposal.",
        "question":"I am willing to discuss the wholesale and buy-back prices. Please submit a specific proposal for consideration."
    }[decision]
    if not OPENAI_KEY: return fallback
    try:
        from openai import OpenAI
        client=OpenAI(api_key=OPENAI_KEY,timeout=12.0,max_retries=0)
        result=client.responses.create(
            model=OPENAI_MODEL,max_output_tokens=110,
            instructions=(
                "You are a professional supplier in a classroom buy-back negotiation. "
                "Write one concise sentence. Do not disclose costs, profits, reservation conditions, thresholds, "
                "or numbers, and do not make counteroffers or directional hints. "
                "The Python decision is authoritative; do not contradict it. "
                "Only say you accept if the decision is accept."),
            input=f"Authoritative supplier decision: {decision}. Respond accordingly.")
        text=(result.output_text or "").strip()
        if not text or re.search(r"\d|\$|cost|profit|threshold|margin|reservation",text,re.I): return fallback
        if decision=="accept" and not re.search(r"accept|agree",text,re.I): return fallback
        if decision=="reject" and not re.search(r"cannot|unable|reject|not accept|decline",text,re.I): return fallback
        return text
    except Exception:
        return fallback


def reset():
    for k in list(st.session_state):
        if k.startswith("bb_"): del st.session_state[k]


def initialize(name):
    st.session_state.bb_name=name.strip()
    st.session_state.bb_cost=private_cost(name)
    st.session_state.bb_baseline_verified=False
    st.session_state.bb_messages=[{"role":"assistant","content":
        "Welcome. The order quantity is fixed at 15,000 units. I will consider wholesale and buy-back offers. Both firms must improve on their existing arrangement."}]
    st.session_state.bb_log=[]
    st.session_state.bb_accepted=[]
    st.session_state.bb_last=(BASE_W,0.)
    st.session_state.bb_finished=None
    st.session_state.bb_final=None
    st.session_state.bb_started=datetime.now(timezone.utc).isoformat()


def finalize():
    if st.session_state.bb_finished is not None: return
    accepted=st.session_state.bb_accepted
    st.session_state.bb_final=max(accepted,key=lambda e:e["buyer_profit"]) if accepted else None
    st.session_state.bb_finished=datetime.now(timezone.utc).isoformat()


def record_prompt(message,decision,offer=None,student_profit=None,carried=""):
    number=len(st.session_state.bb_log)+1
    reply=supplier_reply(decision)
    if carried: reply=carried+" "+reply
    row={"prompt":number,"message":message,"decision":decision,
         "wholesale_price":offer[0] if offer else None,
         "buyback_price":offer[1] if offer else None,
         "buyer_expected_profit_entered":student_profit,"response":reply}
    st.session_state.bb_log.append(row)
    st.session_state.bb_messages.extend([{"role":"user","content":message},
                                          {"role":"assistant","content":reply}])
    if decision=="accept":
        st.session_state.bb_accepted.append({"wholesale_price":offer[0],"buyback_price":offer[1],
             "buyer_profit":buyer_profit(*offer),"prompt":number})
    if len(st.session_state.bb_log)>=MAX_PROMPTS: finalize()


def export_payload():
    f=st.session_state.bb_final
    return {"course":"BAN 517 Supply Chain Analytics","student_name":st.session_state.bb_name,
        "started_utc":st.session_state.bb_started,"finished_utc":st.session_state.bb_finished,
        "baseline_expected_profit_entered":st.session_state.bb_baseline_entry,
        "baseline_expected_profit_verified":True,"baseline_order_quantity":BASE_Q,
        "baseline_wholesale_price":BASE_W,"baseline_salvage":SALVAGE,"salvage_is_external":True,
        "prompts_used":len(st.session_state.bb_log),
        "rejections":sum(e["decision"]=="reject" for e in st.session_state.bb_log),
        "outcome":"agreement" if f else "no_agreement",
        "final_contract":({"wholesale_price":f["wholesale_price"],"buyback_price":f["buyback_price"],"order_quantity":Q} if f else None),
        "buyer_expected_profit":round(f["buyer_profit"],2) if f else None,
        "gain_over_baseline":round(f["buyer_profit"]-BASE_PROFIT,2) if f else 0,
        "lowest_demand_profit":round(downside(f["wholesale_price"],f["buyback_price"]),2) if f else None,
        "baseline_expected_profit":round(BASE_PROFIT,2),"baseline_low_demand_profit":round(BASE_LOW,2),
        "negotiation_log":st.session_state.bb_log,
        "buyer_improved":bool(f and f["buyer_profit"]>BASE_PROFIT),
        "supplier_improved_verified_privately":bool(f),
        "financial_method":"Baseline external salvage; contract unsold units returned at buyback price."}


def pdf_report(payload,code):
    buffer=io.BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=letter,leftMargin=46,rightMargin=46,topMargin=45,bottomMargin=45)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BBTitle",parent=styles["Title"],fontSize=17,textColor=colors.HexColor("#003b5c")))
    story=[Paragraph("Buy-Back Contract Negotiation",styles["BBTitle"]),
           Paragraph("BAN 517 | Final Decision Lab",styles["Normal"]),Spacer(1,10)]
    rows=[["Student",payload["student_name"]],["Outcome",payload["outcome"].replace("_"," ").title()],
          ["Verified baseline expected profit",f'${payload["baseline_expected_profit"]:,.2f}'],
          ["Prompts used",str(payload["prompts_used"])],["Rejections",str(payload["rejections"])],
          ["Completed (UTC)",payload["finished_utc"]],["Verification",code]]
    if payload["final_contract"]:
        f=payload["final_contract"]
        rows += [["Wholesale price",f'${f["wholesale_price"]:,.2f}'],
                 ["Buy-back price",f'${f["buyback_price"]:,.2f}'],["Order quantity",f'{Q:,}'],
                 ["Expected buyer profit",f'${payload["buyer_expected_profit"]:,.2f}'],
                 ["Gain over baseline",f'${payload["gain_over_baseline"]:,.2f}'],
                 ["Lowest-demand buyer profit",f'${payload["lowest_demand_profit"]:,.2f}']]
    else: rows.append(["Final contract","No agreement reached; baseline is reference only."])
    table=Table([[Paragraph(escape(str(a)),styles["Normal"]),Paragraph(escape(str(b)),styles["Normal"])] for a,b in rows],colWidths=[200,320])
    table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),.4,colors.HexColor("#dce4ea")),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#edf5f7")),("VALIGN",(0,0),(-1,-1),"TOP"),
        ("PADDING",(0,0),(-1,-1),6)]))
    story.append(table)
    story.append(Spacer(1,12))
    story.append(Paragraph("Negotiation record",styles["Heading2"]))
    for e in payload["negotiation_log"]:
        story.append(Paragraph(f'<b>Prompt {e["prompt"]}:</b> '+escape(e["message"]),styles["BodyText"]))
        if e["wholesale_price"] is not None:
            story.append(Paragraph(f'Offer: w=${e["wholesale_price"]:.2f}, b=${e["buyback_price"]:.2f}; '
                f'Buyer calculated profit=${e["buyer_expected_profit_entered"]:,.2f}',styles["Normal"]))
        story.append(Paragraph("Supplier: "+escape(e["response"]),styles["Normal"]))
        story.append(Spacer(1,6))
    story.append(Paragraph("BAN 517 | Dr. Manoj Vanajakumari",styles["Normal"]))
    doc.build(story)
    return buffer.getvalue()

st.markdown('''<div class="hero"><div style="font-size:.8rem;letter-spacing:1px">BAN 517 · FINAL DECISION LAB</div>
<h1>The Buy-Back Negotiation</h1><p>Analyze the numbers. Negotiate the terms. Own the decision.</p></div>''',unsafe_allow_html=True)

if not SECRET:
    st.error("Instructor configuration required: set scenario_secret in Streamlit Secrets before using the lab.")
    st.stop()

if "bb_name" not in st.session_state:
    st.subheader("Begin the final negotiation")
    st.write("You are the buyer. The supplier will negotiate the wholesale and buy-back prices. "
             "You will calculate expected profits in Excel and enter them before making offers.")
    name=st.text_input("Student full name",placeholder="First and last name")
    if st.button("Continue to baseline analysis",type="primary",disabled=not name.strip()):
        initialize(name);st.rerun()
    st.caption("BAN 517 · Dr. Manoj Vanajakumari")
    st.stop()

with st.sidebar:
    st.header("Contract case")
    st.write(f"**Student:** {st.session_state.bb_name}")
    st.metric("Selling price",f"${P:.0f}")
    st.metric("Salvage value (baseline)",f"${SALVAGE:.0f}")
    st.metric("Baseline wholesale price",f"${BASE_W:.0f}")
    st.metric("Baseline order quantity",f"{BASE_Q:,}")
    st.metric("Negotiated order quantity",f"{Q:,}")
    st.caption("Baseline salvage comes from an external market; it is not paid by the supplier.")
    st.write("**Demand scenarios**")
    st.dataframe(pd.DataFrame(DEMAND,columns=["Demand","Probability"]).style.format({"Demand":"{:,.0f}","Probability":"{:.0%}"}),hide_index=True,use_container_width=True)
    if st.button("Restart lab"):
        reset();st.rerun()

if not st.session_state.bb_baseline_verified:
    st.subheader("Stage 1 · Establish the no-contract baseline")
    st.write("In Excel, calculate expected buyer profit for the baseline order of 13,000 units at "
             "wholesale price $55, with a $42 EXTERNAL salvage value for each unsold unit. "
             "The supplier does not pay this baseline salvage value. Use the demand probabilities in the sidebar. "
             "The app will verify your calculation without revealing the answer.")
    value=st.number_input("Expected baseline buyer profit ($)",value=None,step=100.,format="%.2f")
    if st.button("Verify baseline and enter negotiation",type="primary",disabled=value is None):
        if abs(value-BASE_PROFIT)<=TOL:
            st.session_state.bb_baseline_entry=float(value)
            st.session_state.bb_baseline_verified=True
            st.rerun()
        else:
            st.error("Your calculation does not match the baseline case. Check the demand probabilities, salvage treatment, and wholesale payment in Excel.")
    st.stop()

st.subheader("Stage 2 · Negotiate the buy-back contract")
count=len(st.session_state.bb_log)
st.progress(count/MAX_PROMPTS,text=(f"Prompt {count+1} of {MAX_PROMPTS}" if count<MAX_PROMPTS else "10 of 10 prompts used"))

left,right=st.columns([1.65,1],gap="large")
with left:
    st.markdown("#### Supplier conversation")
    for message in st.session_state.bb_messages:
        with st.chat_message(message["role"]): st.write(message["content"])
    if st.session_state.bb_finished is None and count<MAX_PROMPTS:
        with st.form("bb_offer_form",clear_on_submit=False):
            st.write("**Prepare a contract offer using your Excel calculations**")
            c1,c2=st.columns(2)
            with c1: w=st.number_input("Wholesale price ($)",min_value=0.,max_value=300.,value=float(st.session_state.bb_last[0]),step=1.,format="%.2f")
            with c2: b=st.number_input("Buy-back price ($)",min_value=0.,max_value=300.,value=float(st.session_state.bb_last[1]),step=1.,format="%.2f")
            student_profit=st.number_input("My expected buyer profit from Excel ($)",value=None,step=100.,format="%.2f")
            note=st.text_input("Message to supplier (optional)",placeholder="I propose these terms for the 15,000-unit contract.")
            submitted=st.form_submit_button("Validate and submit offer",type="primary")
        if submitted:
            if not (MIN_W<=w<=MAX_W and MIN_B<=b<=MAX_B and b<=w):
                st.error(f"Use wholesale ${MIN_W:.0f}-${MAX_W:.0f}, buy-back ${MIN_B:.0f}-${MAX_B:.0f}, with buy-back no greater than wholesale. This offer was not submitted.")
            elif student_profit is None:
                st.error("Enter your Excel-calculated expected buyer profit before submitting.")
            elif abs(float(student_profit)-buyer_profit(w,b))>TOL:
                st.error("Your expected buyer profit does not match these contract terms. Check your Excel calculations and resubmit. This did not use a negotiation prompt.")
            elif buyer_profit(w,b)<=BASE_PROFIT+.01:
                st.error("This offer does not improve your buyer profit over the no-contract baseline. Revise your terms before contacting the supplier. No prompt used.")
            else:
                decision=supplier_decision(w,b,st.session_state.bb_cost)
                st.session_state.bb_last=(w,b)
                message=note.strip() or f"I offer wholesale ${w:.2f} and buy-back ${b:.2f}."
                record_prompt(message,decision,(w,b),float(student_profit))
                st.rerun()
        with st.expander("Ask the supplier a question (uses one prompt)"):
            question=st.text_input("Question",key="bb_question")
            if st.button("Send question",disabled=not question.strip()):
                record_prompt(question,"question")
                st.rerun()
    if st.session_state.bb_finished is None:
        if st.session_state.bb_accepted:
            st.info("An offer has been accepted and both parties benefit. You can finalize the best accepted contract or continue negotiating.")
            if st.button("Lock in best accepted contract",type="primary"):
                finalize();st.rerun()
        else:
            st.caption("No offer has been accepted yet.")
        if st.button("End negotiation now",type="secondary"):
            finalize();st.rerun()
    else:
        st.success("Negotiation complete." if st.session_state.bb_final else "Negotiation ended without an accepted contract.")

with right:
    st.markdown("#### Contract negotiation record")
    if st.session_state.bb_log:
        rows=[]
        for e in st.session_state.bb_log:
            rows.append({"Prompt":e["prompt"],"Wholesale":f'${e["wholesale_price"]:.2f}' if e["wholesale_price"] is not None else "-",
                "Buy-back":f'${e["buyback_price"]:.2f}' if e["buyback_price"] is not None else "-",
                "Buyer profit":f'${e["buyer_expected_profit_entered"]:,.2f}' if e["buyer_expected_profit_entered"] is not None else "-",
                "Supplier response":e["decision"].title()})
        st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    else: st.caption("Verified offers and supplier responses will appear here.")
    st.caption("Supplier cost, profit, and acceptance threshold remain confidential. A successful contract must benefit both firms.")

if st.session_state.bb_finished is not None:
    st.divider()
    st.header("Final negotiation outcome")
    f=st.session_state.bb_final
    if f:
        a,b,c=st.columns(3)
        a.metric("Wholesale price",f'${f["wholesale_price"]:.2f}')
        b.metric("Buy-back price",f'${f["buyback_price"]:.2f}')
        c.metric("Order quantity",f'{Q:,}')
        a,b,c=st.columns(3)
        a.metric("Buyer expected profit",f'${f["buyer_profit"]:,.2f}')
        b.metric("Gain over baseline",f'${f["buyer_profit"]-BASE_PROFIT:,.2f}')
        c.metric("Profit at lowest demand",f'${downside(f["wholesale_price"],f["buyback_price"]):,.2f}')
    else:
        st.warning("No agreement reached. The baseline is a comparison, not an accepted contract.")
    st.write(f'**Prompts used:** {len(st.session_state.bb_log)} · **Rejections:** {sum(e["decision"]=="reject" for e in st.session_state.bb_log)}')
    offers=[{"Prompt":e["prompt"],"Buyer expected profit":e["buyer_expected_profit_entered"]}
            for e in st.session_state.bb_log if e["buyer_expected_profit_entered"] is not None]
    if offers:
        st.markdown("#### Expected buyer profit by offer")
        st.line_chart(pd.DataFrame(offers).set_index("Prompt"))
    payload=export_payload()
    raw=json.dumps(payload,indent=2).encode()
    verification=hashlib.sha256(raw).hexdigest()[:16].upper()
    st.caption("Verification reference: "+verification)
    x,y=st.columns(2)
    safe_name=re.sub(r"[^A-Za-z0-9_-]+","_",st.session_state.bb_name).strip("_") or "student"
    x.download_button("Download final PDF",pdf_report(payload,verification),file_name=f"BAN517_Buyback_{safe_name}.pdf",mime="application/pdf",use_container_width=True)
    y.download_button("Download negotiation JSON",raw,file_name=f"BAN517_Buyback_{safe_name}.json",mime="application/json",use_container_width=True)
    st.caption("Final course decision lab · Dr. Manoj Vanajakumari")
