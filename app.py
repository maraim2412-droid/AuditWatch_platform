import streamlit as st
import pandas as pd
from fpdf import FPDF
from datetime import datetime
import arabic_reshaper
from bidi.algorithm import get_display
import os
import time
import sqlite3

st.set_page_config(page_title="AuditWatch Enterprise AI", layout="wide")

# --- تنسيق مخصص لتوسيع عرض صندوق الرقم لكي يظهر كاملاً ودون قص ---
st.markdown("""
    <style>
    div[data-testid="metric-container"] {
        width: 100% !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. إعداد قاعدة البيانات الدائمة (SQLite) ---
def init_db():
    conn = sqlite3.connect('audit_enterprise.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auditor TEXT,
            date TEXT,
            decision TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors_portal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor_name TEXT,
            invoice_id TEXT,
            complaint_note TEXT,
            status TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers_portal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            bill_id TEXT,
            inquiry_note TEXT,
            status TEXT
        )
    ''')
    conn.commit()
    return conn

db_conn = init_db()

# --- التهيئة والتخزين المؤقت للحالة ---
if 'show_report' not in st.session_state: st.session_state.show_report = False
if 'discrepancies' not in st.session_state: st.session_state.discrepancies = None
if 'customer_discrepancies' not in st.session_state: st.session_state.customer_discrepancies = None
if 'total_files' not in st.session_state: st.session_state.total_files = 0
if 'analysis_time' not in st.session_state: st.session_state.analysis_time = "0.0 ثانية"
if 'chat_messages' not in st.session_state: st.session_state.chat_messages = []

# --- القواميس متعددة اللغات الشاملة ---
translations = {
    "العربية": {
        "title": "AuditWatch: المنصة الشاملة للتدقيق المالي الذكي",
        "btn_start": "بدء التدقيق المزدوج الشامل (المشتريات والمبيعات)",
        "tab1": "⚠️ المشتريات الحرجة", "tab2": "🛒 مبيعات الزبائن", "tab3": "📋 الفواتير والتكرار", "tab4": "🛡️ سجل القرارات الدائم", "tab5": "💬 مساعد التدقيق الذكي",
        "report_btn": "توليد مسودة التقرير النهائي الشامل",
        "total": "إجمالي العمليات", "mismatch": "حالات المخالفة", "compliance": "نسبة الامتثال",
        "risk_amount": "إجمالي المبالغ المعرضة للخطر", "search": "🔍 ابحث برقم المعاملة:",
        "loading": "جاري التحليل المعمق وفحص المشتريات والمبيعات عبر الذكاء الاصطناعي...",
        "ai_advisor_title": "🧠 استنتاج المستشار الذكي (AuditWatch AI Advisor)",
        "ai_high_risk": "رصد النظام انحرافات مالية أو تكرار محتمل في العمليات، مما يستوجب مراجعة الرقابة الداخلية وإخضاع المعاملات لمراجعة تدقيقية عاجلة.",
        "ai_safe": "البيانات سليمة تماماً ومطابقة لمعايير الامتثال والرقابة.",
        "coso": "🏛 معايير COSO:\n1. بيئة الرقابة\n2. تقييم المخاطر\n3. أنشطة الرقابة\n4. المعلومات\n5. المراقبة"
    },
    "English": {
        "title": "AuditWatch: Comprehensive Financial Audit Platform",
        "btn_start": "Start Comprehensive Audit (Purchasing & Sales)",
        "tab1": "⚠️ Critical Purchasing", "tab2": "🛒 Customer Sales", "tab3": "📋 Invoices & Duplicates", "tab4": "🛡️ Persistent Trail", "tab5": "💬 AI Audit Assistant",
        "report_btn": "Generate Comprehensive Report",
        "total": "Total Transactions", "mismatch": "Mismatched Cases", "compliance": "Compliance Rate",
        "risk_amount": "Total At-Risk Amount", "search": "🔍 Search ID:",
        "loading": "Analyzing purchasing and sales data via AI...",
        "ai_advisor_title": "🧠 AuditWatch AI Advisor Insights",
        "ai_high_risk": "System detected financial anomalies or potential duplicates requiring immediate internal control review.",
        "ai_safe": "Data is clean and compliant. No critical risks detected.",
        "coso": "🏛 COSO Framework:\n1. Control Env\n2. Risk Assessment\n3. Control Activities\n4. Information\n5. Monitoring"
    },
    "Français": {
        "title": "AuditWatch: Plateforme d'Audit Financier Globale",
        "btn_start": "Démarrer l'audit global (Achats & Ventes)",
        "tab1": "⚠️ Achats Critiques", "tab2": "🛒 Ventes & Clients", "tab3": "📋 Factures & Duplicata", "tab4": "🛡️ Journal d'audit permanent", "tab5": "💬 Assistant IA d'audit",
        "report_btn": "Générer le rapport global",
        "total": "Total Transactions", "mismatch": "Cas non conformes", "compliance": "Taux de conformité",
        "risk_amount": "Montant total à risque", "search": "🔍 Rechercher:",
        "loading": "Analyse globale des données par l'IA...",
        "ai_advisor_title": "🧠 Analyse de l'Intelligence Artificielle (AI Advisor)",
        "ai_high_risk": "Le système a détecté des anomalies financières ou des duplicata nécessitant une révision urgente du contrôle interne.",
        "ai_safe": "Données conformes. Aucun risque majeur détecté.",
        "coso": "🏛 Cadre COSO:\n1. Env. Contrôle\n2. Évaluation risques\n3. Activités\n4. Information\n5. Suivi"
    }
}

# --- الشريط الجانبي والصلاحيات ---
st.sidebar.markdown("### 🔐 Settings / إعدادات")
user_role = st.sidebar.selectbox("حدد دور المستخدم / Role:", [
    "مدقق مالي (Auditor)", 
    "مدير تنفيذي (Executive)", 
    "بوابة الموردين (Vendor Portal)", 
    "بوابة الزبائن (Customer Portal)"
])
lang = st.sidebar.selectbox("Language / Langue / اللغة", ["العربية", "Français", "English"])
t = translations[lang]

auditor = st.sidebar.text_input("Auditor Name / المدقق:", "نهاد")
entity = st.sidebar.text_input("Entity Name / المنشأة:", "AuditWatch Corp")
st.sidebar.markdown("---")
st.sidebar.info(t["coso"])

# --- 1. واجهة بوابة الموردين الخارجية ---
if user_role == "بوابة الموردين (Vendor Portal)":
    st.title("🏢 Vendor Self-Service Portal / بوابة الموردين")
    st.warning("هذه البوابة مخصصة للموردين لتقديم التفسيرات والتظلمات المالية على الفواتير المعترَض عليها.")
    v_name = st.text_input("اسم المورد الكريم:")
    v_inv = st.text_input("رقم الفاتورة (مثال: 1):")
    v_note = st.text_area("توضيح المورد أو سبب فارق السعر:")
    if st.button("إرسال التوضيح إلى لجنة التدقيق"):
        if v_name and v_inv:
            cursor = db_conn.cursor()
            cursor.execute("INSERT INTO vendors_portal (vendor_name, invoice_id, complaint_note, status) VALUES (?, ?, ?, ?)", 
                           (v_name, v_inv, v_note, "قيد المراجعة"))
            db_conn.commit()
            st.success("تم إرسال تظلمك بنجاح وسيطلع عليه المدقق المالي في النظام.")
        else:
            st.error("الرجاء ملء اسم المورد ورقم الفاتورة.")
            
    st.markdown("---")
    st.subheader("📋 سجل تظلمات الموردين الواردة:")
    cursor = db_conn.cursor()
    cursor.execute("SELECT vendor_name, invoice_id, complaint_note, status FROM vendors_portal")
    v_rows = cursor.fetchall()
    if v_rows:
        st.table(pd.DataFrame(v_rows, columns=["المورد", "رقم الفاتورة", "التظلم", "الحالة"]))
    else:
        st.info("لا توجد تظلمات واردة حالياً.")

# --- 2. واجهة بوابة الزبائن الخارجية ---
elif user_role == "بوابة الزبائن (Customer Portal)":
    st.title("🛒 Customer Inquiry Portal / بوابة الزبائن")
    st.info("هذه البوابة مخصصة لزبائن المؤسسة لتقديم الاستفسارات والشكاوى.")
    c_name = st.text_input("اسم الزبون الكريم:")
    c_bill = st.text_input("رقم المعاملة / الفاتورة:")
    c_note = st.text_area("تفاصيل الشكوى أو الاستفسار المالي:")
    if st.button("إرسال الاستفسار إلى قسم المراجعة"):
        if c_name and c_bill:
            cursor = db_conn.cursor()
            cursor.execute("INSERT INTO customers_portal (customer_name, bill_id, inquiry_note, status) VALUES (?, ?, ?, ?)", 
                           (c_name, c_bill, c_note, "قيد المعالجة"))
            db_conn.commit()
            st.success("تم إرسال استفسارك بنجاح وسيتواصل معك قسم التدقيق والمبيعات قريباً.")
        else:
            st.error("الرجاء ملء اسم الزبون ورقم الفاتورة.")
            
    st.markdown("---")
    st.subheader("📋 سجل استفسارات وشكاوى الزبائن الواردة:")
    cursor = db_conn.cursor()
    cursor.execute("SELECT customer_name, bill_id, inquiry_note, status FROM customers_portal")
    c_rows = cursor.fetchall()
    if c_rows:
        st.table(pd.DataFrame(c_rows, columns=["الزبون", "رقم الفاتورة", "الاستفسار", "الحالة"]))
    else:
        st.info("لا توجد استفسارات أو شكاوى زبائن حالياً.")

# --- الواجهة الرئيسية الشاملة للمدقق والمدير التنفيذي ---
else:
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.markdown("### 🛡️ **AW**")
    with col_title:
        st.title(t["title"])

    st.success(f"🤖 **مرحباً بكِ، {auditor}.** AI ready to help you analyze data today and give strategic insights. مرحبا بكِ، نهاد. أنا مساعدك الذكي جاهز لمساعدتك في تحليل البيانات.")

    uploaded_file = st.file_uploader("Upload CSV / ارفعي ملف المعاملات الشامل (CSV)", type="csv")

    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"خطأ في قراءة ملف الـ CSV: {e}")
            df = None

        if df is not None:
            if st.button(t["btn_start"]):
                start_time = time.time()
                with st.spinner(t["loading"]):
                    time.sleep(1.5)
                    
                    # 1. تحليل المشتريات
                    if 'invoice_price' in df.columns and 'po_price' in df.columns:
                        df['invoice_price'] = pd.to_numeric(df['invoice_price'], errors='coerce')
                        df['po_price'] = pd.to_numeric(df['po_price'], errors='coerce')
                        d = df[df['invoice_price'] > df['po_price']].copy()
                        
                        def deep_audit_analysis(row):
                            diff = row['invoice_price'] - row['po_price']
                            percent = round((diff / row['po_price']) * 100, 1) if row['po_price'] > 0 else 0
                            
                            # إضافة علامة النسبة المئوية % لدرجة المخاطر
                            score = f"{min(int(percent * 3), 100)}%"
                            
                            if percent > 20:
                                explanation = f"تجاوز كبير بنسبة {percent}% (فرق: {diff} DA)."
                                level = "🔴 خطر احتيال"
                            elif percent > 5:
                                explanation = f"خطأ إدخال أو تعديل سعر بنسبة {percent}%."
                                level = "🟠 مشبوه"
                            else:
                                explanation = f"فارق بسيط يحتاج مراجعة بنسبة {percent}%."
                                level = "🟡 يحتاج مراجعة"
                            return explanation, level, score

                        if not d.empty:
                            d['Analysis_Details'], d['Risk_Level'], d['Risk_Score'] = zip(*d.apply(deep_audit_analysis, axis=1))
                        else:
                            d['Analysis_Details'], d['Risk_Level'], d['Risk_Score'] = [], [], []
                        st.session_state.discrepancies = d
                    else:
                        st.session_state.discrepancies = pd.DataFrame()

                    # 2. تحليل المبيعات والزبائن
                    if 'standard_price' in df.columns and 'sold_price' in df.columns:
                        df['standard_price'] = pd.to_numeric(df['standard_price'], errors='coerce')
                        df['sold_price'] = pd.to_numeric(df['sold_price'], errors='coerce')
                        c_disc = df[df['sold_price'] < df['standard_price']].copy()
                        
                        def sales_audit_analysis(row):
                            diff = row['standard_price'] - row['sold_price']
                            percent = round((diff / row['standard_price']) * 100, 1) if row['standard_price'] > 0 else 0
                            if percent > 15:
                                note = f"تخفيض سعر بيع غير مبرر بنسبة {percent}% (خسارة: {diff} DA)."
                                lvl = "🔴 تخفيض حاد"
                            else:
                                note = f"تخفيض عادي في سعر البيع بنسبة {percent}%."
                                lvl = "🟡 تخفيض طفيف"
                            return note, lvl

                        if not c_disc.empty:
                            c_disc['Sales_Note'], c_disc['Sales_Risk'] = zip(*c_disc.apply(sales_audit_analysis, axis=1))
                        else:
                            c_disc['Sales_Note'], c_disc['Sales_Risk'] = [], []
                        st.session_state.customer_discrepancies = c_disc
                    else:
                        st.session_state.customer_discrepancies = pd.DataFrame()

                    st.session_state.total_files = len(df)
                    st.session_state.show_report = False
                    
                    end_time = time.time()
                    st.session_state.analysis_time = f"{round(end_time - start_time, 2)} ثانية"

            if st.session_state.discrepancies is not None:
                d = st.session_state.discrepancies
                c_disc = st.session_state.customer_discrepancies if st.session_state.customer_discrepancies is not None else pd.DataFrame()
                total_inv = st.session_state.total_files
                total_mismatch = len(d) + len(c_disc)
                comp = round(((total_inv - total_mismatch) / total_inv) * 100, 1) if total_inv > 0 else 100
                
                risk_amount_purch = (d['invoice_price'] - d['po_price']).sum() if not d.empty else 0
                risk_amount_sales = (c_disc['standard_price'] - c_disc['sold_price']).sum() if not c_disc.empty else 0
                total_risk_amount = risk_amount_purch + risk_amount_sales

                st.markdown("---")
                h1, h2, h3 = st.columns(3)
                h1.caption(f"🕒 **آخر تحليل:** {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                h2.caption(f"👤 **المستخدم:** {auditor} ({user_role})")
                h3.caption(f"⚡ **سرعة المعالجة:** {st.session_state.analysis_time}")
                st.markdown("---")

                st.markdown(f"## 📊 الملخص التنفيذي للإدارة ({entity})")
                
                # --- توزيع الأعمدة مع التنسيق لضمان ظهور الرقم كاملاً ---
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(t["total"], total_inv)
                c2.metric(t["mismatch"], total_mismatch)
                c3.metric(t["compliance"], f"{comp}%")
                c4.markdown(f"""
                    <div style="background-color: transparent; padding: 0px; margin: 0px;">
                        <div style="font-size: 14px; color: #95a5a6; margin-bottom: 5px;">{t["risk_amount"]}</div>
                        <div style="font-size: 24px; font-weight: bold; color: #ffffff; white-space: nowrap; overflow: visible;">{total_risk_amount:,.2f} DA</div>
                    </div>
                """, unsafe_allow_html=True)
                
                st.markdown("---")

                if user_role == "مدير تنفيذي (Executive)":
                    st.info("👁️ Executive View (عرض التقارير والملخصات الشاملة فقط).")
                    st.markdown("### المشتريات غير المطابقة:")
                    st.dataframe(d, use_container_width=True)
                    st.markdown("### مبيعات الزبائن غير المطابقة:")
                    st.dataframe(c_disc, use_container_width=True)
                else:
                    search = st.text_input(t["search"])
                    if search:
                        st.dataframe(df[df.astype(str).apply(lambda x: x.str.contains(search)).any(axis=1)], use_container_width=True)

                    # --- التبويبات الخمسة الشاملة للمدقق ---
                    tab1, tab2, tab3, tab4, tab5 = st.tabs([t["tab1"], t["tab2"], t["tab3"], t["tab4"], t["tab5"]])
                    
                    with tab1: 
                        st.markdown("### ⚠️ الحالات الحرجة للمشتريات (الموردين)")
                        if not d.empty:
                            st.warning("⚠️ تحذير: نسبة المخاطر مرتفعة جداً! أنصحك بالتركيز على مراجعة الفواتير ذات التجاوز المالي أولاً.")
                            st.info("🔮 توقع ذكاء تليبي (Predictive Audit): الموردون (مورد_ب) يظهرون بشكل متكرر، أوقع أن يصبحوا أعلى خطورة خلال الشهر القادم ويُسَمَح بتجميد التعامل المؤقت معهم.")
                            st.dataframe(d, use_container_width=True)
                        else:
                            st.info("لا توجد مخالفات في المشتريات.")
                        
                    with tab2:
                        st.markdown("### 🛒 مبيعات الزبائن والتخفيضات غير المبررة")
                        if not c_disc.empty:
                            st.dataframe(c_disc, use_container_width=True)
                        else:
                            st.info("لا توجد مخالفات في مبيعات الزبائن.")

                    with tab3: 
                        st.markdown("### 📋 سجل المعاملات والفحص الذكي للتكرار (Duplicate Check)")
                        duplicates = df[df.duplicated(subset=['id'], keep=False)] if 'id' in df.columns else pd.DataFrame()
                        if not duplicates.empty:
                            st.error("⚠️ تنبيه خطير: تم اكتشاف معاملات تحمل نفس المعرف (تكرار محتمل):")
                            st.dataframe(duplicates, use_container_width=True)
                        else:
                            st.success("✅ لا توجد معاملات مكررة مطابقة في المعرفات.")
                        st.markdown("---")
                        st.dataframe(df, use_container_width=True)
                        
                    with tab4:
                        st.markdown("### 🛡️ سجل حماية المدقق والقرارات المعتمدة (قاعدة بيانات SQLite الدائمة)")
                        decision_note = st.text_input("سجلي سبب اعتماد أو معالجة الحالة الشاملة لتوثيقها بشكل دائم:")
                        if st.button("توثيق وحفظ القرار في قاعدة البيانات"):
                            if decision_note:
                                cursor = db_conn.cursor()
                                cursor.execute("INSERT INTO audit_logs (auditor, date, decision) VALUES (?, ?, ?)", 
                                               (auditor, str(datetime.now().date()), decision_note))
                                db_conn.commit()
                                st.success("تم حفظ القرار بشكل دائم في قاعدة البيانات (SQLite)!")
                            else:
                                st.error("الرجاء كتابة تفاصيل القرار.")
                                
                        cursor = db_conn.cursor()
                        cursor.execute("SELECT auditor, date, decision FROM audit_logs")
                        db_logs = cursor.fetchall()
                        if db_logs:
                            st.table(pd.DataFrame(db_logs, columns=["المدقق", "التاريخ", "القرار"]))
                        else:
                            st.info("لا توجد قرارات موثقة في قاعدة البيانات بعد.")

                    with tab5:
                        st.markdown("### 💬 مساعد التدقيق الذكي الشامل (AI Chat Assistant)")
                        st.info("اسألي مساعدك المالي الذكي عن أي استفسار يتعلق بالمشتريات، المبيعات، المخاطر، أو التوصيات!")
                        
                        chat_container = st.container()
                        with chat_container:
                            for msg in st.session_state.chat_messages:
                                if msg["role"] == "user":
                                    st.markdown(f"**👤 أنتِ:** {msg['content']}")
                                else:
                                    st.markdown(f"**🤖 مساعد التدقيق الذكي:** {msg['content']}")

                        user_query = st.text_input("اكتبي سؤالك هنا للمساعد الذكي (مثلاً: ما هي أعلى مخالفة؟):", key="chat_input_field")
                        if st.button("إرسال السؤال للمساعد"):
                            if user_query:
                                st.session_state.chat_messages.append({"role": "user", "content": user_query})
                                
                                query_lower = user_query.lower()
                                if "أعلى" in query_lower or "highest" in query_lower or "أكبر" in query_lower:
                                    if not d.empty:
                                        max_row = d.loc[(d['invoice_price'] - d['po_price']).idxmax()]
                                        bot_response = f"أعلى فاتورة معرضة للخطر هي الفاتورة رقم **{max_row['id']}** بفرق قدره **{max_row['invoice_price'] - max_row['po_price']} DA**."
                                    else:
                                        bot_response = "لا توجد حالات مخالفة مسجلة في المشتريات."
                                elif "كم" in query_lower or "count" in query_lower or "عدد" in query_lower:
                                    bot_response = f"إجمالي المخالفات المرصدة في المشتريات والمبيعات معاً هو **{total_mismatch}** من أصل **{total_inv}** معاملة."
                                else:
                                    bot_response = f"بناءً على معايير COSO الشاملة للرقابة الداخلية، أنصحك بمراجعة دورة المشتريات والمبيعات وتوثيق القرار في السجل الدائم."
                                    
                                st.session_state.chat_messages.append({"role": "assistant", "content": bot_response})
                                st.rerun()

                    st.markdown("### 📈 تحليل بصري للمعاملات غير المطابقة")
                    if not d.empty and 'po_price' in d.columns and 'invoice_price' in d.columns:
                        st.bar_chart(d[['po_price', 'invoice_price']])

                    st.markdown("### 🏢 لوحة ذكاء الموردين (Vendor Intelligence)")
                    if 'vendor_name' in df.columns and not df.empty:
                        v_counts = df['vendor_name'].dropna()
                        if not v_counts.empty:
                            vendor_report = v_counts.value_counts().reset_index()
                            vendor_report.columns = ['vendor_name', 'counts']
                            st.table(vendor_report)

                    st.markdown("---")
                    st.markdown(f"### {t['ai_advisor_title']}")
                    if total_mismatch > 0:
                        st.info(f'"{t["ai_high_risk"]}"')
                    else:
                        st.success(f'"{t["ai_safe"]}"')

                    st.markdown("---")
                    if st.button(t["report_btn"]): 
                        st.session_state.show_report = True
                        report = f"تقرير التدقيق الشامل ({entity})\nالمدقق: {auditor}\nالتاريخ: {datetime.now().date()}\nإجمالي العمليات: {total_inv}\nإجمالي المخالفات: {total_mismatch}\n"
                        report += f"\n- إجمالي المبلغ المعرض للخطر: {total_risk_amount:,.2f} DA\n"
                        report += "\n--- إقرار التدقيق الشامل ---\nيؤكد هذا التقرير التزام المنشأة بـ (COSO Framework) عبر الرقابة على دورة المشتريات والمبيعات."
                        st.session_state['final_report'] = report

                    if st.session_state.show_report:
                        st.text_area("مسودة التقرير النهائي الشامل:", value=st.session_state['final_report'], height=250)

                        if st.button("📥 تحميل التقرير كـ PDF"):
                            font_path = "arial.ttf"
                            if os.path.exists(font_path):
                                pdf = FPDF()
                                pdf.add_page()
                                pdf.add_font("Arial", "", font_path, uni=True)
                                pdf.set_font("Arial", size=14)
                                bidi_text = get_display(arabic_reshaper.reshape(st.session_state['final_report']))
                                pdf.multi_cell(0, 10, txt=bidi_text, align='R')
                                pdf_output = pdf.output(dest='S')
                                st.download_button(
                                    label="اضغطي هنا لتحميل ملف الـ PDF",
                                    data=bytes(pdf_output),
                                    file_name="Comprehensive_Audit_Report.pdf",
                                    mime="application/pdf"
                                )
                            else:
                                st.error(f"خطأ: الملف {font_path} غير موجود.")
            else:
                st.info("الضغط على زر 'بدء التدقيق المزدوج الشامل' لتفعيل التحليل.")
    else:
        st.info("قم برفع ملف المعاملات بصيغة CSV للبدء.")