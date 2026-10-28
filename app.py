import streamlit as st
import pandas as pd
from economics import distributor_no_contract, buyback_metrics, intel_supplier_profit, evaluate_offer
from scenarios import get_scenario
from supplier_agent import supplier_response
from report import build_report

st.set_page_config(page_title='BAN 517 Buy-Back Contract Negotiation', page_icon='🤝', layout='wide')

st.markdown('''<style>
.block-container{max-width:1100px;padding-top:2rem}.hero{background:linear-gradient(135deg,#003b5c,#006c67);padding:24px;border-radius:16px;color:white;margin-bottom:18px}.hero h1{color:white;margin:0}.card{border:1px solid #dfe5ec;border-radius:12px;padding:16px;margin:10px 0}.small{color:#536474;font-size:.92rem}
</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>Buy-Back Contract Negotiation</h1><p>BAN 517 Supply Chain Analytics</p></div>',unsafe_allow_html=True)

for k,v in {'started':False,'history':[],'closed':False,'accepted':False,'scenario':None}.items():
    if k not in st.session_state: st.session_state[k]=v

if not st.session_state.started:
    st.subheader('Start Your Negotiation')
    name=st.text_input('Student name')
    code=st.text_input('Scenario code',placeholder='BBC-17')
    st.caption('Use the scenario code assigned in Canvas. Do not enter your UIN or institutional credentials.')
    if st.button('Load Scenario',type='primary'):
        try:
            s=get_scenario(code); st.session_state.scenario=s; st.session_state.student_name=name.strip(); st.session_state.started=True; st.rerun()
        except KeyError: st.error('Scenario code not recognized.')
    st.stop()

s=st.session_state.scenario
base_profit=distributor_no_contract(s)

st.subheader(f'Scenario {s.code}')
c1,c2,c3,c4=st.columns(4)
c1.metric('Retail price',f'${s.retail_price:,.2f}')
c2.metric('Baseline wholesale',f'${s.baseline_wholesale:,.2f}')
c3.metric('Salvage value without contract',f'${s.salvage_value:,.2f}')
c4.metric('Baseline order quantity',f'{s.baseline_q:,}')
st.info(f'Your expected distributor profit under the existing arrangement is **${base_profit:,.2f}**. Your objective is not merely to obtain a signature; protect the distributor\'s economic interests while reaching a mutually acceptable agreement.')

with st.expander('Demand distribution',expanded=False):
    st.dataframe(pd.DataFrame({'Demand':s.demand,'Probability':s.probabilities}),hide_index=True,use_container_width=True)
with st.expander('Competitive intelligence about the supplier',expanded=True):
    st.write(f'''Industry intelligence suggests the supplier's unit production cost may be between **${s.intel_unit_cost_low:,.2f} and ${s.intel_unit_cost_high:,.2f}**, with a best estimate near **${s.intel_unit_cost_best:,.2f}**. Estimated fixed manufacturing cost is between **${s.intel_fixed_cost_low:,.0f} and ${s.intel_fixed_cost_high:,.0f}**, with a best estimate near **${s.intel_fixed_cost_best:,.0f}**. These estimates are unverified. The supplier's actual economics are private.''')

st.divider(); st.subheader('Contract Calculator')
st.write('Analyze each offer before submitting it. The calculator uses the buy-back model from the module. The supplier independently evaluates the same offer using its private economics.')
col1,col2,col3=st.columns(3)
with col1: w=st.number_input('Wholesale price (w)',min_value=0.01,max_value=float(s.retail_price-.01),value=float(s.baseline_wholesale),step=.50)
with col2: b=st.number_input('Buy-back price (b)',min_value=0.0,max_value=float(max(.01,w-.01)),value=float(min(s.salvage_value+10,w-1)),step=.50)
with col3: q=st.number_input('Order quantity (Q)',min_value=1000,max_value=max(s.demand)+10000,value=int(s.baseline_q),step=250)
try:
    m=buyback_metrics(s,w,b,int(q))
except ValueError as e:
    st.error(str(e)); st.stop()

k1,k2,k3,k4=st.columns(4)
k1.metric('Expected units sold',f"{m['expected_sold']:,.1f}")
k2.metric('Expected returns',f"{m['expected_returns']:,.1f}")
k3.metric('Distributor expected profit',f"${m['distributor_profit']:,.2f}",delta=f"${m['distributor_profit']-base_profit:,.2f} vs baseline")
k4.metric('Estimated supplier profit',f"${intel_supplier_profit(s,w,b,int(q),'best'):,.2f}")
with st.expander('Supplier estimate sensitivity'):
    st.dataframe(pd.DataFrame({'Competitive-intelligence assumption':['Low cost estimate','Best estimate','High cost estimate'],'Estimated supplier profit':[intel_supplier_profit(s,w,b,int(q),'low'),intel_supplier_profit(s,w,b,int(q),'best'),intel_supplier_profit(s,w,b,int(q),'high')]}).style.format({'Estimated supplier profit':'${:,.2f}'}),hide_index=True,use_container_width=True)

st.divider(); st.subheader('Formal Negotiation')
round_no=len(st.session_state.history)+1
if st.session_state.closed:
    if st.session_state.accepted: st.success('Agreement reached. Complete the acknowledgment below and generate the contract.')
    else: st.error('Negotiation closed after 10 unsuccessful formal offers. The supplier has walked away.')
else:
    st.warning(f'Formal Offer {round_no} of 10. Once submitted, an offer cannot be edited.')
    prediction=st.radio('Before submitting, what do you expect the supplier to do?',['Likely Accept','Uncertain','Likely Reject'],horizontal=True,key=f'pred_{round_no}')
    if st.button('Submit Formal Offer',type='primary'):
        decision=evaluate_offer(s,w,b,int(q),round_no)
        offer={'offer_number':round_no,'wholesale':float(w),'buyback':float(b),'quantity':int(q)}
        prior=st.session_state.history.copy()
        response=supplier_response(s,offer,decision,prior)
        outcome='Accepted' if decision['accepted'] else ('Walked Away' if round_no>=10 else 'Rejected')
        record={**offer,'distributor_profit':decision['distributor_profit'],'prediction':prediction,'outcome':outcome,'supplier_response':response,
                'expected_sold':decision['expected_sold'],'expected_returns':decision['expected_returns']}
        st.session_state.history.append(record)
        if decision['accepted']:
            st.session_state.closed=True; st.session_state.accepted=True
        elif round_no>=10:
            st.session_state.closed=True
        st.rerun()

if st.session_state.history:
    st.markdown('### Negotiation Record')
    for h in reversed(st.session_state.history):
        with st.container(border=True):
            st.markdown(f"**Offer {h['offer_number']} - {h['outcome']}**  \nWholesale **${h['wholesale']:,.2f}** | Buy-back **${h['buyback']:,.2f}** | Q **{h['quantity']:,}**  \nYour expected distributor profit: **${h['distributor_profit']:,.2f}**")
            st.markdown(f"**Supplier:** {h['supplier_response']}")

if st.session_state.closed:
    st.divider(); st.subheader('Generate Submission PDF')
    final=st.session_state.history[-1] if st.session_state.history else None
    signature=''
    if st.session_state.accepted:
        signature=st.text_input('Distributor acknowledgment / signature',placeholder='Type your full name')
        st.caption('Typing your name acknowledges the simulated course contract. This is not a legal electronic signature.')
    if st.button('Generate Contract & Negotiation Report',type='primary',disabled=st.session_state.accepted and not signature.strip()):
        final_metrics=buyback_metrics(s,final['wholesale'],final['buyback'],final['quantity']) if final else {}
        pdf,rid=build_report(st.session_state.student_name,s,st.session_state.history,final,final_metrics,st.session_state.accepted,signature)
        filename=f"BAN517_BuyBack_{s.code}_{rid}.pdf"
        st.download_button('Download PDF for Canvas',pdf,file_name=filename,mime='application/pdf')
        st.caption('Submit this single PDF to Canvas. It contains the contract (if agreement was reached), negotiation record, and calculation addendum.')
