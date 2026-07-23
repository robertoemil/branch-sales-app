import streamlit as st
import pandas as pd
from datetime import date
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

# ----------------- إعدادات الصفحة -----------------
st.set_page_config(page_title="نظام مبيعات الفروع", layout="wide")

st.markdown('''
    <style>
        body, .stApp {
            direction: rtl;
            text-align: right;
            font-family: 'Cairo', sans-serif;
        }
    </style>
''', unsafe_allow_html=True)

# ----------------- الاتصال بجوجل شيت -----------------
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
try:
    skey = st.secrets["gcp_service_account"]
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    gc = gspread.authorize(credentials)
    
    sheet_url = st.secrets["sheet_url"]
    sh = gc.open_by_url(sheet_url)
    worksheet = sh.sheet1
except Exception as e:
    st.error("خطأ في الاتصال بقاعدة البيانات (جوجل شيت). تأكد من إعدادات الـ Secrets.")
    st.stop()

# ----------------- واجهة المستخدم -----------------
st.title("📊 نظام إدارة وتحليل المبيعات (سحابي)")

menu = ["إدخال البيانات", "لوحة التحكم والتحليلات"]
choice = st.sidebar.radio("اختر الشاشة:", menu)

if choice == "إدخال البيانات":
    st.header("📝 إدخال مبيعات يومية جديدة")
    
    with st.form(key='sales_form'):
        col_date, col_branch = st.columns(2)
        with col_date:
            date_input = st.date_input("التاريخ", date.today())
        with col_branch:
            branch = st.selectbox("الفرع", ["Shubra", "Sohag", "RS store 2", "RS store"])
            
        st.markdown("---")
        st.markdown("### بيانات التصنيفات")
        
        h1, h2, h3, h4 = st.columns([2, 2, 2, 3])
        h1.markdown("**التصنيف**")
        h2.markdown("**العدد (صافي)**")
        h3.markdown("**القيمة (جنيه)**")
        h4.markdown("**ملاحظات (اختياري)**")
        
        categories = ["موبايل", "اكسسوار", "شاشات", "أجهزة منزلية"]
        inputs = {}
        
        for cat in categories:
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            
            with c1:
                st.write("") 
                st.markdown(f"**{cat}**")
                
            with c2:
                qty = st.number_input(f"العدد", min_value=0, step=1, key=f"qty_{cat}", label_visibility="collapsed")
                
            with c3:
                val = st.number_input(f"القيمة", min_value=0.0, step=10.0, key=f"val_{cat}", label_visibility="collapsed")
                
            with c4:
                notes = st.text_input(f"ملاحظات", key=f"notes_{cat}", label_visibility="collapsed", placeholder="مثال: بعد مرتجع 1")
                
            inputs[cat] = {"qty": qty, "val": val, "notes": notes}
            
        st.markdown("---")
        st.markdown("### 📢 مصروفات الإعلانات اليومية (اختياري)")
        st.info("هذا الحقل يُسجل ميزانية الإعلانات لليوم بأكمله ولا يرتبط بفرع معين.")
        ad_spend = st.number_input("إجمالي صرف الإعلانات لليوم (جنيه)", min_value=0.0, step=10.0)

        submit_button = st.form_submit_button(label='💾 حفظ البيانات')
        
        if submit_button:
            rows_to_add = []
            
            for cat, data in inputs.items():
                if data["qty"] > 0 or data["val"] > 0:
                    rows_to_add.append([str(date_input), branch, cat, data["qty"], data["val"], data["notes"]])
            
            if ad_spend > 0:
                rows_to_add.append([str(date_input), "المركز الرئيسي", "صرف إعلانات", 0, ad_spend, "ميزانية الإعلانات لليوم"])
            
            if rows_to_add:
                worksheet.append_rows(rows_to_add)
                st.success("✅ تم حفظ البيانات بنجاح!")
            else:
                st.warning("⚠️ لم تقم بإدخال أي بيانات للحفظ.")

elif choice == "لوحة التحكم والتحليلات":
    st.header("📈 تقارير وتحليل المبيعات")
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        try:
            df['التاريخ'] = pd.to_datetime(df['التاريخ']).dt.date
            df['العدد'] = pd.to_numeric(df['العدد'])
            df['القيمة'] = pd.to_numeric(df['القيمة'])
            
            # --- فلترة البيانات ---
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 📅 فلترة التقارير")
            min_date = df['التاريخ'].min()
            max_date = df['التاريخ'].max()
            
            # التأكد من اختيار تاريخين
            date_range = st.sidebar.date_input("اختر نطاق التاريخ", [min_date, max_date])
            if len(date_range) == 2:
                start_date, end_date = date_range
            else:
                start_date, end_date = min_date, max_date
                
            # تطبيق الفلتر
            mask = (df['التاريخ'] >= start_date) & (df['التاريخ'] <= end_date)
            filtered_df = df.loc[mask]
            
            sales_df = filtered_df[filtered_df['التصنيف'] != 'صرف إعلانات']
            ads_df = filtered_df[filtered_df['التصنيف'] == 'صرف إعلانات']
            
            # --- المؤشرات الرئيسية (KPIs) ---
            total_qty = sales_df['العدد'].sum()
            total_val = sales_df['القيمة'].sum()
            total_ads = ads_df['القيمة'].sum()
            
            # حساب العائد على الإعلانات (ROAS)
            roas = (total_val / total_ads) if total_ads > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 إجمالي المبيعات", f"{total_val:,.0f} ج")
            col2.metric("📦 إجمالي القطع", f"{total_qty}")
            col3.metric("📢 صرف الإعلانات", f"{total_ads:,.0f} ج")
            col4.metric("🚀 العائد على الإعلانات", f"{roas:,.1f} ضعف" if roas > 0 else "بدون إعلانات")
            
            st.markdown("---")
            
            # --- نظام التبويبات (Tabs) لتنظيم التحليلات ---
            tab1, tab2, tab3 = st.tabs(["📊 ملخص الأداء", "📈 تحليل الاتجاهات (زمني)", "🏢 مقارنة وتقييم الفروع"])
            
            with tab1: # ملخص الأداء
                c1, c2 = st.columns(2)
                with c1:
                    branch_sales = sales_df.groupby('الفرع')['القيمة'].sum().reset_index().sort_values(by='القيمة', ascending=False)
                    fig_branch = px.bar(branch_sales, x='الفرع', y='القيمة', color='الفرع', title="المبيعات حسب الفرع", text_auto='.2s')
                    st.plotly_chart(fig_branch, use_container_width=True)
                with c2:
                    cat_sales = sales_df.groupby('التصنيف')['القيمة'].sum().reset_index()
                    fig_cat = px.pie(cat_sales, values='القيمة', names='التصنيف', title="إيرادات المبيعات حسب التصنيف", hole=0.4)
                    st.plotly_chart(fig_cat, use_container_width=True)
            
            with tab2: # تحليل الاتجاهات
                st.markdown("### تطور المبيعات اليومية")
                daily_sales = sales_df.groupby('التاريخ')['القيمة'].sum().reset_index()
                fig_trend = px.line(daily_sales, x='التاريخ', y='القيمة', markers=True, title="منحنى المبيعات الإجمالية")
                st.plotly_chart(fig_trend, use_container_width=True)
                
                daily_ads = ads_df.groupby('التاريخ')['القيمة'].sum().reset_index()
                if not daily_ads.empty:
                    fig_ads = px.bar(daily_ads, x='التاريخ', y='القيمة', title="صرف الإعلانات اليومي", color_discrete_sequence=['#ff9999'])
                    st.plotly_chart(fig_ads, use_container_width=True)

            with tab3: # مقارنة الفروع (Pivot Table)
                st.markdown("### تحليل مبيعات الفروع حسب التصنيف (القيمة بالجنيه)")
                # عمل جدول محوري (Pivot Table)
                pivot_val = pd.pivot_table(sales_df, values='القيمة', index='الفرع', columns='التصنيف', aggfunc='sum', fill_value=0)
                pivot_val['إجمالي الفرع'] = pivot_val.sum(axis=1)
                st.dataframe(pivot_val.style.format("{:,.0f}").background_gradient(cmap='Blues', subset=['إجمالي الفرع']), use_container_width=True)
                
                st.markdown("### تحليل أعداد القطع المباعة")
                pivot_qty = pd.pivot_table(sales_df, values='العدد', index='الفرع', columns='التصنيف', aggfunc='sum', fill_value=0)
                pivot_qty['إجمالي القطع'] = pivot_qty.sum(axis=1)
                st.dataframe(pivot_qty.style.format("{:,.0f}").background_gradient(cmap='Greens', subset=['إجمالي القطع']), use_container_width=True)
                
            st.markdown("---")
            with st.expander("🔎 عرض جميع البيانات المسجلة (للمراجعة)"):
                st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.warning("البيانات موجودة ولكن يبدو أن هناك خطأ في قراءة بعض الأرقام أو التواريخ من الشيت.")
            
    else:
        st.info("لا توجد بيانات مسجلة حتى الآن.")
