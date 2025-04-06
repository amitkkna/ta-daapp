import os
import streamlit as st
import sqlitecloud
import pandas as pd
from datetime import date
import altair as alt
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Use the connection string from environment variables
conn_string = os.getenv("SQLITECLOUD_CONN_STRING")
conn = sqlitecloud.connect(conn_string)

# Helper: Safe Rerun
def safe_rerun():
    try:
        st.experimental_rerun()
    except AttributeError:
        st.stop()

# Initialize Users Table
def initialize_users():
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    conn.commit()
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    if count == 0:
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                     ("user1", "password1", "admin"))
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                     ("user2", "password2", "user"))
        conn.commit()

initialize_users()

# Initialize Entries Table
conn.execute('''
    CREATE TABLE IF NOT EXISTS entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        employee TEXT,
        expense_type TEXT,
        amount REAL,
        description TEXT
    )
''')
conn.commit()

# Session State Initialization for Login
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "role" not in st.session_state:
    st.session_state["role"] = ""

# Authentication Functions
def get_user(username, password):
    cursor = conn.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
    return cursor.fetchone()

def login():
    st.title("Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")
    if st.button("Login", key="login_button"):
        user = get_user(username, password)
        if user:
            st.session_state["logged_in"] = True
            st.session_state["username"] = user[0]
            st.session_state["role"] = user[1]
            st.success("Logged in successfully!")
            safe_rerun()
        else:
            st.error("Invalid username or password")

if not st.session_state["logged_in"]:
    login()
    st.stop()

st.title("TA & DA Expense and Tour Report Application")
st.write("Logged in as:", st.session_state["username"])
st.write("User Role:", st.session_state["role"])

# Sidebar Navigation & Admin Panel
if st.session_state["role"] == "admin":
    nav = st.sidebar.radio("Navigation", ["Data Entry", "Reports"])
    st.sidebar.subheader("Admin Panel: Add New User")
    new_username = st.sidebar.text_input("New Username")
    new_password = st.sidebar.text_input("New Password", type="password")
    new_role = st.sidebar.selectbox("Role", ["admin", "user"])
    if st.sidebar.button("Add User"):
        try:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                         (new_username, new_password, new_role))
            conn.commit()
            st.sidebar.success(f"User '{new_username}' added successfully!")
        except Exception as e:
            st.sidebar.error(f"Error adding user: {e}")
else:
    nav = "Data Entry"

if st.sidebar.button("Logout"):
    st.session_state["logged_in"] = False
    st.session_state["username"] = ""
    st.session_state["role"] = ""
    safe_rerun()

# Expense Data Helper Functions
def insert_entry(entry_date, employee_name, expense_type, amount, description):
    conn.execute(
        'INSERT INTO entries (date, employee, expense_type, amount, description) VALUES (?, ?, ?, ?, ?)',
        (entry_date, employee_name, expense_type, amount, description)
    )
    conn.commit()

def load_entries():
    cursor = conn.execute('SELECT date, employee, expense_type, amount, description FROM entries')
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=["Date", "Employee", "Expense Type", "Amount", "Description"])
    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"])
    return df

# Navigation: Data Entry and Reports
if nav == "Data Entry":
    st.header("Data Entry")
    with st.form("entry_form", clear_on_submit=True):
        entry_date = st.date_input("Date", date.today())
        employee_name = st.text_input("Employee Name")
        expense_type = st.selectbox("Expense Type", ["TA", "DA", "Tour"])
        amount = st.number_input("Amount", min_value=0.0, step=0.01)
        description = st.text_area("Description")
        submitted = st.form_submit_button("Submit Entry")
        if submitted:
            entry_date_str = entry_date.strftime("%Y-%m-%d")
            insert_entry(entry_date_str, employee_name, expense_type, amount, description)
            st.success("Entry submitted successfully!")
    
    if st.session_state["role"] == "admin":
        st.subheader("All Submitted Entries")
        df = load_entries()
        if not df.empty:
            st.dataframe(df)
        else:
            st.info("No entries submitted yet.")
elif nav == "Reports":
    st.header("Management Reports")
    df = load_entries()
    if df.empty:
        st.info("No data available for reports.")
    else:
        report_option = st.selectbox("Select Report", 
                                     ["Overall Summary", "Employee Ledger", "Expense Head-wise Summary"])
        if report_option == "Overall Summary":
            st.subheader("Overall Summary")
            total_expense = df["Amount"].sum()
            total_ta = df[df["Expense Type"] == "TA"]["Amount"].sum()
            total_da = df[df["Expense Type"] == "DA"]["Amount"].sum()
            total_tour = df[df["Expense Type"] == "Tour"]["Amount"].sum()
            st.write(f"**Total Expenses:** {total_expense}")
            st.write(f"**Total TA Expenses:** {total_ta}")
            st.write(f"**Total DA Expenses:** {total_da}")
            st.write(f"**Total Tour Expenses:** {total_tour}")
            st.subheader("Expense Trend Over Time")
            trend_df = df.groupby("Date")["Amount"].sum().reset_index()
            trend_chart = alt.Chart(trend_df).mark_line().encode(
                x="Date:T",
                y="Amount:Q"
            ).properties(width=700, height=400)
            st.altair_chart(trend_chart, use_container_width=True)
        elif report_option == "Employee Ledger":
            st.subheader("Employee-wise Travel Ledger")
            employees = df["Employee"].unique().tolist()
            selected_employees = st.multiselect("Select Employee(s)", employees, default=employees)
            filtered_df = df[df["Employee"].isin(selected_employees)]
            if filtered_df.empty:
                st.info("No data for the selected employees.")
            else:
                st.dataframe(filtered_df)
                ledger = filtered_df.groupby(["Employee", "Expense Type"])["Amount"].sum().reset_index()
                st.subheader("Ledger Summary")
                st.dataframe(ledger)
        elif report_option == "Expense Head-wise Summary":
            st.subheader("Expense Head-wise Summary")
            summary = df.groupby("Expense Type")["Amount"].sum().reset_index()
            st.dataframe(summary)
            bar_chart = alt.Chart(summary).mark_bar().encode(
                x="Expense Type:N",
                y="Amount:Q",
                color="Expense Type:N"
            ).properties(width=500, height=400)
            st.altair_chart(bar_chart, use_container_width=True)
