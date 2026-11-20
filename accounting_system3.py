"""
Group 1 System: Automated Accounting System with 12-Column Worksheet (GUI)

Tabs: New Transaction | Ledger | Accounts | Transaction History | Adjustments | Worksheet
The worksheet is built automatically from the entries:
  daily entries -> Unadjusted TB, adjusting entries -> Adjustments, both -> Adjusted TB,
  then each account goes to Income Statement / Owner's Equity / Balance Sheet by its type.
Data is saved to 'accounting_data.json' (same folder). Needs only Python 3 (tkinter included).

FILE MAP (search for the banner names to jump around):
  1. CONSTANTS & SETTINGS
  2. DATA LAYER            (load / save JSON)
  3. HELPER FUNCTIONS      (money format, Dr/Cr split)
  4. WORKSHEET ENGINE      (build_worksheet - the accounting logic)
  5. MAIN APP CLASS
       5.1  Setup & Style
       5.2  Shared UI Helpers
       5.3  Tab: New Transaction
       5.4  Tab: Ledger
       5.5  Tab: Accounts
       5.6  Tab: Transaction History
       5.7  Tab: Adjustments
       5.8  Tab: Worksheet
       5.9  Refresh Control
  6. PROGRAM ENTRY POINT
"""

import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


# ============================================================================
# 1. CONSTANTS & SETTINGS
# ============================================================================

DATA_FILE = "accounting_data.json"
EPS = 0.005  # tolerance for floating-point comparisons (half a cent)

# Order accounts appear in the worksheet
TYPE_ORDER = ["Asset", "Contra Asset", "Liability", "Equity", "Drawings", "Revenue", "Expense"]
DEBIT_NORMAL = ("Asset", "Drawings", "Expense")   # types whose normal balance is a debit
IS_TYPES = ("Revenue", "Expense")                 # -> Income Statement columns
OE_TYPES = ("Equity", "Drawings")                 # -> Owner's Equity columns

# 12 worksheet columns: u=Unadjusted, j=adjustments, a=Adjusted, i=Income Stmt, o=Owner's Equity, b=Balance Sheet
COLS = [p + s for p in ("u", "j", "a", "i", "o", "b") for s in ("_dr", "_cr")]
GROUPS = ("Unadjusted Trial Balance", "Adjustments", "Adjusted Trial Balance",
          "Income Statement", "Owner's Equity", "Balance Sheet")

# Icons shown next to each tab name in the left sidebar
ICONS = {"New Transaction": "➕", "Ledger": "📒", "Accounts": "🏦",
         "Transaction History": "🕘", "Adjustments": "🛠", "Worksheet": "📊"}

# Starting chart of accounts (used when no save file exists)
DEFAULT_ACCOUNTS = [{"name": n, "type": t} for n, t in [
    ("Cash", "Asset"), ("Accounts Receivable", "Asset"), ("Supplies", "Asset"),
    ("Prepaid Expenses", "Asset"), ("Equipment", "Asset"),
    ("Accumulated Depreciation", "Contra Asset"),
    ("Accounts Payable", "Liability"), ("Salaries Payable", "Liability"), ("Unearned Revenue", "Liability"),
    ("Owner's Capital", "Equity"), ("Owner's Drawings", "Drawings"), ("Sales Revenue", "Revenue"),
    ("Rent Expense", "Expense"), ("Salaries Expense", "Expense"), ("Utilities Expense", "Expense"),
    ("Supplies Expense", "Expense"), ("Insurance Expense", "Expense"), ("Depreciation Expense", "Expense")]]

# Adjustment presets: name -> (debit acct, debit type, credit acct, credit type, description)
# The types let the app auto-create the account if it's missing.
ADJUSTMENT_TEMPLATES = {
    "Depreciation of equipment": ("Depreciation Expense", "Expense", "Accumulated Depreciation",
                                  "Contra Asset", "Depreciation for the period"),
    "Supplies used": ("Supplies Expense", "Expense", "Supplies", "Asset", "Supplies used during the period"),
    "Prepaid expense expired": ("Insurance Expense", "Expense", "Prepaid Expenses", "Asset",
                                "Prepaid expense expired"),
    "Accrued expense (unpaid salaries)": ("Salaries Expense", "Expense", "Salaries Payable", "Liability",
                                          "Salaries earned but not yet paid"),
    "Unearned revenue now earned": ("Unearned Revenue", "Liability", "Sales Revenue", "Revenue",
                                    "Unearned revenue earned during the period"),
    "Accrued revenue (earned, not billed)": ("Accounts Receivable", "Asset", "Sales Revenue", "Revenue",
                                             "Revenue earned but not yet billed"),
    "Bad debts estimate": ("Bad Debts Expense", "Expense", "Allowance for Doubtful Accounts",
                           "Contra Asset", "Estimated uncollectible accounts"),
    "Custom adjustment": ("", None, "", None, ""),
}


# ============================================================================
# 2. DATA LAYER  (load / save the JSON file)
# ============================================================================

def load_data():
    """Read accounts, transactions and rules from the JSON file; fall back to defaults if missing."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        transactions = data.get("transactions", [])
        for t in transactions:
            t.setdefault("kind", "regular")  # older saves have no 'kind'
        return (data.get("accounts") or [dict(a) for a in DEFAULT_ACCOUNTS]), transactions, data.get("rules", [])
    return [dict(a) for a in DEFAULT_ACCOUNTS], [], []


def save_data(accounts, transactions, rules):
    """Write everything to the JSON file."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts, "transactions": transactions, "rules": rules}, f, indent=2)


# ============================================================================
# 3. HELPER FUNCTIONS
# ============================================================================

def money(v):
    """Format a number with commas and 2 decimals; negatives in parentheses."""
    return f"({-v:,.2f})" if v < -EPS else f"{v:,.2f}"


def split_dr_cr(net):
    """Net (debits - credits): positive -> Debit column, negative -> Credit column."""
    net = round(net, 2)
    return (net, 0.0) if net > 0 else (0.0, -net)


# ============================================================================
# 4. WORKSHEET ENGINE  (pure accounting logic, no GUI)
# ============================================================================

def build_worksheet(accounts, transactions):
    """Build the 12-column worksheet; returns rows, totals, net income, ending equity.

    Steps: sum daily (reg) and adjusting (adj) debits/credits per account -> Unadjusted TB,
    Adjustments, Adjusted TB -> push each adjusted balance to IS / OE / BS by account type ->
    add the Net Income and Ending Equity balancing rows.
    """
    ordered = sorted(accounts, key=lambda a: TYPE_ORDER.index(a["type"]) if a["type"] in TYPE_ORDER else 99)

    # --- Totals per account: regular vs adjusting, debit vs credit ---
    tot = {k: {} for k in ("reg_dr", "reg_cr", "adj_dr", "adj_cr")}
    for t in transactions:
        p = "adj" if t.get("kind") == "adjusting" else "reg"
        for side, key in (("dr", "debit"), ("cr", "credit")):
            d = tot[f"{p}_{side}"]
            d[t[key]] = d.get(t[key], 0.0) + t["amount"]

    # --- One worksheet row per account ---
    rows = []
    for acc in ordered:
        n = acc["name"]
        rd, rc, ad, ac = (tot[k].get(n, 0.0) for k in ("reg_dr", "reg_cr", "adj_dr", "adj_cr"))
        adjusted = round(rd - rc + ad - ac, 2)
        row = dict.fromkeys(COLS, 0.0)
        row.update(name=n, type=acc["type"])
        row["u_dr"], row["u_cr"] = split_dr_cr(rd - rc)          # Unadjusted TB
        row["j_dr"], row["j_cr"] = round(ad, 2), round(ac, 2)    # Adjustments
        row["a_dr"], row["a_cr"] = split_dr_cr(adjusted)         # Adjusted TB
        # Copy the adjusted balance into IS, OE or BS depending on the type
        target = "i" if acc["type"] in IS_TYPES else "o" if acc["type"] in OE_TYPES else "b"
        row[target + "_dr"], row[target + "_cr"] = row["a_dr"], row["a_cr"]
        # Extra fields used by the Accounts tab (not worksheet columns)
        row["p_dr"], row["p_cr"] = round(rd + ad, 2), round(rc + ac, 2)
        row["balance"] = round(adjusted if acc["type"] in DEBIT_NORMAL else -adjusted, 2)
        rows.append(row)

    totals = {k: round(sum(r[k] for r in rows), 2) for k in COLS}

    # --- Net income row: balances the Income Statement, carries into Owner's Equity ---
    ni = round(totals["i_cr"] - totals["i_dr"], 2)
    ni_row = dict.fromkeys(COLS, 0.0)
    if ni >= 0:
        ni_row["i_dr"] = ni_row["o_cr"] = ni
    else:
        ni_row["i_cr"] = ni_row["o_dr"] = -ni

    final = dict(totals)
    for k in ("i_dr", "i_cr", "o_dr", "o_cr"):
        final[k] = round(totals[k] + ni_row[k], 2)

    # --- Ending equity row: balances Owner's Equity, carries into Balance Sheet ---
    equity_end = round(final["o_cr"] - final["o_dr"], 2)
    end_row = dict.fromkeys(COLS, 0.0)
    if equity_end >= 0:
        end_row["o_dr"] = end_row["b_cr"] = equity_end
    else:
        end_row["o_cr"] = end_row["b_dr"] = -equity_end
    for k in ("o_dr", "o_cr", "b_dr", "b_cr"):
        final[k] = round(final[k] + end_row[k], 2)

    return {"rows": rows, "totals": totals, "ni": ni, "ni_row": ni_row,
            "end_row": end_row, "final": final, "equity_end": equity_end}


# ============================================================================
# 5. MAIN APP CLASS
# ============================================================================

class AccountingApp(tk.Tk):
    """Main window: a sidebar notebook with 6 tabs, all driven by self.accounts / transactions / rules."""

    # ------------------------------------------------------------------------
    # 5.1  SETUP & STYLE
    # ------------------------------------------------------------------------

    def __init__(self):
        """Load data, build every tab, and set up lazy refreshing (a tab refreshes only when opened)."""
        super().__init__()
        self.title("Automated Accounting System")
        self.geometry("1280x720")
        self.apply_style()
        self.accounts, self.transactions, self.rules = load_data()
        self.ws = None  # cached worksheet result

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        for build in (self.build_new_transaction_page, self.build_ledger_page, self.build_accounts_page,
                      self.build_history_page, self.build_adjustments_page, self.build_worksheet_page):
            build()

        # One refresher per tab, in the SAME order as the tabs above (None = nothing to refresh)
        self.page_refreshers = [None, self.refresh_ledger, self.refresh_accounts, self.refresh_history,
                                self.refresh_adjustments, self.refresh_worksheet]
        self.dirty = set()  # indexes of tabs that need redrawing
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_tab(self.notebook.index("current")))
        self.refresh_all()

    def apply_style(self):
        """Dark left sidebar for the tabs, plus a light color theme for the rest."""
        s = ttk.Style(self)
        s.theme_use("clam")  # 'clam' is needed so the tabs can be moved to the side on every OS
        self.configure(bg="#1b2631")
        s.configure(".", background="#eaf2f8", font=("Segoe UI", 10))
        s.configure("TNotebook", tabposition="wn", background="#1b2631", borderwidth=0,
                    tabmargins=(0, 10, 0, 0))
        s.configure("TNotebook.Tab", background="#1b2631", foreground="#d6eaf8", borderwidth=0,
                    padding=(16, 14), width=22, anchor="w", font=("Segoe UI", 11, "bold"))
        s.map("TNotebook.Tab", background=[("selected", "#2e86c1"), ("active", "#34495e")],
              foreground=[("selected", "white")])
        s.configure("Treeview", rowheight=26, background="white", fieldbackground="white")
        s.configure("Treeview.Heading", background="#2e86c1", foreground="white", font=("Segoe UI", 10, "bold"))
        s.map("Treeview", background=[("selected", "#aed6f1")], foreground=[("selected", "black")])
        s.configure("TButton", padding=(10, 6))

    def save(self):
        """Save current data to disk."""
        save_data(self.accounts, self.transactions, self.rules)

    # ------------------------------------------------------------------------
    # 5.2  SHARED UI HELPERS  (used by several tabs)
    # ------------------------------------------------------------------------

    def make_page(self, title, purpose):
        """Create a tab with its icon title and a purpose note at the top; returns the page frame."""
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text=f"  {ICONS.get(title, '')}   {title}")
        ttk.Label(page, text=f"PURPOSE: {purpose}", foreground="#1a5276", wraplength=1000,
                  font=("Arial", 10, "italic")).pack(anchor="w", pady=(0, 10))
        return page

    def make_table(self, parent, columns, widths, right_from=None):
        """Treeview with a vertical scrollbar. Columns from index right_from are right-aligned."""
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for i, (col, w) in enumerate(zip(columns, widths)):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="e" if right_from is not None and i >= right_from else "w")
        vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        return tree

    @staticmethod
    def add_field(form, row, label, var, values=None, readonly=False, width=35):
        """One 'label + entry/combobox' row in a form grid."""
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
        if values is None:
            w = ttk.Entry(form, textvariable=var, width=width)
        else:
            w = ttk.Combobox(form, textvariable=var, values=values, width=width - 3,
                             state="readonly" if readonly else "normal")
        w.grid(row=row, column=1, pady=4)
        return w

    def find_account(self, name):
        """Case-insensitive account lookup; returns the account dict or None."""
        name = name.strip().lower()
        return next((a for a in self.accounts if a["name"].lower() == name), None)

    def next_id(self):
        """Next transaction number (highest existing id + 1)."""
        return max((t["id"] for t in self.transactions), default=0) + 1

    def check_entry(self, date, desc, debit, credit, amount_text):
        """Validate fields shared by daily and adjusting entries. Returns the amount, or None after a warning."""
        def warn(title, msg):
            messagebox.showwarning(title, msg)  # returns None, so callers can `return warn(...)`

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return warn("Bad date", "Date must look like 2026-10-22.")
        if not desc or not debit or not credit:
            return warn("Missing info", "Enter a description, a debit account and a credit account.")
        if debit.lower() == credit.lower():
            return warn("Same account", "Debit and credit accounts must be different.")
        try:
            amount = float(amount_text.replace(",", ""))
            if amount <= 0:
                raise ValueError
        except ValueError:
            return warn("Bad amount", "Amount must be a number greater than 0.")
        return round(amount, 2)

    # ------------------------------------------------------------------------
    # 5.3  TAB: NEW TRANSACTION
    # ------------------------------------------------------------------------

    def build_new_transaction_page(self):
        """Form for daily transactions: person, date, description, debit/credit accounts, amount."""
        page = self.make_page(
            "New Transaction",
            "Record a DAILY transaction: who is recording it, the date, a description, the account to DEBIT, "
            "the account to CREDIT, and the amount. It is posted to the Ledger, History and Unadjusted Trial "
            "Balance automatically. (End-of-period adjustments go on the Adjustments tab.)")
        form = ttk.Frame(page)
        form.pack(anchor="w")
        self.var_person, self.var_desc, self.var_debit, self.var_credit, self.var_amount = \
            (tk.StringVar() for _ in range(5))
        self.var_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        self.add_field(form, 0, "Person (who is inputting):", self.var_person)
        self.add_field(form, 1, "Date (YYYY-MM-DD):", self.var_date)
        self.add_field(form, 2, "Description:", self.var_desc)
        self.cmb_debit = self.add_field(form, 3, "Debit Account:", self.var_debit, [], readonly=True)
        self.cmb_credit = self.add_field(form, 4, "Credit Account:", self.var_credit, [], readonly=True)
        self.add_field(form, 5, "Amount:", self.var_amount)
        ttk.Button(form, text="Record Transaction", command=self.record_transaction) \
            .grid(row=6, column=1, sticky="w", pady=12)

    def record_transaction(self):
        """Validate the form, store the transaction as 'regular', save, and refresh all tabs."""
        person, date, desc = self.var_person.get().strip(), self.var_date.get().strip(), self.var_desc.get().strip()
        debit, credit = self.var_debit.get(), self.var_credit.get()
        if not person:
            return messagebox.showwarning("Missing info", "Please enter the person.")
        amount = self.check_entry(date, desc, debit, credit, self.var_amount.get())
        if amount is None:
            return
        self.transactions.append({"id": self.next_id(), "kind": "regular", "person": person, "date": date,
                                  "description": desc, "debit": debit, "credit": credit, "amount": amount})
        self.save()
        for v in (self.var_desc, self.var_amount, self.var_debit, self.var_credit):
            v.set("")  # clear the form (person and date stay for the next entry)
        self.refresh_all()
        messagebox.showinfo("Saved", "Transaction recorded and posted to the Ledger and Worksheet.")

    # ------------------------------------------------------------------------
    # 5.4  TAB: LEDGER
    # ------------------------------------------------------------------------

    def build_ledger_page(self):
        """Account picker on top, the account's ledger table below, totals at the bottom."""
        page = self.make_page(
            "Ledger",
            "Choose an account to see its ledger. Each transaction is posted to the account debited "
            "(Debit column) and the account credited (Credit column). Adjusting entries are marked [ADJ].")
        self.lbl_totals = ttk.Label(page, font=("Arial", 10, "bold"))
        self.lbl_totals.pack(side="bottom", anchor="e", pady=6)

        top = ttk.Frame(page)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Account:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 8))
        self.var_ledger_acc = tk.StringVar()
        self.cmb_ledger = ttk.Combobox(top, textvariable=self.var_ledger_acc, state="readonly", font=("Arial", 14))
        self.cmb_ledger.pack(side="left", fill="x", expand=True)
        self.cmb_ledger.bind("<<ComboboxSelected>>", lambda e: self.show_account_ledger())

        self.lbl_ledger_title = ttk.Label(page, font=("Arial", 11, "bold"), justify="left")
        self.lbl_ledger_title.pack(anchor="w", pady=(0, 6), fill="x")
        self.tree_ledger = self.make_table(page, ("Date", "Description", "Debit", "Credit", "Balance"),
                                           (100, 430, 130, 130, 140), right_from=2)
        self.lbl_account_totals = ttk.Label(page, font=("Arial", 10, "bold"))
        self.lbl_account_totals.pack(anchor="e", pady=6)

    def refresh_ledger(self):
        """Reload the account list (keeping the current choice) and the grand totals."""
        names = [a["name"] for a in self.accounts]
        self.cmb_ledger["values"] = names
        self.cmb_ledger.configure(height=min(max(len(names), 1), 15))
        current = self.var_ledger_acc.get()
        self.var_ledger_acc.set(current if current in names else (names[0] if names else ""))
        self.show_account_ledger()
        grand = sum(t["amount"] for t in self.transactions)
        self.lbl_totals.config(text=f"All Accounts - Total Debit: {grand:,.2f}    Total Credit: {grand:,.2f}")

    def show_account_ledger(self):
        """Fill the table with the chosen account's entries (by date) and a running balance."""
        self.tree_ledger.delete(*self.tree_ledger.get_children())
        acc = self.find_account(self.var_ledger_acc.get())
        if acc is None:
            self.lbl_ledger_title.config(text="No account selected")
            self.lbl_account_totals.config(text="")
            return
        self.lbl_ledger_title.config(text=f"{acc['name']}  ({acc['type']})")

        debit_normal = acc["type"] in DEBIT_NORMAL
        total_dr = total_cr = balance = 0.0
        for t in sorted(self.transactions, key=lambda x: (x["date"], x["id"])):
            is_dr = t["debit"] == acc["name"]
            if not is_dr and t["credit"] != acc["name"]:
                continue  # entry doesn't touch this account
            amt = t["amount"]
            # Balance goes up when the entry is on the account's normal side, down otherwise
            balance += amt if is_dr == debit_normal else -amt
            if is_dr:
                total_dr += amt
            else:
                total_cr += amt
            tag = "[ADJ] " if t.get("kind") == "adjusting" else ""
            self.tree_ledger.insert("", "end", values=(
                t["date"], tag + t["description"],
                f"{amt:,.2f}" if is_dr else "", "" if is_dr else f"{amt:,.2f}", money(balance)))
        self.lbl_account_totals.config(
            text=f"Total Debit: {total_dr:,.2f}    Total Credit: {total_cr:,.2f}    Balance: {money(balance)}")

    # ------------------------------------------------------------------------
    # 5.5  TAB: ACCOUNTS
    # ------------------------------------------------------------------------

    def build_accounts_page(self):
        """Accounts table plus a small form to add accounts and a button to delete one."""
        page = self.make_page(
            "Accounts",
            "Every account and its current balance (daily + adjusting entries). You can add or delete accounts. "
            "The type decides the worksheet columns: Asset / Contra Asset / Liability -> Balance Sheet, "
            "Equity / Drawings -> Owner's Equity, Revenue / Expense -> Income Statement.")
        self.tree_accounts = self.make_table(
            page, ("Account", "Type", "Total Debit", "Total Credit", "Balance"),
            (260, 120, 140, 140, 140), right_from=2)

        add = ttk.Frame(page)
        add.pack(anchor="w", pady=10)
        self.var_new_acc = tk.StringVar()
        self.var_new_type = tk.StringVar(value="Asset")
        ttk.Label(add, text="New account name:").grid(row=0, column=0, padx=4)
        ttk.Entry(add, textvariable=self.var_new_acc, width=25).grid(row=0, column=1, padx=4)
        ttk.Label(add, text="Type:").grid(row=0, column=2, padx=4)
        ttk.Combobox(add, textvariable=self.var_new_type, values=TYPE_ORDER, width=14,
                     state="readonly").grid(row=0, column=3, padx=4)
        ttk.Button(add, text="Add Account", command=self.add_account).grid(row=0, column=4, padx=4)
        ttk.Button(add, text="Delete Selected Account", command=self.delete_account).grid(row=0, column=5, padx=20)

    def add_account(self):
        """Add a new account (name must be non-empty and unique)."""
        name = self.var_new_acc.get().strip()
        if not name:
            return messagebox.showwarning("Missing name", "Enter an account name.")
        if self.find_account(name):
            return messagebox.showwarning("Duplicate", "That account already exists.")
        self.accounts.append({"name": name, "type": self.var_new_type.get()})
        self.save()
        self.var_new_acc.set("")
        self.refresh_all()

    def delete_account(self):
        """Delete the selected account, but only if no transaction or rule uses it."""
        selected = self.tree_accounts.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click an account in the list first.")
        idx = int(selected[0])  # row id = index in self.accounts
        acc = self.accounts[idx]
        uses = lambda items: any(x["debit"] == acc["name"] or x["credit"] == acc["name"] for x in items)
        if uses(self.transactions):
            return messagebox.showwarning(
                "Account in use", f"'{acc['name']}' has recorded transactions and can't be deleted.\n"
                                  "Delete those transactions first (Transaction History tab).")
        if uses(self.rules):
            return messagebox.showwarning(
                "Account in use", f"'{acc['name']}' is used by a recurring adjustment rule. Delete the rule first.")
        if not messagebox.askyesno("Confirm delete", f"Delete account '{acc['name']}' ({acc['type']})?"):
            return
        del self.accounts[idx]
        for var in (self.var_debit, self.var_credit):
            if var.get() == acc["name"]:
                var.set("")  # don't leave a deleted account selected in the form
        self.save()
        self.refresh_all()
        messagebox.showinfo("Deleted", "Account deleted.")

    def refresh_accounts(self):
        """Redraw the table using totals/balances from the worksheet result."""
        self.tree_accounts.delete(*self.tree_accounts.get_children())
        by_name = {r["name"]: r for r in self.ws["rows"]}
        for i, acc in enumerate(self.accounts):
            r = by_name[acc["name"]]
            self.tree_accounts.insert("", "end", iid=str(i), values=(
                acc["name"], acc["type"], f"{r['p_dr']:,.2f}", f"{r['p_cr']:,.2f}", money(r["balance"])))

    # ------------------------------------------------------------------------
    # 5.6  TAB: TRANSACTION HISTORY
    # ------------------------------------------------------------------------

    def build_history_page(self):
        """Table of all entries (newest first) with a delete button."""
        page = self.make_page(
            "Transaction History",
            "Every entry as it was entered (daily and adjusting), including who entered it. "
            "Use it to check past entries or to delete a wrong one.")
        self.tree_history = self.make_table(
            page, ("No.", "Type", "Date", "Person", "Description", "Debit Account", "Credit Account", "Amount"),
            (50, 80, 100, 130, 300, 180, 180, 110), right_from=7)
        ttk.Button(page, text="Delete Selected Transaction", command=self.delete_transaction).pack(anchor="w", pady=8)

    def refresh_history(self):
        """Redraw the table, newest entry first."""
        self.tree_history.delete(*self.tree_history.get_children())
        for t in reversed(self.transactions):
            self.tree_history.insert("", "end", values=(
                t["id"], "Adjusting" if t.get("kind") == "adjusting" else "Daily", t["date"], t["person"],
                t["description"], t["debit"], t["credit"], f"{t['amount']:,.2f}"))

    def delete_transaction(self):
        """Delete the selected transaction, then renumber all ids so there are no gaps."""
        selected = self.tree_history.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click a transaction in the list first.")
        trans_id = int(self.tree_history.item(selected[0], "values")[0])
        if not messagebox.askyesno(
                "Confirm delete", f"Delete transaction No. {trans_id}?\nThis also removes it from the Ledger, "
                                  "the Worksheet and the account balances."):
            return
        self.transactions = [t for t in self.transactions if t["id"] != trans_id]
        for new_id, t in enumerate(self.transactions, start=1):
            t["id"] = new_id
        self.save()
        self.refresh_all()
        messagebox.showinfo("Deleted", "Transaction deleted.")

    # ------------------------------------------------------------------------
    # 5.7  TAB: ADJUSTMENTS
    # ------------------------------------------------------------------------

    def build_adjustments_page(self):
        """Adjustment form (with templates) on top, recurring-rules table and buttons below."""
        page = self.make_page(
            "Adjustments",
            "Post end-of-period ADJUSTING entries. Pick an adjustment type and the accounts are filled in "
            "(missing accounts are created automatically); enter the amount and post. Use 'Save as Recurring "
            "Rule' for adjustments that repeat every period, then 'Apply All Rules' posts them in one click. "
            "Adjustments flow into the Adjustments columns of the Worksheet.")
        form = ttk.Frame(page)
        form.pack(anchor="w")
        self.var_adj_template = tk.StringVar(value=list(ADJUSTMENT_TEMPLATES)[0])
        self.var_adj_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.var_adj_desc, self.var_adj_debit, self.var_adj_credit, self.var_adj_amount = \
            (tk.StringVar() for _ in range(4))

        cmb = self.add_field(form, 0, "Adjustment type:", self.var_adj_template,
                             list(ADJUSTMENT_TEMPLATES), readonly=True, width=43)
        cmb.bind("<<ComboboxSelected>>", lambda e: self.apply_template())
        self.add_field(form, 1, "Period-end date (YYYY-MM-DD):", self.var_adj_date, width=43)
        self.add_field(form, 2, "Description:", self.var_adj_desc, width=43)
        self.cmb_adj_debit = self.add_field(form, 3, "Debit Account:", self.var_adj_debit, [], width=43)
        self.cmb_adj_credit = self.add_field(form, 4, "Credit Account:", self.var_adj_credit, [], width=43)
        self.add_field(form, 5, "Amount:", self.var_adj_amount, width=43)

        btns = ttk.Frame(form)
        btns.grid(row=6, column=1, sticky="w", pady=10)
        ttk.Button(btns, text="Post Adjustment", command=self.post_adjustment).pack(side="left")
        ttk.Button(btns, text="Save as Recurring Rule", command=self.save_rule).pack(side="left", padx=10)

        ttk.Label(page, text="Recurring adjustment rules", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 4))
        self.tree_rules = self.make_table(
            page, ("Type", "Debit Account", "Credit Account", "Amount", "Description"), (250, 180, 200, 110, 350))
        rbtns = ttk.Frame(page)
        rbtns.pack(anchor="w", pady=8)
        ttk.Button(rbtns, text="Apply All Rules (uses the period-end date above)",
                   command=self.apply_rules).pack(side="left")
        ttk.Button(rbtns, text="Delete Selected Rule", command=self.delete_rule).pack(side="left", padx=10)
        self.apply_template()  # fill the form with the first template

    def apply_template(self):
        """Fill debit, credit and description from the selected adjustment type."""
        d, _, c, _, desc = ADJUSTMENT_TEMPLATES[self.var_adj_template.get()]
        self.var_adj_debit.set(d)
        self.var_adj_credit.set(c)
        self.var_adj_desc.set(desc)

    def read_adjustment_form(self):
        """Validate the adjustment form. Returns an entry dict or None.

        debit_type / credit_type are set only when the account still matches the template's
        default, so post_entry knows it may auto-create that account.
        """
        date, desc = self.var_adj_date.get().strip(), self.var_adj_desc.get().strip()
        debit, credit = self.var_adj_debit.get().strip(), self.var_adj_credit.get().strip()
        amount = self.check_entry(date, desc, debit, credit, self.var_adj_amount.get())
        if amount is None:
            return None
        template = self.var_adj_template.get()
        d_def, d_type, c_def, c_type, _ = ADJUSTMENT_TEMPLATES[template]
        return {"template": template, "date": date, "description": desc, "debit": debit, "credit": credit,
                "amount": amount, "debit_type": d_type if debit.lower() == d_def.lower() else None,
                "credit_type": c_type if credit.lower() == c_def.lower() else None}

    def post_entry(self, e):
        """Post one adjusting entry (creating missing template accounts). Returns an error message, or None on success."""
        if e["debit"].lower() == e["credit"].lower():
            return "Debit and credit accounts must be different."
        accs = []
        for side in ("debit", "credit"):
            acc = self.find_account(e[side])
            if acc is None and e.get(side + "_type") not in TYPE_ORDER:
                return f"Account '{e[side]}' doesn't exist. Pick an existing account or use the template's account."
            accs.append(acc)
        # Only create accounts after BOTH sides passed validation
        for i, side in enumerate(("debit", "credit")):
            if accs[i] is None:
                accs[i] = {"name": e[side].strip(), "type": e[side + "_type"]}
                self.accounts.append(accs[i])
        self.transactions.append({
            "id": self.next_id(), "kind": "adjusting", "person": "System (Adjusting)", "date": e["date"],
            "description": e["description"], "debit": accs[0]["name"], "credit": accs[1]["name"],
            "amount": e["amount"]})
        return None

    def post_adjustment(self):
        """'Post Adjustment' button: validate the form, post the entry, save, refresh."""
        e = self.read_adjustment_form()
        if e is None:
            return
        err = self.post_entry(e)
        if err:
            return messagebox.showwarning("Cannot post", err)
        self.save()
        self.var_adj_amount.set("")
        self.refresh_all()
        messagebox.showinfo("Posted", "Adjusting entry posted. The Worksheet has been updated.")

    def save_rule(self):
        """Save the current form as a recurring rule (amount included; date is chosen when applying)."""
        e = self.read_adjustment_form()
        if e is None:
            return
        self.rules.append({k: e[k] for k in
                           ("template", "debit", "credit", "debit_type", "credit_type", "amount", "description")})
        self.save()
        self.refresh_all()

    def delete_rule(self):
        """Delete the selected recurring rule."""
        selected = self.tree_rules.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click a rule in the list first.")
        del self.rules[int(selected[0])]
        self.save()
        self.refresh_all()

    def apply_rules(self):
        """Post every rule at the period-end date; entries already posted for that date are skipped."""
        date = self.var_adj_date.get().strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return messagebox.showwarning("Bad date", "Enter a valid period-end date (YYYY-MM-DD) first.")
        if not self.rules:
            return messagebox.showinfo("No rules", "There are no recurring rules yet.")

        posted = skipped = 0
        errors = []
        for r in self.rules:
            # Same date + description + accounts + amount = already posted, so don't double up
            duplicate = any(
                t.get("kind") == "adjusting" and t["date"] == date and t["description"] == r["description"]
                and t["debit"].lower() == r["debit"].lower() and t["credit"].lower() == r["credit"].lower()
                and abs(t["amount"] - r["amount"]) < EPS for t in self.transactions)
            if duplicate:
                skipped += 1
                continue
            err = self.post_entry(dict(r, date=date))
            if err:
                errors.append(err)
            else:
                posted += 1
        self.save()
        self.refresh_all()
        msg = f"Posted {posted} adjusting entr{'y' if posted == 1 else 'ies'} dated {date}."
        if skipped:
            msg += f"\nSkipped {skipped} already posted for that date."
        if errors:
            msg += "\n\nProblems:\n" + "\n".join(errors)
        messagebox.showinfo("Rules applied", msg)

    def refresh_adjustments(self):
        """Refresh the account dropdowns and the rules table."""
        names = [a["name"] for a in self.accounts]
        self.cmb_adj_debit["values"] = self.cmb_adj_credit["values"] = names
        self.tree_rules.delete(*self.tree_rules.get_children())
        for i, r in enumerate(self.rules):
            self.tree_rules.insert("", "end", iid=str(i), values=(
                r["template"], r["debit"], r["credit"], f"{r['amount']:,.2f}", r["description"]))

    # ------------------------------------------------------------------------
    # 5.8  TAB: WORKSHEET
    # ------------------------------------------------------------------------

    def build_worksheet_page(self):
        """A scrollable Canvas (the worksheet is drawn by hand) plus a summary line."""
        page = self.make_page(
            "Worksheet",
            "The 12-column worksheet, built automatically from your entries. Net income is pulled into the "
            "Owner's Equity columns, and ending owner's equity is pulled into the Balance Sheet columns.")
        self.lbl_ws_summary = ttk.Label(page, font=("Arial", 10, "bold"))
        self.lbl_ws_summary.pack(side="bottom", anchor="w", pady=6)

        frame = ttk.Frame(page)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        c = self.ws_canvas = tk.Canvas(frame, highlightthickness=0, background="white")
        vs = ttk.Scrollbar(frame, orient="vertical", command=c.yview)
        hs = ttk.Scrollbar(frame, orient="horizontal", command=c.xview)
        c.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        c.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        # Mouse wheel scrolling (Windows/Mac use <MouseWheel>, Linux uses Button-4/5)
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))

    def refresh_worksheet(self):
        """Redraw the whole worksheet on the canvas from self.ws (headers, account rows, totals, final row)."""
        ws, c = self.ws, self.ws_canvas
        c.delete("all")
        NAME_W, COL_W, ROW_H = 230, 105, 26  # layout sizes in pixels
        LINE, HEAD, TOTAL, PULL = "#2c3e50", "#d6eaf8", "#aed6f1", "#fcf3cf"  # border / header / totals / pulled-row colors

        def cell(x0, y0, x1, y1, text, bg, bold=False, align="e"):
            """Draw one ruled cell with text aligned 'w' (left), 'e' (right) or 'center'."""
            c.create_rectangle(x0 + 1, y0 + 1, x1 + 1, y1 + 1, fill=bg, outline=LINE)
            if text:
                x = {"w": x0 + 8, "e": x1 - 8, "center": (x0 + x1) / 2}[align]
                c.create_text(x + 1, (y0 + y1) / 2 + 1, text=text, font=("Arial", 10, "bold" if bold else "normal"),
                              anchor="center" if align == "center" else align)

        # --- Header: account column + 6 group titles, each split into Debit / Credit ---
        cell(0, 0, NAME_W, 2 * ROW_H, "Account", HEAD, True, "center")
        for i, name in enumerate(GROUPS):
            x0 = NAME_W + i * 2 * COL_W
            cell(x0, 0, x0 + 2 * COL_W, ROW_H, name, HEAD, True, "center")
            cell(x0, ROW_H, x0 + COL_W, 2 * ROW_H, "Debit", HEAD, True, "center")
            cell(x0 + COL_W, ROW_H, x0 + 2 * COL_W, 2 * ROW_H, "Credit", HEAD, True, "center")

        def put_row(r, name, d, bg="white", bold=False):
            """Draw one full worksheet row (name + 12 amount cells); zeros are left blank."""
            y0, y1 = r * ROW_H, (r + 1) * ROW_H
            cell(0, y0, NAME_W, y1, name, bg, bold, "w")
            for k, col in enumerate(COLS):
                x0 = NAME_W + k * COL_W
                cell(x0, y0, x0 + COL_W, y1, "" if abs(d[col]) < EPS else f"{d[col]:,.2f}", bg, bold)

        # --- Body: account rows, then totals, net income, ending equity, final totals ---
        r = 2
        for row in ws["rows"]:
            put_row(r, row["name"], row)
            r += 1
        put_row(r, "TOTALS", ws["totals"], TOTAL, True)
        put_row(r + 1, "Net Income" if ws["ni"] >= 0 else "Net Loss", ws["ni_row"], PULL, True)
        put_row(r + 2, "Ending Owner's Equity", ws["end_row"], PULL, True)

        f = ws["final"]
        balanced = all(abs(f[p + "_dr"] - f[p + "_cr"]) < EPS for p in "ujaiob")
        put_row(r + 3, "FINAL TOTALS", f, "#d5f5e3" if balanced else "#f5b7b1", True)  # green = balanced, red = not
        c.configure(scrollregion=(0, 0, NAME_W + 12 * COL_W + 2, (r + 4) * ROW_H + 2))

        self.lbl_ws_summary.config(
            text=f"{'Net Income' if ws['ni'] >= 0 else 'Net Loss'}: {abs(ws['ni']):,.2f}     "
                 f"Ending Owner's Equity: {money(ws['equity_end'])}     "
                 f"Worksheet: {'BALANCED' if balanced else 'OUT OF BALANCE'}")

    # ------------------------------------------------------------------------
    # 5.9  REFRESH CONTROL  (keeps every tab up to date)
    # ------------------------------------------------------------------------

    def refresh_all(self):
        """Call after ANY data change: rebuild the worksheet, mark all tabs dirty, redraw the visible one."""
        names = [a["name"] for a in self.accounts]
        self.cmb_debit["values"] = self.cmb_credit["values"] = names
        self.ws = build_worksheet(self.accounts, self.transactions)
        self.dirty = set(range(len(self.page_refreshers)))
        self.refresh_tab(self.notebook.index("current"))

    def refresh_tab(self, idx):
        """Redraw tab number idx only if it is marked dirty (so hidden tabs update when opened)."""
        if idx in self.dirty:
            if self.page_refreshers[idx]:
                self.page_refreshers[idx]()
            self.dirty.discard(idx)


# ============================================================================
# 6. PROGRAM ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    AccountingApp().mainloop()


# ============================================================================
# 7. QUICK GLOSSARY  (what the common words in this file mean)
# ============================================================================
#
# --- PYTHON BASICS ---------------------------------------------------------
# def          Starts a function:  def money(v):  ->  call it with money(5)
# class        A blueprint for an object. AccountingApp is the blueprint of our window.
# self         "This very window/object". Inside a class, self.accounts means the
#              accounts that belong to this window. Every method must list self first.
# __init__     Runs automatically once when the object is created, e.g. AccountingApp().
#              We use it to load data and build the tabs.
# method       A def that lives inside a class (record_transaction, refresh_ledger...).
# return       Sends a value back. A bare "return" just stops the function early.
# lambda       A tiny one-line function, e.g. lambda e: self.apply_template().
# @staticmethod  A method that doesn't need self (add_field).
# """text"""   Docstring: the description shown for a function/class/file.
# # text       A normal comment, ignored by Python.
# if __name__ == "__main__":   Runs the app only when this file is run directly,
#                              not when it is imported by another file.
#
# --- IMPORTS ---------------------------------------------------------------
# json         Saves/loads data as text in a .json file (json.dump / json.load).
# os           Talks to the computer; os.path.exists checks if a file exists.
# tkinter (tk) Python's built-in window/GUI library (windows, buttons, canvas).
# ttk          Newer "themed" widgets inside tkinter: ttk.Frame, ttk.Label,
#              ttk.Button, ttk.Entry, ttk.Combobox, ttk.Treeview, ttk.Notebook.
# messagebox   Pop-up boxes: showinfo, showwarning, askyesno.
# datetime     Dates. strptime checks "YYYY-MM-DD"; now() gives today's date.
#
# --- GUI WORDS (tkinter) ---------------------------------------------------
# widget       Any screen item (button, label, text box, table).
# Tk / tk.Tk   The main window. AccountingApp(tk.Tk) means "our app IS a window".
# Frame        An invisible box used to group other widgets.
# Notebook     The tab container; each page is one tab (shown as the sidebar).
# Treeview     A table with rows and columns (ledger, history, accounts).
# Combobox     A dropdown list. state="readonly" = pick only, no typing.
# Entry        A one-line text box.
# Canvas       A blank drawing area; the Worksheet is drawn on it cell by cell.
# StringVar    A box holding text that is linked to a widget. .get() reads it,
#              .set("x") changes it.
# .configure() / .config()  Changes a widget's settings after it is created
#              (text, colors, fonts, values).
# Style        ttk.Style sets colors/fonts for all widgets of one kind.
# .bind()      "When this event happens, run this function" (click, select, scroll).
# command=     The function a button runs when clicked.
#
# --- LAYOUT (how widgets are placed) ---------------------------------------
# .pack()      Stacks widgets (side="left"/"bottom", fill, expand, anchor).
# .grid()      Places widgets in rows and columns (row=, column=, sticky=).
# padx / pady  Space around a widget (horizontal / vertical).
# anchor / sticky  Which edge/corner the widget sticks to: "w"=left, "e"=right,
#              "n"=top, "s"=bottom, "nsew"=stretch in all directions.
#
# --- DATA TYPES USED IN THIS FILE ------------------------------------------
# str          Text:     "Cash"
# float        Decimal:  1250.50 (money amounts)
# int          Whole number: 3 (ids, row numbers)
# bool         True / False
# None         "Nothing / no value" (e.g. check_entry returns None on error)
# list  [ ]    Ordered items you can change:  accounts, transactions, rules
# tuple ( )    Ordered items that can't change: TYPE_ORDER, COLS
# dict  { }    Key -> value pairs:  {"name": "Cash", "type": "Asset"}
# set          Unique items only: self.dirty (tabs that need redrawing)
#
# --- OTHER SYNTAX YOU WILL SEE ---------------------------------------------
# f"..{x}.."   f-string: puts the value of x inside the text.
# f"{n:,.2f}"  Format a number with commas and 2 decimals (1,250.50).
# [x for ...]  List comprehension: builds a list in one line.
# t.get("kind")  Read a dict key safely (gives None instead of an error if missing).
# *args        "*" unpacks a list into separate arguments (delete(*children)).
# a, b = x, y  Assign several variables at once.
# try / except Try something; if it fails (e.g. a bad date), run the except part.
# with open()  Opens a file and closes it automatically afterwards.
#
# --- QUICK DATA FLOW -------------------------------------------------------
# User input -> self.transactions (list of dicts) -> save() writes the JSON file
# -> refresh_all() runs build_worksheet() -> every tab redraws from the result.
