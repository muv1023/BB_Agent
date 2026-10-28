import io, hashlib
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

def _money(x): return f'${x:,.2f}'

def build_report(student_name, scenario, history, final_offer, final_metrics, accepted, student_signature):
    now=datetime.now().astimezone()
    payload=f"{student_name}|{scenario.code}|{now.isoformat()}|{len(history)}"
    report_id=hashlib.sha256(payload.encode()).hexdigest()[:12].upper()
    buf=io.BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=letter,rightMargin=.55*inch,leftMargin=.55*inch,topMargin=.55*inch,bottomMargin=.6*inch)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='T',parent=styles['Title'],textColor=colors.HexColor('#003b5c'),fontSize=18,alignment=TA_CENTER,spaceAfter=8))
    styles.add(ParagraphStyle(name='H',parent=styles['Heading2'],textColor=colors.HexColor('#003b5c'),fontSize=12,spaceBefore=10,spaceAfter=6))
    story=[Paragraph('BAN 517 Buy-Back Contract Negotiation',styles['T']),
           Paragraph('Course Simulation - Not a Legally Binding Commercial Agreement',styles['Normal']),Spacer(1,8)]
    status='AGREEMENT REACHED' if accepted else 'NO AGREEMENT - SUPPLIER WALKED AWAY'
    meta=[['Student',student_name],['Scenario',scenario.code],['Outcome',status],['Generated',now.strftime('%Y-%m-%d %I:%M %p %Z')],['Report ID',report_id]]
    t=Table(meta,colWidths=[1.5*inch,4.8*inch]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#eef7ff')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [t,Spacer(1,8)]
    if accepted and final_offer:
        story += [Paragraph('Executed Buy-Back Contract',styles['H'])]
        contract=[['Term','Agreed Value'],['Wholesale price',_money(final_offer['wholesale'])],['Buy-back price',_money(final_offer['buyback'])],['Order quantity',f"{final_offer['quantity']:,}"],['Retail selling price',_money(scenario.retail_price)],['Distributor acknowledgment',student_signature or student_name],['Manufacturer','Accepted by Supplier Negotiation Agent']]
        ct=Table(contract,colWidths=[2.2*inch,4.1*inch]); ct.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#003b5c')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.lightgrey),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold')]))
        story += [ct,Spacer(1,8),Paragraph('Contract Economics Available to the Distributor',styles['H'])]
        econ=[['Measure','Value'],['Expected units sold',f"{final_metrics['expected_sold']:,.1f}"],['Expected buy-back returns',f"{final_metrics['expected_returns']:,.1f}"],['Expected distributor profit',_money(final_metrics['distributor_profit'])]]
        et=Table(econ,colWidths=[3.1*inch,3.2*inch]); et.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#006c67')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)])); story += [et]
    story += [PageBreak(),Paragraph('Addendum A - Negotiation Record',styles['H'])]
    rows=[['Round','w','b','Q','Distributor Profit','Prediction','Supplier Outcome']]
    for h in history:
        rows.append([str(h['offer_number']),_money(h['wholesale']),_money(h['buyback']),f"{h['quantity']:,}",_money(h['distributor_profit']),h['prediction'],h['outcome']])
    nt=Table(rows,repeatRows=1,colWidths=[.45*inch,.7*inch,.7*inch,.75*inch,1.25*inch,1.05*inch,1.35*inch]); nt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#003b5c')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTSIZE',(0,0),(-1,-1),7),('GRID',(0,0),(-1,-1),.25,colors.lightgrey),('VALIGN',(0,0),(-1,-1),'TOP')]))
    story += [nt,PageBreak(),Paragraph('Addendum B - Final Calculation Record',styles['H'])]
    if final_offer:
        calc=[['Input / Calculation','Value'],['Retail price',_money(scenario.retail_price)],['Wholesale price',_money(final_offer['wholesale'])],['Buy-back price',_money(final_offer['buyback'])],['Order quantity',f"{final_offer['quantity']:,}"],['Expected units sold',f"{final_metrics['expected_sold']:,.2f}"],['Expected unsold / returned units',f"{final_metrics['expected_returns']:,.2f}"],['Expected distributor profit',_money(final_metrics['distributor_profit'])]]
        c=Table(calc,colWidths=[3.2*inch,3.1*inch]); c.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#006c67')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('GRID',(0,0),(-1,-1),.3,colors.lightgrey)])); story += [c]
    story += [Spacer(1,12),Paragraph('Private supplier costs, reservation profit, concession thresholds, and actual supplier expected profit are intentionally excluded from the student report.',styles['Normal'])]
    doc.build(story); buf.seek(0); return buf.getvalue(),report_id
