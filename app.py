import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

st.set_page_config(page_title="PharmaStock Control", layout="wide")

# --- DATABASE SETUP ---
DB_FILE = "pharma_inventory_v2.db"
CATEGORIES = ["Antibiotic", "Vitamin", "Supplements", "Vaccine", "Other"]

# Simple Admin Account Credentials (Change these to whatever you like)
USER_ID = "ldl"
USER_PIN = "ldl123"

# Initialize Session State for Login Tracking
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT NOT NULL,
            category TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit TEXT NOT NULL,
            min_level INTEGER NOT NULL,
            expiry_date TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_name TEXT NOT NULL,
            batch_number TEXT NOT NULL,
            quantity_used INTEGER NOT NULL,
            unit TEXT NOT NULL,
            purpose TEXT,
            date_used TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()
    return df

def load_logs():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM usage_logs ORDER BY date_used DESC", conn)
    conn.close()
    return df

def insert_drug(name, cat, batch, qty, unit, min_lvl, expiry):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO stock (drug_name, category, batch_number, quantity, unit, min_level, expiry_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (name, cat, batch, qty, unit, min_lvl, expiry))
    conn.commit()
    conn.close()

def update_drug(drug_id, name, cat, batch, qty, unit, min_lvl, expiry):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        UPDATE stock 
        SET drug_name = ?, category = ?, batch_number = ?, quantity = ?, unit = ?, min_level = ?, expiry_date = ?
        WHERE id = ?
    ''', (name, cat, batch, qty, unit, min_lvl, expiry, drug_id))
    conn.commit()
    conn.close()

def dispense_drug(drug_id, qty_to_use, purpose):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT drug_name, batch_number, quantity, unit FROM stock WHERE id = ?", (drug_id,))
    drug = c.fetchone()
    
    if drug:
        name, batch, current_qty, unit = drug
        if current_qty >= qty_to_use:
            new_qty = current_qty - qty_to_use
            c.execute("UPDATE stock SET quantity = ? WHERE id = ?", (new_qty, drug_id))
            
            today_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('''
                INSERT INTO usage_logs (drug_name, batch_number, quantity_used, unit, purpose, date_used)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, batch, qty_to_use, unit, purpose, today_str))
            
            conn.commit()
            conn.close()
            return True, f"Successfully dispensed {qty_to_use} {unit} of {name}."
        else:
            conn.close()
            return False, f"Error: Not enough stock! Only {current_qty} {unit} available."
    conn.close()
    return False, "Drug not found."

def clear_all_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM stock")
    c.execute("DELETE FROM usage_logs")
    conn.commit()
    conn.close()

# Initialize Database Architecture
init_db()


# --- INTERFACE ROUTING ---

# GATE 1: LOGIN PORTAL
if not st.session_state.authenticated:
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.write("### 🔐 Staff Authentication")
        with st.form("login_form"):
            username = st.text_input("Username Input")
            password = st.text_input("Password Input", type="password")
            login_btn = st.form_submit_button("Enter System")
            
            if login_btn:
                if username == USER_ID and password == USER_PIN:
                    st.session_state.authenticated = True
                    st.success("Access Granted!")
                    st.rerun()
                else:
                    st.error("Invalid Username or Password combination.")

# GATE 2: THE MAIN SYSTEM DASHBOARD (Loads only if authenticated)
else:
    # Sidebar logout configuration
    st.sidebar.title("🔐 Session Profile")
    st.sidebar.write(f"Logged in as: **{USER_ID}**")
    if st.sidebar.button("Logout of System"):
        st.session_state.authenticated = False
        st.rerun()
        
    st.title("💊 Drug Stock & Dispensing System")
    
    # Reload freshest data variations
    df = load_data()
    df_logs = load_logs()

    if not df.empty:
        df["expiry_date"] = pd.to_datetime(df["expiry_date"])

    # --- ALERTS SECTION ---
    st.subheader("⚠️ Safety Alerts")
    col1, col2 = st.columns(2)

    with col1:
        if not df.empty:
            low_stock = df[df["quantity"] <= df["min_level"]]
            if not low_stock.empty:
                for _, row in low_stock.iterrows():
                    st.error(f"🚨 **Low Stock:** {row['drug_name']} ({row['quantity']} {row['unit']} left / Min is {row['min_level']} {row['unit']})")
            else:
                st.success("✅ All stock levels are sufficient.")
        else:
            st.info("No items in inventory.")

    with col2:
        if not df.empty:
            near_expiry = df[df["expiry_date"] <= (datetime.now() + timedelta(days=60))]
            if not near_expiry.empty:
                for _, row in near_expiry.iterrows():
                    st.warning(f"⏳ **Expiring Soon:** {row['drug_name']} (Batch: {row['batch_number']}) expires on {row['expiry_date'].strftime('%Y-%m-%d')}")
            else:
                st.success("✅ No medications expiring soon.")
        else:
            st.info("No items in inventory.")

    st.markdown("---")

    # --- APP LAYOUT ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Current Stock List", 
        "📉 Dispense / Use Drug", 
        "➕ Add New Stock", 
        "✏️ Edit Existing Stock",
        "⚙️ Danger Zone"
    ])

    # TAB 1: Current Stock Directory
    with tab1:
        st.subheader("Inventory Directory")
        if not df.empty:
            selected_cat = st.selectbox("Filter by Category:", ["All"] + CATEGORIES)
            
            display_df = df.copy()
            display_df["expiry_date"] = display_df["expiry_date"].dt.strftime('%Y-%m-%d')
            
            display_df["Quantity Available"] = display_df["quantity"].astype(str) + " " + display_df["unit"]
            display_df["Min Trigger Level"] = display_df["min_level"].astype(str) + " " + display_df["unit"]
            
            display_df = display_df[["id", "drug_name", "category", "batch_number", "Quantity Available", "Min Trigger Level", "expiry_date"]]
            display_df.columns = ["ID", "Drug Name", "Category", "Batch Number", "Quantity Available", "Min Level", "Expiry Date"]
            
            if selected_cat != "All":
                display_df = display_df[display_df["Category"] == selected_cat]
                
            st.dataframe(display_df, use_container_width=True, hide_index=True)
        else:
            st.write("The inventory is empty.")
            
        st.markdown("---")
        st.subheader("📜 Used Drug History Log")
        if not df_logs.empty:
            display_logs = df_logs.copy()
            display_logs["Quantity Used"] = display_logs["quantity_used"].astype(str) + " " + display_logs["unit"]
            display_logs = display_logs[["id", "drug_name", "batch_number", "Quantity Used", "purpose", "date_used"]]
            display_logs.columns = ["Log ID", "Drug Name", "Batch Number", "Quantity Used", "Purpose / Patient", "Date & Time Used"]
            st.dataframe(display_logs, use_container_width=True, hide_index=True)
        else:
            st.write("No usage logs recorded yet.")

    # TAB 2: Dispense Form
    with tab2:
        st.subheader("Record Used / Dispensed Medication")
        if not df.empty:
            drug_options = {row['id']: f"[{row['category']}] {row['drug_name']} (Batch: {row['batch_number']} | Avail: {row['quantity']} {row['unit']})" for _, row in df.iterrows()}
            selected_drug_id = st.selectbox("Select Drug to Use", options=list(drug_options.keys()), format_func=lambda x: drug_options[x])
            
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
            st.warning("You must add items to your stock before you can record usage.")

    # TAB 3: Add Items Form
    with tab3:
        st.subheader("Log New Batch or Medication")
        with st.form("add_form", clear_on_submit=True):
            name = st.text_input("Drug Name (e.g., Amoxicillin 500mg)")
            category = st.selectbox("Select Category", CATEGORIES)
            batch = st.text_input("Batch / Lot Number")
            
            qty_col, unit_col = st.columns([2, 1])
            with qty_col:
                qty = st.number_input("Initial Quantity", min_value=0, step=1)
            with unit_col:
                unit = st.text_input("Unit Type", value="Pills", placeholder="e.g., Box, Vial, Bottle")
                
            min_lvl = st.number_input("Minimum Safe Stock Level", min_value=1, step=1)
            expiry = st.date_input("Expiration Date")
            
            submit = st.form_submit_button("Save to Persistent Database")
            
            if submit:
                if name and batch and unit:
                    expiry_str = expiry.strftime('%Y-%m-%d')
                    insert_drug(name, category, batch, qty, unit, min_lvl, expiry_str)
                    st.success(f"Successfully recorded {name} into permanent storage!")
                    st.rerun()
                else:
                    st.error("Please fill out all text fields (Name, Batch, and Unit).")

    # TAB 4: Edit Form
    with tab4:
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
                
                save_changes = st.form_submit_button("Apply and Save Changes")
                
                if save_changes:
                    if edit_name and edit_batch and edit_unit:
                        expiry_str = edit_expiry.strftime('%Y-%m-%d')
                        update_drug(selected_edit_id, edit_name, edit_category, edit_batch, edit_qty, edit_unit, edit_min_lvl, expiry_str)
                        st.success("Record updated successfully!")
                        st.rerun()
                    else:
                        st.error("Fields cannot be left blank.")
        else:
            st.warning("No records found to edit.")

    # TAB 5: Danger Zone
    with tab5:
        st.subheader("Wipe System Records")
        st.warning("⚠️ Warning: Clicking the button below will instantly clear all stock logs and history logs forever. This cannot be undone.")
        confirm_text = st.text_input("Type **DELETE** to unlock the reset button:")
        if confirm_text == "DELETE":
            if st.button("🔴 WIPE ALL DATA PERMANENTLY"):
                clear_all_data()
                st.success("Database cleared successfully!")
                st.rerun()
        else:
            st.button("🔴 WIPE ALL DATA PERMANENTLY", disabled=True)