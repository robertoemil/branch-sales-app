
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
# استدعاء بيانات الاعتماد (الرقم السري) من إعدادات Streamlit
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
        col1, col2 = st.columns(2)
        
        with col1:
            date_input = st.date_input("التاريخ", date.today())
            branch = st.selectbox("الفرع", ["Shubra", "Sohag", "RS store 2", "RS store"])
            category = st.selectbox("التصنيف", ["موبايل", "اكسسوار", "شاشات", "أجهزة منزلية"])
            
        with col2:
            quantity = st.number_input("العدد (صافي)", min_value=0, step=1)
            value = st.number_input("القيمة (جنيه)", min_value=0.0, step=10.0)
            notes = st.text_input("ملاحظات (اختياري - مثل: مرتجع 1)")
            
        submit_button = st.form_submit_button(label='💾 حفظ البيانات')
        
        if submit_button:
            # تحويل البيانات إلى صف جديد وإرساله لجوجل شيت
            row_data = [str(date_input), branch, category, quantity, value, notes]
            worksheet.append_row(row_data)
            st.success("✅ تم حفظ البيانات بنجاح في Google Sheets!")

elif choice == "لوحة التحكم (Dashboard)":
    st.header("📈 تقرير المبيعات المجمع")
    
    # جلب البيانات من جوجل شيت
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    
    if not df.empty:
        # التأكد من أسماء الأعمدة (يجب أن تكون في أول صف في جوجل شيت)
        try:
            df['التاريخ'] = pd.to_datetime(df['التاريخ']).dt.date
            # التأكد من أن الأرقام تقرأ بشكل صحيح
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
            st.warning("البيانات موجودة ولكن يبدو أن عناوين الأعمدة في جوجل شيت غير متطابقة. تأكد من أن الصف الأول يحتوي على: التاريخ | الفرع | التصنيف | العدد | القيمة | ملاحظات")
            
    else:
        st.info("لا توجد بيانات مسجلة حتى الآن. يرجى إدخال البيانات من الشاشة الأخرى.")
