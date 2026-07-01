import streamlit as st
import pandas as pd
import psycopg2
from psycopg2.extensions import AsIs
from datetime import datetime, timedelta

st.set_page_config(page_title="PharmaStock Control", layout="wide")

## --- CLOUD DATABASE CONFIGURATION ---
# ⚠️ Make sure to use a colon (:) right after your project ID string, NOT a dot (.)!
# --- CLOUD DATABASE CONFIGURATION ---
DB_URI = "postgresql://postgres.slnpojpmczffprhnvhyg:vyqnidDysgicquqpy3@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

CATEGORIES = ["Antibiotic", "Vitamin", "Supplements", "Vaccine", "Other"]
USER_ID = "ldl"
USER_PIN = "ldl123"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# --- POSTGRES DATABASE FUNCTIONS ---
def get_connection():
    return psycopg2.connect(DB_URI)

def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock (
                id SERIAL PRIMARY KEY,
                drug_name TEXT NOT NULL,
                category TEXT NOT NULL,
                batch_number TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit TEXT NOT NULL,
                min_level INTEGER NOT NULL,
                expiry_date TEXT NOT NULL,
                drug_image BYTEA
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                drug_name TEXT NOT NULL,
                batch_number TEXT NOT NULL,
                quantity_used INTEGER NOT NULL,
                unit TEXT NOT NULL,
                purpose TEXT,
                date_used TEXT NOT NULL
            )
        ''')
        conn.commit()
        c.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"⚠️ Database Connection Failed! Error details: {e}")
        return False

def load_data():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM stock ORDER BY id ASC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def load_logs():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM usage_logs ORDER BY date_used DESC", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

def insert_drug(name, cat, batch, qty, unit, min_lvl, expiry, img_bytes):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO stock (drug_name, category, batch_number, quantity, unit, min_level, expiry_date, drug_image)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ''', (name, cat, batch, qty, unit, min_lvl, expiry, psycopg2.Binary(img_bytes) if img_bytes else None))
    conn.commit()
    c.close()
    conn.close()

def update_drug(drug_id, name, cat, batch, qty, unit, min_lvl, expiry, img_bytes):
    conn = get_connection()
    c = conn.cursor()
    if img_bytes:
        c.execute('''
            UPDATE stock 
            SET drug_name = %s, category = %s, batch_number = %s, quantity = %s, unit = %s, min_level = %s, expiry_date = %s, drug_image = %s
            WHERE id = %s
        ''', (name, cat, batch, qty, unit, min_lvl, expiry, psycopg2.Binary(img_bytes), drug_id))
    else:
        c.execute('''
            UPDATE stock 
            SET drug_name = %s, category = %s, batch_number = %s, quantity = %s, unit = %s, min_level = %s, expiry_date = %s
            WHERE id = %s
        ''', (name, cat, batch, qty, unit, min_lvl, expiry, drug_id))
    conn.commit()
    c.close()
    conn.close()

def add_stock_quantity(drug_id, qty_to_add):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT quantity, drug_name, unit FROM stock WHERE id = %s", (drug_id,))
    res = c.fetchone()
    if res:
        current_qty, name, unit = res
        new_qty = current_qty + qty_to_add
        c.execute("UPDATE stock SET quantity = %s WHERE id = %s", (new_qty, drug_id))
        conn.commit()
        c.close()
        conn.close()
        return True, f"Successfully added {qty_to_add} {unit} to {name}. New balance: {new_qty} {unit}."
    c.close()
    conn.close()
    return False, "Drug not found."

def dispense_drug(drug_id, qty_to_use, purpose):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT drug_name, batch_number, quantity, unit FROM stock WHERE id = %s", (drug_id,))
    drug = c.fetchone()
    
    if drug:
        name, batch, current_qty, unit = drug
        if current_qty >= qty_to_use:
            new_qty = current_qty - qty_to_use
            c.execute("UPDATE stock SET quantity = %s WHERE id = %s", (new_qty, drug_id))
            
            today_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''
                INSERT INTO usage_logs (drug_name, batch_number, quantity_used, unit, purpose, date_used)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (name, batch, qty_to_use, unit, purpose, today_str))
            
            conn.commit()
            c.close()
            conn.close()
            return True, f"Successfully dispensed {qty_to_use} {unit} of {name}."
        else:
            c.close()
            conn.close()
            return False, f"Error: Not enough stock! Only {current_qty} {unit} available."
    c.close()
    conn.close()
    return False, "Drug not found."

def clear_all_data():
    conn = get_connection()
    c = conn.cursor()
    c.execute("TRUNCATE TABLE stock RESTART IDENTITY")
    c.execute("TRUNCATE TABLE usage_logs RESTART IDENTITY")
    conn.commit()
    c.close()
    conn.close()

# Start database architecture safely
db_is_ready = init_db()

# --- PORTAL SCREEN CONTROLLER ---
if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.write("### 🔐 Staff Authentication")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Enter System"):
                if username == USER_ID and password == USER_PIN:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
else:
    st.sidebar.title("🔐 Session Profile")
    st.sidebar.write(f"Logged in as: **{USER_ID}**")
    if st.sidebar.button("Logout of System"):
        st.session_state.authenticated = False
        st.rerun()
        
    if db_is_ready:
        df = load_data()
        df_logs = load_logs()

        if not df.empty:
            df["expiry_date"] = pd.to_datetime(df["expiry_date"])

        # --- ALERTS ---
        st.subheader("⚠️ Safety Alerts")
        col1, col2 = st.columns(2)
        with col1:
            if not df.empty:
                low_stock = df[df["quantity"] <= df["min_level"]]
                if not low_stock.empty:
                    for _, row in low_stock.iterrows():
                        st.error(f"🚨 **Low Stock:** {row['drug_name']} ({row['quantity']} {row['unit']} left)")
                else:
                    st.success("✅ Stock levels sufficient.")
            else:
                st.info("No items in inventory.")
        with col2:
            if not df.empty:
                near_expiry = df[df["expiry_date"] <= (datetime.now() + timedelta(days=60))]
                if not near_expiry.empty:
                    for _, row in near_expiry.iterrows():
                        st.warning(f"⏳ **Expiring Soon:** {row['drug_name']} expires on {row['expiry_date'].strftime('%Y-%m-%d')}")
                else:
                    st.success("✅ No records expiring soon.")
            else:
                st.info("No items in inventory.")

        st.markdown("---")

        # --- APPLICATION TABS ---
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "📋 Current Stock List", 
            "📉 Dispense / Use Drug", 
            "🔄 Quick Restock",
            "➕ Add New Product", 
            "✏️ Edit Existing Stock",
            "⚙️ Danger Zone"
        ])

        # TAB 1: Display
        with tab1:
            st.subheader("Inventory Directory")
            if not df.empty:
                selected_cat = st.selectbox("Filter by Category:", ["All"] + CATEGORIES)
                filtered_df = df.copy()
                if selected_cat != "All":
                    filtered_df = filtered_df[filtered_df["category"] == selected_cat]
                
                for _, row in filtered_df.iterrows():
                    with st.container(border=True):
                        img_col, info_col = st.columns([1, 4])
                        with img_col:
                            if row["drug_image"]:
                                st.image(bytes(row["drug_image"]), width=120)
                            else:
                                st.image("https://placehold.co/120x120?text=No+Photo", width=120)
                        with info_col:
                            st.markdown(f"### {row['drug_name']} `ID: {row['id']}`")
                            st.write(f"**Category:** {row['category']} | **Batch:** {row['batch_number']}")
                            st.write(f"📈 **Quantity:** {row['quantity']} {row['unit']} (Minimum Alert Level: {row['min_level']} {row['unit']})")
                            st.write(f"📅 **Expiry:** {row['expiry_date'].strftime('%Y-%m-%d')}")
            else:
                st.write("The inventory is empty.")

        # TAB 2: Dispense Form
        with tab2:
            st.subheader("Record Used / Dispensed Medication")
            if not df.empty:
                drug_options = {row['id']: f"[{row['category']}] {row['drug_name']} (Batch: {row['batch_number']} | Avail: {row['quantity']} {row['unit']})" for _, row in df.iterrows()}
                selected_drug_id = st.selectbox("Select Drug to Dispense", options=list(drug_options.keys()), format_func=lambda x: drug_options[x])
                
                active_dispense = df[df["id"] == selected_drug_id].iloc[0]
                qty_used = st.number_input(f"Quantity Used ({active_dispense['unit']})", min_value=1, step=1)
                purpose = st.text_input("Purpose / Patient Name / Notes")
                
                if st.button("Confirm Dispense / Usage"):
                    success, message = dispense_drug(selected_drug_id, qty_used, purpose)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.warning("No stock items found.")

        # TAB 3: QUICK RESTOCK TOOL
        with tab3:
            st.subheader("🔄 Quick Restock Existing Product")
            if not df.empty:
                restock_options = {row['id']: f"{row['drug_name']} (Current: {row['quantity']} {row['unit']} | Batch: {row['batch_number']})" for _, row in df.iterrows()}
                selected_restock_id = st.selectbox("Select Product to Restock", options=list(restock_options.keys()), format_func=lambda x: restock_options[x])
                
                active_restock = df[df["id"] == selected_restock_id].iloc[0]
                qty_to_add = st.number_input(f"How many {active_restock['unit']} are you adding?", min_value=1, step=1, value=1)
                
                if st.button("Apply Restock Balance"):
                    success, message = add_stock_quantity(selected_restock_id, qty_to_add)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
            else:
                st.warning("No products found in the database to restock. Please add a product first.")

        # TAB 4: Add Stock
        with tab4:
            st.subheader("Log New Batch or Medication")
            with st.form("add_form", clear_on_submit=True):
                name = st.text_input("Drug Name (e.g., Amoxicillin 500mg)")
                category = st.selectbox("Select Category", CATEGORIES)
                batch = st.text_input("Batch / Lot Number")
                
                qty_col, unit_col = st.columns([2, 1])
                with qty_col:
                    qty = st.number_input("Initial Quantity", min_value=0, step=1)
                with unit_col:
                    unit = st.text_input("Unit Type", value="Pills")
                    
                min_lvl = st.number_input("Minimum Safe Stock Level", min_value=1, step=1)
                expiry = st.date_input("Expiration Date")
                
                uploaded_file = st.file_uploader("📸 Take Picture / Upload Medication Image", type=["jpg", "jpeg", "png"])
                
                submit = st.form_submit_button("Save to Persistent Database")
                
                if submit:
                    if name and batch and unit:
                        img_bytes = uploaded_file.read() if uploaded_file is not None else None
                        expiry_str = expiry.strftime('%Y-%m-%d')
                        insert_drug(name, category, batch, qty, unit, min_lvl, expiry_str, img_bytes)
                        st.success(f"Successfully recorded {name} into permanent storage!")
                        st.rerun()
                    else:
                        st.error("Please fill out Name, Batch, and Unit fields.")

        # TAB 5: Edit Form
        with tab5:
            st.subheader("Modify Existing Medication Record")
            if not df.empty:
                edit_options = {row['id']: f"{row['drug_name']} (Batch: {row['batch_number']})" for _, row in df.iterrows()}
                selected_edit_id = st.selectbox("Select Drug Record to Edit", options=list(edit_options.keys()), format_func=lambda x: edit_options[x])
                active_row = df[df["id"] == selected_edit_id].iloc[0]
                
                with st.form("edit_form"):
                    edit_name = st.text_input("Drug Name", value=active_row["drug_name"])
                    edit_category = st.selectbox("Category", CATEGORIES, index=CATEGORIES.index(active_row["category"]))
                    edit_batch = st.text_input("Batch / Lot Number", value=active_row["batch_number"])
                    
                    eqty_col, eunit_col = st.columns([2, 1])
                    with eqty_col:
                        edit_qty = st.number_input("Adjust Quantity Available", min_value=0, step=1, value=int(active_row["quantity"]))
                    with eunit_col:
                        edit_unit = st.text_input("Unit Type", value=active_row["unit"])
                        
                    edit_min_lvl = st.number_input("Adjust Minimum Safe Stock Level", min_value=1, step=1, value=int(active_row["min_level"]))
                    current_expiry_date = active_row["expiry_date"].date() if isinstance(active_row["expiry_date"], datetime) else datetime.strptime(str(active_row["expiry_date"])[:10], '%Y-%m-%d').date()
                    edit_expiry = st.date_input("Expiration Date", value=current_expiry_date)
                    
                    edit_uploaded_file = st.file_uploader("📸 Replace Photo (Leave empty to keep current picture)", type=["jpg", "jpeg", "png"])
                    
                    if st.form_submit_button("Apply and Save Changes"):
                        if edit_name and edit_batch and edit_unit:
                            img_bytes = edit_uploaded_file.read() if edit_uploaded_file is not None else None
                            expiry_str = edit_expiry.strftime('%Y-%m-%d')
                            update_drug(selected_edit_id, edit_name, edit_category, edit_batch, edit_qty, edit_unit, edit_min_lvl, expiry_str, img_bytes)
                            st.success("Record updated successfully!")
                            st.rerun()
            else:
                st.warning("No records found to edit.")

        # TAB 6: Danger Zone
        with tab6:
            st.subheader("Wipe System Records")
            if st.text_input("Type **DELETE** to unlock:") == "DELETE":
                if st.button("🔴 WIPE ALL DATA PERMANENTLY"):
                    clear_all_data()
                    st.rerun()
    else:
        st.warning("⚠️ Connection to Supabase is pending. The application layout components will build once Supabase clears their system network incident.")