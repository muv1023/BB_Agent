"""
Supply Chain Analytics Inventory Decision Agent
Interactive Web Application powered by Streamlit.

Implements the 6-stage cognitive decision pipeline:
Customer Question -> Identify Model -> Extract Inputs -> Select Python Tool -> Calculate -> Verify -> Explain
"""

import math
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from inventory_agent import InventoryDecisionAgent
import inventory_tools

# Page Configuration
st.set_page_config(
    page_title="Supply Chain Analytics | Inventory Decision Agent",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .executive-card {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        color: #F8FAFC;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.15);
        border-left: 6px solid #3B82F6;
    }
    .stage-badge {
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 4px 10px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .badge-stage {
        background-color: #E2E8F0;
        color: #334155;
    }
    .badge-success {
        background-color: #DCFCE7;
        color: #166534;
    }
    .badge-alert {
        background-color: #FEF3C7;
        color: #92400E;
    }
    .metric-container {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Agent
if "agent" not in st.session_state:
    st.session_state.agent = InventoryDecisionAgent()

# Pre-loaded Business Scenarios
PRELOADED_SCENARIOS = {
    "1. Economic Order Quantity (EOQ)": (
        "We sell 1,200 units per year. Each order costs $50 to place and our inventory holding cost "
        "is $6 per unit per year. What is our optimal batch order size and total annual cost?"
    ),
    "2. Quantity Discount Model": (
        "Our annual demand is 10,000 units and ordering cost is $100 per purchase order. "
        "Carrying cost is 20% of unit cost. The supplier offers 3 tiers: 1 to 999 units at $10.00, "
        "1000 to 1999 units at $9.80, and 2000+ units at $9.60. Which price break minimizes total cost?"
    ),
    "3. Safety Stock & Reorder Point (Continuous)": (
        "Daily demand averages 100 units with a standard deviation of 20 units. Lead time is 9 days. "
        "What safety stock and reorder point do we need to maintain a 95% cycle service level?"
    ),
    "4. Fixed-Period Review (Periodic Order-Up-To)": (
        "We review inventory every 7 days. Supplier lead time is 3 days. Average demand is 20 units per day "
        "with standard deviation of 5 units. Service level target is 95%. Currently we have 50 units on hand "
        "and 20 on order with no backorders. How much should we order?"
    ),
    "5. Newsvendor Model (Single-Period Probabilistic)": (
        "We are buying seasonal winter jackets for $40 wholesale and selling them for $100 retail. "
        "Any leftover units at the end of the season can be salvaged for $10. Expected demand is normally distributed "
        "with a mean of 1,000 units and standard deviation of 200 units. What is our optimal stocking level?"
    ),
    "6. Classification: How many items in each class?": "How many items are in each class?",
    "7. Classification: Show all Class A items": "Show me all Class A items.",
    "8. Classification: Top 5 Class A items by Sales": "Show me the top 5 Class A items by Sales.",
    "9. Classification: Sales % by class": "What percentage of total sales is in each class?",
    "10. Classification: Why was an item classified as A, B, C, or D?": "Why was an item classified as A, B, C, or D?"
}

# Sidebar - Architecture & Quick Controls
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/warehouse.png", width=64)
    st.title("Inventory Agent")
    st.markdown("**Cognitive Decision Pipeline**")
    st.markdown("""
    `1. Question`  
    `↳ 2. Identify Model`  
    `↳ 3. Extract Inputs`  
    `↳ 4. Select Python Tool`  
    `↳ 5. Calculate (Deterministic)`  
    `↳ 6. Verify (Feasibility)`  
    `↳ 7. Explain (Managerial Brief)`
    """)

    st.divider()
    st.subheader("📚 Quick-Start Scenarios")
    selected_scenario = st.selectbox(
        "Choose a textbook scenario:",
        options=list(PRELOADED_SCENARIOS.keys()),
        index=0
    )
    if st.button("Load Scenario into Input", use_container_width=True):
        st.session_state.current_prompt = PRELOADED_SCENARIOS[selected_scenario]

    st.divider()
    st.caption("Supply Chain Analytics Decision Agent • BAN 517")


# Header
st.markdown('<div class="main-header">📦 Supply Chain Analytics: Inventory Decision Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-guided inventory modeling with deterministic Python calculations, physical feasibility verification, and managerial decision recommendations.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# CSV Data Upload & Inventory Portfolio Analysis Section
# -----------------------------------------------------------------------------
st.markdown("### 📁 Upload & Analyze Inventory Dataset (CSV)")
st.caption("Upload a CSV dataset to explore inventory records, compute portfolio summary statistics, and evaluate inventory valuation.")

uploaded_file = st.file_uploader("Upload an inventory CSV file:", type=["csv"], key="inventory_csv_uploader")

if uploaded_file is not None:
    # 1. Read the CSV into a pandas dataframe
    df = pd.read_csv(uploaded_file)

    # 3. Show the number of rows and columns
    num_rows, num_cols = df.shape

    # 4. Display the column names
    col_names = df.columns.tolist()

    st.markdown("#### 📋 Dataset Dimensions & Metadata")
    meta_c1, meta_c2, meta_c3 = st.columns([1, 1, 3])
    with meta_c1:
        st.metric("Number of Rows", f"{num_rows:,}")
    with meta_c2:
        st.metric("Number of Columns", f"{num_cols}")
    with meta_c3:
        st.markdown("**Column Names:**")
        st.write(", ".join([f"`{col}`" for col in col_names]))

    # 2. Display the uploaded data
    st.markdown("#### 📄 Uploaded Data Preview")
    st.dataframe(df, use_container_width=True)

    # Check for Multicriteria Inventory Classification columns (Sales and Hits)
    res_cols = inventory_tools.resolve_inventory_columns(df)
    has_sales_and_hits = (res_cols["sales"] is not None) and (res_cols["hits"] is not None)

    if has_sales_and_hits:
        with st.spinner("Executing Deterministic Multicriteria Inventory Classification (Sales & Hits Matrix)..."):
            classification_result = inventory_tools.classify_inventory_multicriteria(df)

        if classification_result.get("is_valid"):
            classified_df = classification_result["classified_df"]
            st.session_state.classified_df = classified_df
            summary_df = classification_result["summary_df"]

            st.markdown("#### 🏷️ Multicriteria Inventory Classification Results (A, B, C, D Classes)")
            st.caption("Classified using bi-criteria Pareto matrix: Financial Impact (Sales $) & Operational Velocity (Hits).")

            # 4 KPI Cards for Classes A, B, C, D
            k_cols = st.columns(4)
            class_colors = {"A": "#10B981", "B": "#3B82F6", "C": "#F59E0B", "D": "#64748B"}
            for col, c in zip(k_cols, ["A", "B", "C", "D"]):
                sub = summary_df[summary_df["Class"] == c].iloc[0]
                with col:
                    st.markdown(f"""
                    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-top: 4px solid {class_colors[c]}; border-radius: 8px; padding: 12px; text-align: center;">
                        <div style="font-size: 0.8rem; font-weight: 700; color: #475569;">CLASS {c}</div>
                        <div style="font-size: 1.3rem; font-weight: 800; color: #0F172A; margin: 4px 0;">{sub['Item Count']:,} items</div>
                        <div style="font-size: 0.75rem; color: #64748B;">{sub['% of Items']}% of SKUs • {sub['% of Total Sales']}% Sales</div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            col_tbl, col_cht = st.columns([3, 2])
            with col_tbl:
                st.markdown("##### 📊 Portfolio Classification Distribution Summary")
                st.dataframe(summary_df[["Class", "Item Count", "% of Items", "Total Sales ($)", "% of Total Sales", "Total Hits", "% of Total Hits"]], use_container_width=True)
            with col_cht:
                st.markdown("##### 📈 Items per Class")
                st.bar_chart(summary_df.set_index("Class")["Item Count"])

            # Full Classified Dataset with Calculated Columns & Rationales
            st.markdown("##### 📄 Classified Data Table (with A, B, C, D Classes & Rationale Rules)")
            disp_cols = [c for c in [res_cols["item_number"], res_cols["item_name"], res_cols["uom"], res_cols["sales"], res_cols["hits"], "Sales_Tier", "Hits_Tier", "Inventory Class", "Classification Reason"] if c and c in classified_df.columns]
            st.dataframe(classified_df[disp_cols] if disp_cols else classified_df, use_container_width=True)
    else:
        # Fallback to Units & Unit Cost analysis if available
        col_units = next((c for c in df.columns if c.strip().lower() in ["units", "unit"]), "Units" if "Units" in df.columns else None)
        col_cost = next((c for c in df.columns if c.strip().lower() in ["unit cost", "unitcost", "cost"]), "Unit Cost" if "Unit Cost" in df.columns else None)
        col_prod = next((c for c in df.columns if c.strip().lower() in ["product", "sku", "item"]), "Product" if "Product" in df.columns else None)
        col_cat = next((c for c in df.columns if c.strip().lower() in ["category", "cat"]), "Category" if "Category" in df.columns else None)

        if col_units and col_cost:
            df["Inventory Value"] = df[col_units] * df[col_cost]
            total_units = int(df[col_units].sum())
            avg_unit_cost = float(df[col_cost].mean())
            highest_units_idx = df[col_units].idxmax()
            highest_units_product = df.loc[highest_units_idx, col_prod] if col_prod else f"Row {highest_units_idx}"
            highest_units_val = df.loc[highest_units_idx, col_units]
            total_inv_value = float(df["Inventory Value"].sum())

            st.markdown("#### 📊 Inventory Analysis Metrics")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            with kpi1:
                st.metric("Total Units", f"{total_units:,}")
            with kpi2:
                st.metric("Average Unit Cost", f"${avg_unit_cost:,.2f}")
            with kpi3:
                st.metric("Highest Units Product", f"{highest_units_product}", f"{highest_units_val:,} units")
            with kpi4:
                st.metric("Total Inventory Value", f"${total_inv_value:,.2f}")

        if col_cat and col_units:
            st.markdown("#### 🏷️ Total Units by Category")
            category_summary = (
                df.groupby(col_cat, as_index=False)[col_units]
                .sum()
                .rename(columns={col_units: "Total Units"})
                .sort_values(by="Total Units", ascending=False)
            )
            cat_c1, cat_c2 = st.columns([2, 3])
            with cat_c1:
                st.dataframe(category_summary, use_container_width=True)
            with cat_c2:
                st.bar_chart(category_summary.set_index(col_cat)["Total Units"])

        if "Inventory Value" in df.columns:
            st.markdown("#### 💰 Data with Calculated Column: `Inventory Value = Units × Unit Cost`")
            st.dataframe(
                df.style.format({
                    col_cost: "${:,.2f}",
                    "Inventory Value": "${:,.2f}"
                }) if col_cost else df,
                use_container_width=True
            )

st.divider()

# Query Input Section
default_prompt = st.session_state.get("current_prompt", PRELOADED_SCENARIOS["1. Economic Order Quantity (EOQ)"])
user_query = st.text_area(
    "Enter your inventory or procurement question in natural language:",
    value=default_prompt,
    height=90,
    key="query_input"
)

col_btn1, col_btn2 = st.columns([1, 5])
with col_btn1:
    execute_clicked = st.button("⚡ Solve Inventory Problem", type="primary", use_container_width=True)
with col_btn2:
    if st.button("Clear / Reset", use_container_width=False):
        st.session_state.current_prompt = ""
        st.rerun()

if execute_clicked or user_query:
    agent = st.session_state.agent
    with st.spinner("Executing 6-Stage Inventory Decision Pipeline..."):
        report = agent.process_query(user_query, dataframe=st.session_state.get("classified_df"))

    s1 = report["stage_1_identify_model"]
    s2 = report["stage_2_extract_inputs"]
    s3 = report["stage_3_select_tool"]
    s4 = report["stage_4_calculate"]
    s5 = report["stage_5_verify"]
    s6 = report["stage_6_explain"]

    # Top-Level Executive Decision Card
    st.markdown(f"""
    <div class="executive-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="color: #60A5FA; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.85rem;">
                Executive Decision Recommendation
            </span>
            <span style="background: rgba(59, 130, 246, 0.2); color: #93C5FD; padding: 3px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600;">
                {s1['model_name']} • Conf: {int(s1['confidence']*100)}%
            </span>
        </div>
        <div style="font-size: 1.25rem; font-weight: 600; line-height: 1.4; color: #FFFFFF;">
            {s6['executive_takeaway']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Key Metrics Row
    if s6.get("key_metrics"):
        metric_cols = st.columns(len(s6["key_metrics"]))
        for col, (metric_label, metric_value) in zip(metric_cols, s6["key_metrics"].items()):
            with col:
                st.markdown(f"""
                <div class="metric-container">
                    <div style="font-size: 0.75rem; color: #64748B; font-weight: 600; text-transform: uppercase;">{metric_label}</div>
                    <div style="font-size: 1.15rem; color: #0F172A; font-weight: 700; margin-top: 4px;">{metric_value}</div>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Main Visual Tabs
    tab_pipeline, tab_charts, tab_whatif = st.tabs([
        "🔍 6-Stage Execution Pipeline",
        "📊 Model Analytics & Visualizations",
        "🎛️ 'What-If' Parameter Sensitivity"
    ])

    # --------------------------------------------------------------------------
    # TAB 1: 6-STAGE EXECUTION PIPELINE
    # --------------------------------------------------------------------------
    with tab_pipeline:
        st.markdown("### Step-by-Step Cognitive Decision Architecture")

        # Stage 1: Identify Model
        with st.expander("Stage 1: Identify Model", expanded=True):
            col_m1, col_m2 = st.columns([2, 3])
            with col_m1:
                st.markdown(f"**Identified Model:** `{s1['model_name']}`")
                st.markdown(f"**Classification Confidence:** `{s1['confidence']*100:.0f}%`")
                st.progress(float(s1['confidence']))
            with col_m2:
                st.markdown("**Classification Rationales:**")
                for r in s1["rationales"]:
                    st.markdown(f"- {r}")

        # Stage 2: Extract Inputs
        with st.expander("Stage 2: Extract Inputs", expanded=True):
            col_i1, col_i2 = st.columns([3, 2])
            with col_i1:
                st.markdown("**Extracted Parameters:**")
                st.json(s2["extracted_parameters"])
            with col_i2:
                if s2["missing_parameters"]:
                    st.warning(f"⚠️ **Missing Parameters:** {', '.join(s2['missing_parameters'])}")
                else:
                    st.success("✅ **All essential parameters extracted.**")
                if s2["parsing_notes"]:
                    st.markdown("**Parsing Notes:**")
                    for note in s2["parsing_notes"]:
                        st.caption(f"• {note}")

        # Stage 3: Select Python Tool
        with st.expander("Stage 3: Select Python Tool", expanded=False):
            st.markdown(f"**Selected Tool Function:** `inventory_tools.{s3['tool_function_name']}`")
            st.code(f"def {s3['tool_function_name']}(**parameters):\n    \"\"\"{s3['docstring']}\"\"\"", language="python")

        # Stage 4: Calculate
        with st.expander("Stage 4: Calculate (Deterministic Python Execution & Analyst Verification Audit)", expanded=True):
            if s4.get("is_valid", False):
                if s4.get("display_table") is not None:
                    st.markdown("#### 📋 Query Result Table (Direct pandas Calculation)")
                    st.dataframe(s4["display_table"], use_container_width=True)
                    st.divider()

                if s4.get("step_by_step_audit"):
                    st.markdown("#### 🔬 Step-by-Step Analyst Verification Audit (Direct Python Output)")
                    st.markdown(s4["step_by_step_audit"])
                    st.divider()

                col_c1, col_c2 = st.columns([1, 1])
                with col_c1:
                    st.markdown("**Variable Definitions:**")
                    st.json(s4.get("variable_definitions", {}))
                    st.markdown("**Formulas with Substituted Values:**")
                    st.json(s4.get("formula_with_substituted_values", {}))
                    st.markdown("**Underlying Model Assumptions:**")
                    for asm in s4.get("assumptions", []):
                        st.markdown(f"- 📌 {asm}")
                with col_c2:
                    st.markdown("**Intermediate Calculation Breakdown:**")
                    st.json(s4.get("intermediate_calculation", {}))
                    st.markdown("**Final Decision Metrics:**")
                    st.json(s4.get("final_answer", {}))
            else:
                st.error(f"❌ Calculation Failed: {', '.join(s4.get('errors', []))}")

        # Stage 5: Verify
        with st.expander("Stage 5: Verify (Physical Feasibility & Economics)", expanded=True):
            v_status = s5["verification_status"]
            if v_status == "PASSED":
                st.success(f"✅ **Verification Status: {v_status}**")
            else:
                st.error(f"❌ **Verification Status: {v_status}**")

            col_v1, col_v2 = st.columns(2)
            with col_v1:
                st.markdown("**Passed Validation Checks:**")
                for chk in s5.get("passed_checks", []):
                    st.markdown(f"- ✅ {chk}")
            with col_v2:
                if s5.get("warnings"):
                    st.markdown("**Operational Warnings:**")
                    for w in s5["warnings"]:
                        st.markdown(f"- ⚠️ {w}")
                if s5.get("failed_checks"):
                    st.markdown("**Failed Boundary Checks:**")
                    for f in s5["failed_checks"]:
                        st.markdown(f"- ❌ {f}")

        # Stage 6: Explain
        with st.expander("Stage 6: Explain (Managerial Decision Brief)", expanded=True):
            st.markdown(f"**Executive Summary:** {s6['executive_takeaway']}")
            st.markdown("#### Strategic Guidance & Managerial Trade-offs:")
            for adv in s6.get("managerial_advice", []):
                st.markdown(f"- {adv}")

    # --------------------------------------------------------------------------
    # TAB 2: MODEL ANALYTICS & VISUALIZATIONS
    # --------------------------------------------------------------------------
    with tab_charts:
        st.markdown("### Visual Supply Chain Trade-Off Analysis")
        model_key = s1["model_key"]

        if model_key == "eoq" and s4.get("is_valid"):
            inputs = s2["extracted_parameters"]
            D = inputs["annual_demand"]
            S = inputs["order_cost"]
            H = inputs["holding_cost"]
            q_opt = s4["results"]["optimal_order_quantity"]

            q_vals = np.linspace(max(10, q_opt * 0.2), q_opt * 2.5, 200)
            holding_costs = (q_vals / 2.0) * H
            ordering_costs = (D / q_vals) * S
            total_costs = holding_costs + ordering_costs

            fig, ax = plt.subplots(figsize=(9, 4.5), dpi=100)
            ax.plot(q_vals, ordering_costs, label="Annual Ordering Cost (D/Q * S)", color="#EF4444", linestyle="--", linewidth=1.8)
            ax.plot(q_vals, holding_costs, label="Annual Holding Cost (Q/2 * H)", color="#3B82F6", linestyle="--", linewidth=1.8)
            ax.plot(q_vals, total_costs, label="Total Variable Cost", color="#0F172A", linewidth=2.4)
            ax.axvline(q_opt, color="#10B981", linestyle=":", linewidth=2, label=f"Optimal EOQ (Q* = {q_opt:.1f})")
            ax.scatter([q_opt], [s4['results']['total_variable_cost']], color="#10B981", s=80, zorder=5)

            ax.set_title("EOQ Cost Trade-off: Holding vs. Ordering Costs", fontsize=12, fontweight="bold")
            ax.set_xlabel("Order Quantity (Q)")
            ax.set_ylabel("Annual Cost ($)")
            ax.grid(True, linestyle=":", alpha=0.6)
            ax.legend(frameon=True)
            st.pyplot(fig)

        elif model_key == "quantity_discount" and s4.get("is_valid"):
            tiers_data = s4["tiers_evaluated"]
            df_tiers = pd.DataFrame(tiers_data)
            st.markdown("#### All-Units Discount Schedule Comparison")
            st.dataframe(
                df_tiers[[
                    "tier_index", "min_qty", "max_qty", "unit_cost",
                    "evaluated_order_quantity", "decision_rule",
                    "annual_order_cost", "annual_holding_cost", "annual_purchase_cost", "total_annual_cost"
                ]].rename(columns={
                    "tier_index": "Tier #",
                    "min_qty": "Min Qty",
                    "max_qty": "Max Qty",
                    "unit_cost": "Price ($)",
                    "evaluated_order_quantity": "Evaluated Q",
                    "decision_rule": "Rule",
                    "annual_order_cost": "Order Cost ($)",
                    "annual_holding_cost": "Holding Cost ($)",
                    "annual_purchase_cost": "Purchase Cost ($)",
                    "total_annual_cost": "Total Cost ($)"
                }),
                use_container_width=True
            )

            fig, ax = plt.subplots(figsize=(8, 4), dpi=100)
            bars = ax.bar(
                [f"Tier #{t['tier_index']} (${t['unit_cost']:.2f})" for t in tiers_data],
                [t["total_annual_cost"] for t in tiers_data],
                color=["#10B981" if t["tier_index"] == s4["results"]["optimal_tier_index"] else "#94A3B8" for t in tiers_data],
                width=0.45
            )
            ax.set_title("Total Annual Cost across Discount Tiers", fontsize=12, fontweight="bold")
            ax.set_ylabel("Total Annual Cost ($)")
            for bar in bars:
                h = bar.get_height()
                ax.annotate(f"${h:,.0f}", (bar.get_x() + bar.get_width() / 2, h),
                            ha="center", va="bottom", fontsize=9, fontweight="bold")
            ax.grid(axis="y", linestyle=":", alpha=0.5)
            st.pyplot(fig)

        elif model_key == "safety_stock_rop" and s4.get("is_valid"):
            mean_d = s4["results"]["expected_lead_time_demand"]
            sigma_dl = max(1.0, s4["results"]["lead_time_std_dev"])
            rop = s4["results"]["reorder_point"]
            ss = s4["results"]["safety_stock"]

            x = np.linspace(max(0, mean_d - 4 * sigma_dl), mean_d + 4 * sigma_dl, 300)
            y = (1.0 / (sigma_dl * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean_d) / sigma_dl) ** 2)

            fig, ax = plt.subplots(figsize=(9, 4.5), dpi=100)
            ax.plot(x, y, label="Lead Time Demand Distribution", color="#3B82F6", linewidth=2)
            ax.fill_between(x, 0, y, where=(x <= rop), color="#3B82F6", alpha=0.25, label=f"Cycle Service Level ({s2['extracted_parameters']['service_level']*100:.1f}%)")
            ax.axvline(mean_d, color="#64748B", linestyle="--", label=f"Mean Demand during Lead Time ({mean_d:.1f})")
            ax.axvline(rop, color="#EF4444", linestyle="-", linewidth=2, label=f"Reorder Point ROP ({rop:.1f})")
            ax.axvspan(mean_d, rop, color="#FEF3C7", alpha=0.5, label=f"Safety Stock Buffer (SS = {ss:.1f})")

            ax.set_title("Lead Time Demand Distribution & Reorder Point (ROP)", fontsize=12, fontweight="bold")
            ax.set_xlabel("Lead Time Demand (units)")
            ax.set_ylabel("Probability Density")
            ax.legend(frameon=True, fontsize=9)
            ax.grid(True, linestyle=":", alpha=0.5)
            st.pyplot(fig)

        elif model_key == "newsvendor" and s4.get("is_valid"):
            mean_d = s2["extracted_parameters"]["demand_mean"]
            sigma_d = max(1.0, s2["extracted_parameters"]["demand_std"])
            q_opt = s4["results"]["optimal_order_quantity"]
            cr = s4["results"]["critical_ratio"]

            x = np.linspace(max(0, mean_d - 3.5 * sigma_d), mean_d + 3.5 * sigma_d, 300)
            y = (1.0 / (sigma_d * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - mean_d) / sigma_d) ** 2)

            fig, ax = plt.subplots(figsize=(9, 4.5), dpi=100)
            ax.plot(x, y, label="Seasonal Demand Distribution", color="#6366F1", linewidth=2)
            ax.fill_between(x, 0, y, where=(x <= q_opt), color="#6366F1", alpha=0.25, label=f"Non-Stockout Area (CR = {cr*100:.1f}%)")
            ax.axvline(mean_d, color="#64748B", linestyle="--", label=f"Mean Demand ({mean_d:,.0f})")
            ax.axvline(q_opt, color="#10B981", linestyle="-", linewidth=2.2, label=f"Optimal Stocking Q* ({q_opt:,.0f})")

            ax.set_title("Newsvendor Critical Fractile & Optimal Order Quantity", fontsize=12, fontweight="bold")
            ax.set_xlabel("Demand (units)")
            ax.set_ylabel("Probability Density")
            ax.legend(frameon=True, fontsize=9)
            ax.grid(True, linestyle=":", alpha=0.5)
            st.pyplot(fig)

        elif model_key == "inventory_classification" and s4.get("is_valid"):
            st.markdown("#### 📊 Multicriteria Inventory Portfolio Visualizations")
            c_df = st.session_state.get("classified_df")
            if c_df is not None:
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2), dpi=100)
                class_counts = c_df["Inventory Class"].value_counts().reindex(["A", "B", "C", "D"]).fillna(0)
                colors = ["#10B981", "#3B82F6", "#F59E0B", "#94A3B8"]

                ax1.bar(class_counts.index, class_counts.values, color=colors, width=0.5)
                ax1.set_title("SKU Count by Class", fontsize=11, fontweight="bold")
                ax1.set_ylabel("Number of SKUs")
                ax1.grid(axis="y", linestyle=":", alpha=0.5)
                for i, v in enumerate(class_counts.values):
                    ax1.annotate(f"{int(v)}", (i, v), ha="center", va="bottom", fontsize=9, fontweight="bold")

                sales_col = next((c for c in c_df.columns if "sales" in c.lower()), None)
                if sales_col:
                    sales_by_c = c_df.groupby("Inventory Class")[sales_col].sum().reindex(["A", "B", "C", "D"]).fillna(0)
                    ax2.bar(sales_by_c.index, sales_by_c.values, color=colors, width=0.5)
                    ax2.set_title("Total Sales ($) by Class", fontsize=11, fontweight="bold")
                    ax2.set_ylabel("Sales ($)")
                    ax2.grid(axis="y", linestyle=":", alpha=0.5)
                    for i, v in enumerate(sales_by_c.values):
                        ax2.annotate(f"${v:,.0f}", (i, v), ha="center", va="bottom", fontsize=8, fontweight="bold")

                plt.tight_layout()
                st.pyplot(fig)
            if s4.get("display_table") is not None:
                st.markdown("##### 📋 Filtered Query Data Table")
                st.dataframe(s4["display_table"], use_container_width=True)

        else:
            st.info("Visualizations available for EOQ, Quantity Discount, Safety Stock/ROP, Newsvendor, and Inventory Classification.")

    # --------------------------------------------------------------------------
    # TAB 3: "WHAT-IF" SENSITIVITY SIMULATOR
    # --------------------------------------------------------------------------
    with tab_whatif:
        st.markdown("### Dynamic 'What-If' Parameter Sensitivity")
        st.caption("Interactively adjust key parameters to evaluate real-time supply chain impacts.")

        model_key = s1["model_key"]
        inputs = s2["extracted_parameters"]

        if model_key == "eoq" and s4.get("is_valid"):
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                new_demand = st.slider("Annual Demand (units)", min_value=100, max_value=int(inputs["annual_demand"] * 3), value=int(inputs["annual_demand"]), step=50)
            with col_w2:
                new_order_cost = st.slider("Order Setup Cost ($)", min_value=5.0, max_value=float(inputs["order_cost"] * 3), value=float(inputs["order_cost"]), step=5.0)
            with col_w3:
                new_h = st.slider("Holding Cost ($/unit/yr)", min_value=0.5, max_value=float(inputs["holding_cost"] * 3), value=float(inputs["holding_cost"]), step=0.5)

            sim_res = inventory_tools.calculate_eoq(annual_demand=new_demand, order_cost=new_order_cost, holding_cost=new_h)
            st.metric(
                label="Simulated Optimal Batch Size (Q*)",
                value=f"{sim_res['results']['optimal_order_quantity']:,.1f} units",
                delta=f"{sim_res['results']['optimal_order_quantity'] - s4['results']['optimal_order_quantity']:+.1f} units vs baseline"
            )
            st.metric(
                label="Simulated Total Variable Cost",
                value=f"${sim_res['results']['total_variable_cost']:,.2f}",
                delta=f"${sim_res['results']['total_variable_cost'] - s4['results']['total_variable_cost']:+,.2f} vs baseline"
            )

        elif model_key == "safety_stock_rop" and s4.get("is_valid"):
            col_w1, col_w2, col_w3 = st.columns(3)
            with col_w1:
                new_sl = st.slider("Target Service Level", min_value=0.80, max_value=0.999, value=float(inputs["service_level"]), step=0.01, format="%.2f")
            with col_w2:
                new_lt = st.slider("Lead Time (days)", min_value=1, max_value=int(inputs["lead_time_periods"] * 3), value=int(inputs["lead_time_periods"]))
            with col_w3:
                new_std_d = st.slider("Demand Std Dev", min_value=0.0, max_value=float(inputs["std_demand_per_period"] * 3 + 1.0), value=float(inputs["std_demand_per_period"]), step=1.0)

            sim_rop = inventory_tools.calculate_safety_stock_rop(
                avg_demand_per_period=inputs["avg_demand_per_period"],
                lead_time_periods=new_lt,
                service_level=new_sl,
                std_demand_per_period=new_std_d,
                std_lead_time_periods=inputs.get("std_lead_time_periods", 0.0)
            )
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric(
                    label="Simulated Safety Stock",
                    value=f"{sim_rop['results']['safety_stock']:,.1f} units",
                    delta=f"{sim_rop['results']['safety_stock'] - s4['results']['safety_stock']:+.1f} units"
                )
            with col_m2:
                st.metric(
                    label="Simulated Reorder Point (ROP)",
                    value=f"{sim_rop['results']['reorder_point']:,.1f} units",
                    delta=f"{sim_rop['results']['reorder_point'] - s4['results']['reorder_point']:+.1f} units"
                )

        elif model_key == "newsvendor" and s4.get("is_valid"):
            col_w1, col_w2 = st.columns(2)
            with col_w1:
                new_salvage = st.slider("Salvage Value ($/unit)", min_value=0.0, max_value=float(inputs["unit_cost"] - 1.0), value=float(inputs.get("salvage_value", 0.0)), step=2.0)
            with col_w2:
                new_std = st.slider("Demand Std Dev (Uncertainty)", min_value=10.0, max_value=float(inputs["demand_std"] * 2.5), value=float(inputs["demand_std"]), step=10.0)

            sim_nv = inventory_tools.calculate_newsvendor(
                selling_price=inputs["selling_price"],
                unit_cost=inputs["unit_cost"],
                salvage_value=new_salvage,
                demand_mean=inputs["demand_mean"],
                demand_std=new_std
            )
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric(
                    label="Simulated Stocking Level (Q*)",
                    value=f"{sim_nv['results']['optimal_order_quantity']:,.0f} units",
                    delta=f"{sim_nv['results']['optimal_order_quantity'] - s4['results']['optimal_order_quantity']:+.0f} units"
                )
            with col_m2:
                st.metric(
                    label="Simulated Expected Profit",
                    value=f"${sim_nv['results']['expected_profit']:,.2f}",
                    delta=f"${sim_nv['results']['expected_profit'] - s4['results']['expected_profit']:+,.2f}"
                )
        else:
            st.info("Interactive sensitivity adjusters are active for calculated models.")
