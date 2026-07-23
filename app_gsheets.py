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
st.title("📊 نظام إدارة مبيعات الفروع (سحابي)")

menu = ["إدخال البيانات", "لوحة التحكم (Dashboard)"]
choice = st.sidebar.radio("اختر الشاشة:", menu)

if choice == "إدخال البيانات":
    st.header("📝 إدخال مبيعات يومية جديدة")
    
    with st.form(key='sales_form'):
        # اختيار التاريخ والفرع في الأعلى
        col_date, col_branch = st.columns(2)
        with col_date:
            date_input = st.date_input("التاريخ", date.today())
        with col_branch:
            branch = st.selectbox("الفرع", ["Shubra", "Sohag", "RS store 2", "RS store"])
            
        st.markdown("---")
        st.markdown("### بيانات التصنيفات")
        
        # إنشاء عناوين للأعمدة
        h1, h2, h3, h4 = st.columns([2, 2, 2, 3])
        h1.markdown("**التصنيف**")
        h2.markdown("**العدد (صافي)**")
        h3.markdown("**القيمة (جنيه)**")
        h4.markdown("**ملاحظات (اختياري)**")
        
        categories = ["موبايل", "اكسسوار", "شاشات", "أجهزة منزلية"]
        inputs = {}
        
        # إنشاء صفوف الإدخال لكل تصنيف بشكل منظم
        for cat in categories:
            c1, c2, c3, c4 = st.columns([2, 2, 2, 3])
            
            with c1:
                st.write("") # لضبط المحاذاة الرأسية
                st.markdown(f"**{cat}**")
                
            with c2:
                qty = st.number_input(f"العدد", min_value=0, step=1, key=f"qty_{cat}", label_visibility="collapsed")
                
            with c3:
                val = st.number_input(f"القيمة", min_value=0.0, step=10.0, key=f"val_{cat}", label_visibility="collapsed")
                
            with c4:
                notes = st.text_input(f"ملاحظات", key=f"notes_{cat}", label_visibility="collapsed", placeholder="مثال: بعد مرتجع 1")
                
            inputs[cat] = {"qty": qty, "val": val, "notes": notes}
            
        st.markdown("---")
        submit_button = st.form_submit_button(label='💾 حفظ بيانات الفرع بالكامل')
        
        if submit_button:
            rows_to_add = []
            for cat, data in inputs.items():
                # سيتم حفظ التصنيف فقط إذا كان العدد أو القيمة أكبر من صفر
                if data["qty"] > 0 or data["val"] > 0:
                    rows_to_add.append([str(date_input), branch, cat, data["qty"], data["val"], data["notes"]])
            
            if rows_to_add:
                # إضافة كل الصفوف مرة واحدة لجوجل شيت
                worksheet.append_rows(rows_to_add)
                st.success(f"✅ تم حفظ بيانات فرع {branch} بنجاح!")
            else:
                st.warning("⚠️ لم تقم بإدخال أي مبيعات للحفظ. تأكد من كتابة العدد والقيمة أولاً.")

elif choice == "لوحة التحكم (Dashboard)":
    st.header("📈 تقرير المبيعات المجمع")
    
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        try:
            df['التاريخ'] = pd.to_datetime(df['التاريخ']).dt.date
            df['العدد'] = pd.to_numeric(df['العدد'])
            df['القيمة'] = pd.to_numeric(df['القيمة'])
            
            total_qty = df['العدد'].sum()
            total_val = df['القيمة'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("إجمالي القطع المباعة", f"{total_qty} قطعة")
            col2.metric("إجمالي المبيعات", f"{total_val:,.2f} جنيه")
            col3.metric("عدد الفروع المسجلة", df['الفرع'].nunique())
            
            st.markdown("---")
            
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.subheader("المبيعات حسب الفرع")
                branch_sales = df.groupby('الفرع')['القيمة'].sum().reset_index()
                fig_branch = px.bar(branch_sales, x='الفرع', y='القيمة', color='الفرع', title="إجمالي القيمة لكل فرع")
                st.plotly_chart(fig_branch, use_container_width=True)
                
            with chart_col2:
                st.subheader("المبيعات حسب التصنيف")
                cat_sales = df.groupby('التصنيف')['العدد'].sum().reset_index()
                fig_cat = px.pie(cat_sales, values='العدد', names='التصنيف', title="توزيع القطع المباعة")
                st.plotly_chart(fig_cat, use_container_width=True)
                
            st.markdown("---")
            st.subheader("📋 سجل البيانات التفصيلي")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning("البيانات موجودة ولكن يبدو أن عناوين الأعمدة في جوجل شيت غير متطابقة.")
            
    else:
        st.info("لا توجد بيانات مسجلة حتى الآن.")
