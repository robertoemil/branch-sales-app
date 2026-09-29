import streamlit as st
import pandas as pd
import numpy as np
from datetime import date, timedelta
import re
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from sklearn.linear_model import LinearRegression

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
    st.header("📝 إدخال المبيعات اليومية")
    
    tab_smart, tab_manual = st.tabs(["🚀 إدخال سريع (لصق الرسالة)", "✍️ إدخال يدوي"])
    
    # ----------------- 1. الإدخال السريع -----------------
    with tab_smart:
        st.markdown("### 📋 انسخ والصق رسالة الواتساب هنا")
        st.info("السيستم سيقرأ الرسالة تلقائياً ويستخرج منها التاريخ، الفروع، والمبيعات (وسيتم تجاهل الإجماليات).")
        
        pasted_text = st.text_area("رسالة تقرير المبيعات:", height=300, placeholder="قم بلصق تقرير المبيعات هنا...")
        
        st.markdown("### 📢 مصروفات الإعلانات لليوم (اختياري)")
        smart_ad_spend = st.number_input("إجمالي صرف الإعلانات لليوم (جنيه) - للنسخ السريع", min_value=0.0, step=10.0, key="smart_ad")
        
        if st.button("معالجة وحفظ البيانات (سريع)", type="primary"):
            if pasted_text:
                try:
                    # تحويل الأرقام العربية إلى إنجليزية لسهولة المعالجة
                    arabic_to_english = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
                    text_clean = pasted_text.translate(arabic_to_english)
                    
                    # استخراج التاريخ
                    date_match = re.search(r'يوم\s*([\d/]+|[\d-]+)', text_clean)
                    if date_match:
                        raw_date = date_match.group(1).replace('/', '-')
                        parts = raw_date.split('-')
                        if len(parts) == 3 and len(parts[2]) == 4:
                            report_date = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                        else:
                            report_date = raw_date
                    else:
                        report_date = str(date.today())
                    
                    # فصل النص بناءً على الفروع
                    branches_data = re.split(r'\*\*فرع\s+(.*?)\*\*', text_clean)[1:]
                    
                    rows_to_add = []
                    
                    for i in range(0, len(branches_data), 2):
                        branch_name = branches_data[i].strip()
                        branch_text = branches_data[i+1]
                        
                        # استخراج الأصناف
                        items = re.findall(r'-\s*(.*?):\s*(\d+)\s*قطعة\s*\|\s*([\d,.]+)\s*جنيه', branch_text)
                        
                        for cat, qty, val in items:
                            # 🔴 هنا الكود بيتجاهل أي سطر فيه كلمة "إجمالي" أو "الإجمالي"
                            if "إجمالي" in cat or "الإجمالي" in cat:
                                continue
                                
                            qty = int(qty)
                            val = float(val.replace(',', ''))
                            
                            # تنظيف اسم التصنيف من أي نجوم ** 
                            clean_cat = cat.replace('*', '').strip()
                            
                            if qty > 0 or val > 0:
                                rows_to_add.append([report_date, branch_name, clean_cat, qty, val, "وارد من رسالة الواتساب"])
                    
                    # إضافة صرف الإعلانات
                    if smart_ad_spend > 0:
                        rows_to_add.append([report_date, "المركز الرئيسي", "صرف إعلانات", 0, smart_ad_spend, "ميزانية الإعلانات لليوم"])
                    
                    # الترحيل
                    if rows_to_add:
                        worksheet.append_rows(rows_to_add)
                        st.success(f"✅ تم بنجاح استخراج وحفظ {len(rows_to_add)} سجل في قاعدة البيانات (تم تجاهل الإجماليات)!")
                        
                        df_preview = pd.DataFrame(rows_to_add, columns=["التاريخ", "الفرع", "التصنيف", "العدد", "القيمة", "ملاحظات"])
                        st.dataframe(df_preview, use_container_width=True)
                    else:
                        st.warning("⚠️ لم أتمكن من العثور على بيانات مبيعات صالحة. تأكد من أن الرسالة مطابقة للصيغة.")
                        
                except Exception as e:
                    st.error(f"حدث خطأ أثناء قراءة النص: {e}")
            else:
                st.warning("يرجى لصق النص أولاً في المربع أعلاه.")

    # ----------------- 2. الإدخال اليدوي -----------------
    with tab_manual:
        with st.form(key='sales_form_manual'):
            col_date, col_branch = st.columns(2)
            with col_date:
                date_input = st.date_input("التاريخ", date.today())
            with col_branch:
                branch = st.selectbox("الفرع", ["Shubra", "Sohag", "RS store 2", "RS store"], key="manual_branch")
                
            st.markdown("---")
            st.markdown("### بيانات التصنيفات")
            
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
                    notes = st.text_input(f"ملاحظات", key=f"notes_{cat}", label_visibility="collapsed", placeholder="ملاحظات (اختياري)")
                inputs[cat] = {"qty": qty, "val": val, "notes": notes}
                
            st.markdown("---")
            st.markdown("### 📢 مصروفات الإعلانات اليومية (اختياري)")
            manual_ad_spend = st.number_input("إجمالي صرف الإعلانات لليوم (جنيه)", min_value=0.0, step=10.0, key="manual_ad")

            submit_button_manual = st.form_submit_button(label='💾 حفظ البيانات يدوياً')
            
            if submit_button_manual:
                rows_to_add = []
                for cat, data in inputs.items():
                    if data["qty"] > 0 or data["val"] > 0:
                        rows_to_add.append([str(date_input), branch, cat, data["qty"], data["val"], data["notes"]])
                
                if manual_ad_spend > 0:
                    rows_to_add.append([str(date_input), "المركز الرئيسي", "صرف إعلانات", 0, manual_ad_spend, "ميزانية الإعلانات لليوم"])
                
                if rows_to_add:
                    worksheet.append_rows(rows_to_add)
                    st.success("✅ تم حفظ البيانات اليدوية بنجاح!")
                else:
                    st.warning("⚠️ لم تقم بإدخال أي بيانات للحفظ.")

elif choice == "لوحة التحكم والتحليلات":
    st.header("📈 تقارير وتحليل المبيعات")
    
    try:
        all_values = worksheet.get_all_values()
        
        if len(all_values) > 1:
            headers = all_values[0]
            data_rows = all_values[1:]
            df = pd.DataFrame(data_rows, columns=headers)
            df.columns = df.columns.str.strip()
            df = df.loc[:, df.columns != '']
        elif len(all_values) == 1:
            df = pd.DataFrame(columns=all_values[0])
        else:
            df = pd.DataFrame()
            
    except Exception as e:
        st.error(f"حدث خطأ أثناء جلب البيانات من الشيت: {e}")
        df = pd.DataFrame()

    if not df.empty:
        try:
            # استبعاد الصفوف الفارغة وتحويل الأنواع
            df = df[df['التاريخ'].notna() & (df['التاريخ'] != '')].copy()
            df['التاريخ'] = pd.to_datetime(df['التاريخ'], errors='coerce')
            
            day_mapping = {
                'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الاثنين',
                'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء', 'Thursday': 'الخميس', 'Friday': 'الجمعة'
            }
            df['يوم الأسبوع'] = df['التاريخ'].dt.day_name().map(day_mapping)
            cats = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
            df['يوم الأسبوع'] = pd.Categorical(df['يوم الأسبوع'], categories=cats, ordered=True)
            
            df['التاريخ_كنص'] = df['التاريخ'].dt.date
            df['العدد'] = pd.to_numeric(df['العدد'], errors='coerce').fillna(0)
            df['القيمة'] = pd.to_numeric(df['القيمة'], errors='coerce').fillna(0)
            
            # --- فلترة البيانات ---
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 📅 فلترة التقارير")
            
            valid_dates = df['التاريخ_كنص'].dropna()
            if not valid_dates.empty:
                min_date = valid_dates.min()
                max_date = valid_dates.max()
                
                date_range = st.sidebar.date_input("اختر نطاق التاريخ", [min_date, max_date])
                if len(date_range) == 2:
                    start_date, end_date = date_range
                else:
                    start_date, end_date = min_date, max_date
                    
                mask = (df['التاريخ_كنص'] >= start_date) & (df['التاريخ_كنص'] <= end_date)
                filtered_df = df.loc[mask]
            else:
                filtered_df = df
            
            sales_df = filtered_df[filtered_df['التصنيف'] != 'صرف إعلانات']
            ads_df = filtered_df[filtered_df['التصنيف'] == 'صرف إعلانات']
            
            # --- المؤشرات الرئيسية (KPIs) ---
            total_qty = sales_df['العدد'].sum()
            total_val = sales_df['القيمة'].sum()
            total_ads = ads_df['القيمة'].sum()
            roas = (total_val / total_ads) if total_ads > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 إجمالي المبيعات", f"{total_val:,.0f} ج")
            col2.metric("📦 إجمالي القطع", f"{total_qty:,.0f}")
            col3.metric("📢 صرف الإعلانات", f"{total_ads:,.0f} ج")
            col4.metric("🚀 العائد على الإعلانات", f"{roas:,.1f} ضعف" if roas > 0 else "بدون إعلانات")
            
            st.markdown("---")
            
            # --- نظام التبويبات (Tabs) ---
            tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
                "📊 ملخص الأداء", 
                "📈 تحليل الاتجاهات", 
                "🏢 مقارنة الفروع", 
                "🔗 تأثير الإعلانات",
                "📅 تحليل أيام الأسبوع",
                "🔮 التنبؤ بالمبيعات"
            ])
            
            with tab1:
                c1, c2 = st.columns(2)
                with c1:
                    branch_sales = sales_df.groupby('الفرع')['القيمة'].sum().reset_index().sort_values(by='القيمة', ascending=False)
                    if not branch_sales.empty and branch_sales['القيمة'].sum() > 0:
                        fig_branch = px.bar(branch_sales, x='الفرع', y='القيمة', color='الفرع', title="المبيعات حسب الفرع", text_auto='.2s')
                        st.plotly_chart(fig_branch, use_container_width=True)
                with c2:
                    cat_sales = sales_df.groupby('التصنيف')['القيمة'].sum().reset_index()
                    if not cat_sales.empty and cat_sales['القيمة'].sum() > 0:
                        fig_cat = px.pie(cat_sales, values='القيمة', names='التصنيف', title="إيرادات المبيعات حسب التصنيف", hole=0.4)
                        st.plotly_chart(fig_cat, use_container_width=True)
            
            with tab2:
                st.markdown("### تطور المبيعات اليومية")
                daily_sales = sales_df.groupby('التاريخ_كنص')['القيمة'].sum().reset_index()
                if not daily_sales.empty:
                    fig_trend = px.line(daily_sales, x='التاريخ_كنص', y='القيمة', markers=True, title="منحنى المبيعات الإجمالية")
                    st.plotly_chart(fig_trend, use_container_width=True)
                
                daily_ads = ads_df.groupby('التاريخ_كنص')['القيمة'].sum().reset_index()
                if not daily_ads.empty and daily_ads['القيمة'].sum() > 0:
                    fig_ads = px.bar(daily_ads, x='التاريخ_كنص', y='القيمة', title="صرف الإعلانات اليومي", color_discrete_sequence=['#ff9999'])
                    st.plotly_chart(fig_ads, use_container_width=True)

            with tab3:
                st.markdown("### تحليل مبيعات الفروع حسب التصنيف (القيمة بالجنيه)")
                if not sales_df.empty:
                    pivot_val = pd.pivot_table(sales_df, values='القيمة', index='الفرع', columns='التصنيف', aggfunc='sum', fill_value=0)
                    pivot_val['إجمالي الفرع'] = pivot_val.sum(axis=1)
                    st.dataframe(pivot_val.style.format("{:,.0f}"), use_container_width=True)
                    
                    st.markdown("### تحليل أعداد القطع المباعة")
                    pivot_qty = pd.pivot_table(sales_df, values='العدد', index='الفرع', columns='التصنيف', aggfunc='sum', fill_value=0)
                    pivot_qty['إجمالي القطع'] = pivot_qty.sum(axis=1)
                    st.dataframe(pivot_qty.style.format("{:,.0f}"), use_container_width=True)
                     
            with tab4:
                st.markdown("### ⏱️ متى ينعكس الصرف الإعلاني على المبيعات؟")
                daily_sales_total = sales_df.groupby('التاريخ_كنص')['القيمة'].sum().reset_index().rename(columns={'القيمة': 'إجمالي المبيعات'})
                daily_ads_total = ads_df.groupby('التاريخ_كنص')['القيمة'].sum().reset_index().rename(columns={'القيمة': 'صرف الإعلانات'})
                merged_df = pd.merge(daily_sales_total, daily_ads_total, on='التاريخ_كنص', how='outer').fillna(0).sort_values('التاريخ_كنص')
                
                if len(merged_df) > 3 and merged_df['صرف الإعلانات'].sum() > 0:
                    max_lag = 7
                    correlations = []
                    for lag in range(max_lag + 1):
                        shifted_ads = merged_df['صرف الإعلانات'].shift(lag)
                        corr = merged_df['إجمالي المبيعات'].corr(shifted_ads)
                        correlations.append({
                            'الفترة الزمنية': "نفس اليوم" if lag == 0 else f"بعد {lag} يوم", 
                            'معامل الارتباط': corr if not pd.isna(corr) else 0
                        })
                    corr_df = pd.DataFrame(correlations)
                    best_lag_row = corr_df.loc[corr_df['معامل الارتباط'].idxmax()]
                    if best_lag_row['معامل الارتباط'] > 0.3:
                        st.success(f"💡 **أعلى تأثير للإعلانات يظهر:** {best_lag_row['الفترة الزمنية']} (بمعامل ارتباط {best_lag_row['معامل الارتباط']:.2f})")
                    else:
                        st.warning("⚠️ لا يوجد ارتباط قوي بين الإعلانات والمبيعات في البيانات الحالية.")
                    fig_corr = px.bar(corr_df, x='الفترة الزمنية', y='معامل الارتباط', title="قوة العلاقة", text_auto='.2f')
                    fig_corr.update_layout(yaxis=dict(range=[-1, 1]))
                    st.plotly_chart(fig_corr, use_container_width=True)
                else:
                    st.warning("نحتاج لعدة أيام متتالية من المبيعات والإعلانات لظهور نتائج الارتباط.")

            with tab5:
                st.markdown("### 📅 أداء الإعلانات والمبيعات حسب أيام الأسبوع")
                dow_sales = sales_df.groupby('يوم الأسبوع', observed=False)['القيمة'].sum().reset_index().rename(columns={'القيمة': 'إجمالي المبيعات'})
                dow_ads = ads_df.groupby('يوم الأسبوع', observed=False)['القيمة'].sum().reset_index().rename(columns={'القيمة': 'صرف الإعلانات'})
                dow_merged = pd.merge(dow_sales, dow_ads, on='يوم الأسبوع', how='left').fillna(0)
                dow_merged['العائد (ROAS)'] = np.where(dow_merged['صرف الإعلانات'] > 0, dow_merged['إجمالي المبيعات'] / dow_merged['صرف الإعلانات'], 0)
                
                if not dow_merged.empty and dow_merged['صرف الإعلانات'].sum() > 0:
                    c1, c2 = st.columns(2)
                    with c1:
                        fig_dow_bar = go.Figure()
                        fig_dow_bar.add_trace(go.Bar(x=dow_merged['يوم الأسبوع'], y=dow_merged['إجمالي المبيعات'], name='المبيعات', marker_color='#1f77b4'))
                        fig_dow_bar.add_trace(go.Bar(x=dow_merged['يوم الأسبوع'], y=dow_merged['صرف الإعلانات'], name='الإعلانات', marker_color='#ff9999'))
                        fig_dow_bar.update_layout(title='المبيعات مقابل الإعلانات', barmode='group')
                        st.plotly_chart(fig_dow_bar, use_container_width=True)
                    with c2:
                        fig_roas = px.line(dow_merged, x='يوم الأسبوع', y='العائد (ROAS)', markers=True, title='كفاءة الإعلان (ROAS)', text='العائد (ROAS)')
                        fig_roas.update_traces(textposition="top center", texttemplate='%{text:.1f}x')
                        st.plotly_chart(fig_roas, use_container_width=True)
                        
                    best_roas_day = dow_merged.loc[dow_merged['العائد (ROAS)'].idxmax()]
                    if best_roas_day['العائد (ROAS)'] > 0:
                        st.success(f"🔥 **أفضل يوم لكفاءة الإعلانات هو ( {best_roas_day['يوم الأسبوع']} )** بيحقق عائد {best_roas_day['العائد (ROAS)']:.1f} ضعف اللي بتصرفه.")
                else:
                    st.info("لا توجد بيانات إعلانات كافية لتحليل أيام الأسبوع.")

            with tab6:
                st.markdown("### 🔮 التنبؤ بالمبيعات للأيام القادمة (AI)")
                st.write("يقوم هذا النموذج بتحليل نمط المبيعات السابقة للتنبؤ بمبيعات الـ 7 أيام القادمة.")
                daily_pred_sales = sales_df.groupby('التاريخ_كنص')['القيمة'].sum().reset_index()
                daily_pred_sales['التاريخ_كنص'] = pd.to_datetime(daily_pred_sales['التاريخ_كنص'])
                daily_pred_sales = daily_pred_sales.sort_values('التاريخ_كنص')
                
                if len(daily_pred_sales) >= 5:
                    min_date_val = daily_pred_sales['التاريخ_كنص'].min()
                    daily_pred_sales['Days'] = (daily_pred_sales['التاريخ_كنص'] - min_date_val).dt.days
                    X = daily_pred_sales[['Days']]
                    y = daily_pred_sales['القيمة']
                    
                    model = LinearRegression()
                    model.fit(X, y)
                    
                    last_date_val = daily_pred_sales['التاريخ_كنص'].max()
                    future_dates = [last_date_val + timedelta(days=i) for i in range(1, 8)]
                    future_days = [(d - min_date_val).days for d in future_dates]
                    
                    future_X = pd.DataFrame({'Days': future_days})
                    predictions = model.predict(future_X)
                    predictions = [max(0, p) for p in predictions] 
                    
                    future_df = pd.DataFrame({
                        'التاريخ': future_dates,
                        'المبيعات المتوقعة': predictions
                    })
                    
                    fig_pred = go.Figure()
                    fig_pred.add_trace(go.Scatter(x=daily_pred_sales['التاريخ_كنص'], y=daily_pred_sales['القيمة'], mode='lines+markers', name='المبيعات الفعلية', line=dict(color='#1f77b4')))
                    fig_pred.add_trace(go.Scatter(x=future_df['التاريخ'], y=future_df['المبيعات المتوقعة'], mode='lines+markers', name='المتوقعة (ذكاء اصطناعي)', line=dict(color='#ff7f0e', dash='dash')))
                    fig_pred.update_layout(title='التوقع المستقبلي لحركة المبيعات', xaxis_title='التاريخ', yaxis_title='القيمة (جنيه)')
                    st.plotly_chart(fig_pred, use_container_width=True)
                    
                    future_df['التاريخ'] = future_df['التاريخ'].dt.strftime('%Y-%m-%d')
                    st.dataframe(future_df.style.format({'المبيعات المتوقعة': "{:,.0f} ج"}), use_container_width=True)
                else:
                    st.warning("⚠️ نحتاج إلى بيانات مبيعات فعلية مسجلة لـ 5 أيام على الأقل لكي يتمكن النموذج من رسم التوقعات.")

            st.markdown("---")
            with st.expander("🔎 عرض جميع البيانات المسجلة (للمراجعة)"):
                st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"حدث خطأ أثناء معالجة البيانات: {e}")
            
    else:
        st.info("لا توجد بيانات مسجلة حتى الآن.")
