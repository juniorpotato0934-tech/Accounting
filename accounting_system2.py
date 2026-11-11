"""
Group 1 System: Automated Accounting System with 12-Column Worksheet (GUI)

Tabs: New Transaction | Ledger | Accounts | Transaction History | Adjustments | Worksheet
The worksheet is built automatically from the entries:
  daily entries -> Unadjusted TB, adjusting entries -> Adjustments, both -> Adjusted TB,
  then each account goes to Income Statement / Owner's Equity / Balance Sheet by its type.
Data is saved to 'accounting_data.json' (same folder). Needs only Python 3 (tkinter included).
"""

import json                                   # I use this to save/load my data as a JSON file
import os                                     # I use this to check if the data file already exists
import tkinter as tk                          # I use tkinter to build the whole window
from tkinter import ttk, messagebox           # ttk gives me nicer widgets, messagebox gives me popups
from datetime import datetime                 # I use this to validate and generate dates

#DATA & CONSTANTS
DATA_FILE = "accounting_data.json"            # the file where I store everything
EPS = 0.005  # tolerance for money comparisons  # I treat anything smaller than half a cent as zero

# the order I want accounts to appear in the worksheet
TYPE_ORDER = ["Asset", "Contra Asset", "Liability", "Equity", "Drawings", "Revenue", "Expense"]
DEBIT_NORMAL = ("Asset", "Drawings", "Expense")   # balance rises with a debit (all others: credit)
IS_TYPES = ("Revenue", "Expense")                 # Income Statement
OE_TYPES = ("Equity", "Drawings")                 # Owner's Equity (the rest -> Balance Sheet)

# I generate the 12 column keys: u_dr, u_cr, j_dr, j_cr, ... (u=unadjusted, j=adjustments, a=adjusted, i=income stmt, o=owner's equity, b=balance sheet)
COLS = [p + s for p in ("u", "j", "a", "i", "o", "b") for s in ("_dr", "_cr")]  # 12 worksheet columns
# the six group headings shown above each Debit/Credit pair
GROUPS = ("Unadjusted Trial Balance", "Adjustments", "Adjusted Trial Balance",
          "Income Statement", "Owner's Equity", "Balance Sheet")

# the starter chart of accounts I give a new user
DEFAULT_ACCOUNTS = [{"name": n, "type": t} for n, t in [
    ("Cash", "Asset"), ("Accounts Receivable", "Asset"), ("Supplies", "Asset"),
    ("Prepaid Expenses", "Asset"), ("Equipment", "Asset"),
    ("Accumulated Depreciation", "Contra Asset"),
    ("Accounts Payable", "Liability"), ("Salaries Payable", "Liability"), ("Unearned Revenue", "Liability"),
    ("Owner's Capital", "Equity"), ("Owner's Drawings", "Drawings"), ("Sales Revenue", "Revenue"),
    ("Rent Expense", "Expense"), ("Salaries Expense", "Expense"), ("Utilities Expense", "Expense"),
    ("Supplies Expense", "Expense"), ("Insurance Expense", "Expense"), ("Depreciation Expense", "Expense")]]

# Adjustment templates: (debit account, its type, credit account, its type, description).
# Missing accounts are created automatically with the type shown.
# my ready-made adjusting entries so I don't retype the accounts every time
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
    "Custom adjustment": ("", None, "", None, ""),   # blank so I can fill in my own accounts
}


def load_data():
    # I load saved data if the file exists; otherwise I start fresh with the default accounts
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)                       # data = everything I saved last time
        transactions = data.get("transactions", [])
        for t in transactions:
            t.setdefault("kind", "regular")           # older entries without a kind count as daily entries
        return (data.get("accounts") or [dict(a) for a in DEFAULT_ACCOUNTS]), transactions, data.get("rules", [])
    return [dict(a) for a in DEFAULT_ACCOUNTS], [], []


def save_data(accounts, transactions, rules):
    # I write accounts, transactions and rules to the JSON file
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts, "transactions": transactions, "rules": rules}, f, indent=2)


#  ACCOUNTING ENGINE
def money(v):
    """Format a number; negatives in parentheses."""
    # I show negatives like (1,000.00) the way accountants do
    return f"({-v:,.2f})" if v < -EPS else f"{v:,.2f}"


def split_dr_cr(net):
    """Net (debits - credits): positive -> Debit column, negative -> Credit column."""
    # I turn one net number into a (debit, credit) pair
    net = round(net, 2)
    return (net, 0.0) if net > 0 else (0.0, -net)


def build_worksheet(accounts, transactions):
    """Build the 12-column worksheet; returns rows, totals, net income, ending equity."""
    # ordered = my accounts sorted by type so the worksheet is grouped properly
    ordered = sorted(accounts, key=lambda a: TYPE_ORDER.index(a["type"]) if a["type"] in TYPE_ORDER else 99)

    # Debit/credit totals per account, split into daily ("reg") and adjusting ("adj")
    # tot = my running totals per account for each of the four buckets
    tot = {k: {} for k in ("reg_dr", "reg_cr", "adj_dr", "adj_cr")}
    for t in transactions:
        p = "adj" if t.get("kind") == "adjusting" else "reg"   # p = which bucket this entry belongs to
        for side, key in (("dr", "debit"), ("cr", "credit")):
            d = tot[f"{p}_{side}"]
            d[t[key]] = d.get(t[key], 0.0) + t["amount"]       # I add the amount to the account's total

    rows = []                                                  # one worksheet row per account
    for acc in ordered:
        n = acc["name"]
        # rd/rc = daily debit/credit, ad/ac = adjusting debit/credit for this account
        rd, rc, ad, ac = (tot[k].get(n, 0.0) for k in ("reg_dr", "reg_cr", "adj_dr", "adj_cr"))
        adjusted = round(rd - rc + ad - ac, 2)                 # adjusted net balance (debit positive)
        row = dict.fromkeys(COLS, 0.0)                         # start every column at zero
        row.update(name=n, type=acc["type"])
        row["u_dr"], row["u_cr"] = split_dr_cr(rd - rc)        # unadjusted trial balance
        row["j_dr"], row["j_cr"] = round(ad, 2), round(ac, 2)  # adjustments columns
        row["a_dr"], row["a_cr"] = split_dr_cr(adjusted)       # adjusted trial balance
        # target = the statement this account's adjusted balance moves to
        target = "i" if acc["type"] in IS_TYPES else "o" if acc["type"] in OE_TYPES else "b"
        row[target + "_dr"], row[target + "_cr"] = row["a_dr"], row["a_cr"]
        row["p_dr"], row["p_cr"] = round(rd + ad, 2), round(rc + ac, 2)    # used by Accounts page
        row["balance"] = round(adjusted if acc["type"] in DEBIT_NORMAL else -adjusted, 2)  # balance on its normal side
        rows.append(row)

    totals = {k: round(sum(r[k] for r in rows), 2) for k in COLS}   # column totals

    # Net income moves from the Income Statement into Owner's Equity
    ni = round(totals["i_cr"] - totals["i_dr"], 2)             # ni = revenue minus expenses
    ni_row = dict.fromkeys(COLS, 0.0)                          # the balancing row for net income/loss
    if ni >= 0:
        ni_row["i_dr"] = ni_row["o_cr"] = ni                   # profit: debit IS, credit Owner's Equity
    else:
        ni_row["i_cr"] = ni_row["o_dr"] = -ni                  # loss: the opposite

    final = dict(totals)                                       # final = totals after my balancing rows
    for k in ("i_dr", "i_cr", "o_dr", "o_cr"):
        final[k] = round(totals[k] + ni_row[k], 2)

    # Ending owner's equity moves from Owner's Equity into the Balance Sheet
    equity_end = round(final["o_cr"] - final["o_dr"], 2)       # ending owner's equity
    end_row = dict.fromkeys(COLS, 0.0)                         # the balancing row for ending equity
    if equity_end >= 0:
        end_row["o_dr"] = end_row["b_cr"] = equity_end
    else:
        end_row["o_cr"] = end_row["b_dr"] = -equity_end
    for k in ("o_dr", "o_cr", "b_dr", "b_cr"):
        final[k] = round(final[k] + end_row[k], 2)

    return {"rows": rows, "totals": totals, "ni": ni, "ni_row": ni_row,
            "end_row": end_row, "final": final, "equity_end": equity_end}


# MAIN WINDOW
class AccountingApp(tk.Tk):
    def __init__(self):
        # I set up the window, load my data and build all six tabs
        super().__init__()
        self.title("Automated Accounting System")
        self.geometry("1280x720")
        self.accounts, self.transactions, self.rules = load_data()   # my three lists of saved data
        self.ws = None                                               # holds the latest worksheet result

        self.notebook = ttk.Notebook(self)                           # the tab container
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)
        for build in (self.build_new_transaction_page, self.build_ledger_page, self.build_accounts_page,
                      self.build_history_page, self.build_adjustments_page, self.build_worksheet_page):
            build()

        # Lazy refresh: only the visible tab is redrawn; others redraw when opened
        # one refresh function per tab, in tab order (New Transaction has none)
        self.page_refreshers = [None, self.refresh_ledger, self.refresh_accounts, self.refresh_history,
                                self.refresh_adjustments, self.refresh_worksheet]
        self.dirty = set()                                           # tabs that are out of date
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self.refresh_tab(self.notebook.index("current")))
        self.refresh_all()

    #  helpers
    def save(self):
        # I save my current data to disk
        save_data(self.accounts, self.transactions, self.rules)

    def make_page(self, title, purpose):
        # I create a tab with a blue purpose line at the top and return it
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text=title)
        ttk.Label(page, text=f"PURPOSE: {purpose}", foreground="#1a5276", wraplength=1180,
                  font=("Arial", 10, "italic")).pack(anchor="w", pady=(0, 10))
        return page

    def make_table(self, parent, columns, widths, right_from=None):
        """Treeview with a vertical scrollbar. Columns from index right_from are right-aligned."""
        # I build a table (Treeview) with a scrollbar; number columns are right-aligned
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for i, (col, w) in enumerate(zip(columns, widths)):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="e" if right_from is not None and i >= right_from else "w")
        vs = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)   # vs = vertical scrollbar
        tree.configure(yscrollcommand=vs.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        return tree

    @staticmethod #define a method inside a class that does not receive any implicit first argument
    def add_field(form, row, label, var, values=None, readonly=False, width=35):
        """One 'label + entry/combobox' row in a form grid."""
        # I add a label plus a textbox (or dropdown if I pass values) to a form row
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)
        if values is None:
            w = ttk.Entry(form, textvariable=var, width=width)
        else:
            w = ttk.Combobox(form, textvariable=var, values=values, width=width - 3,
                             state="readonly" if readonly else "normal")
        w.grid(row=row, column=1, pady=4)
        return w

    def find_account(self, name):
        # I look up an account by name (ignoring case); returns None if not found
        name = name.strip().lower()
        return next((a for a in self.accounts if a["name"].lower() == name), None)

    def next_id(self):
        # I give each new transaction the next number after the highest existing id
        return max((t["id"] for t in self.transactions), default=0) + 1

    def check_entry(self, date, desc, debit, credit, amount_text):
        """Validate fields shared by daily and adjusting entries. Returns the amount, or None after a warning."""
        def warn(title, msg):
            # I show a warning popup and return None so callers know validation failed
            messagebox.showwarning(title, msg)

        try:
            datetime.strptime(date, "%Y-%m-%d")                 # I check the date format
        except ValueError:
            return warn("Bad date", "Date must look like 2026-10-22.")
        if not desc or not debit or not credit:
            return warn("Missing info", "Enter a description, a debit account and a credit account.")
        if debit.lower() == credit.lower():
            return warn("Same account", "Debit and credit accounts must be different.")
        try:
            amount = float(amount_text.replace(",", ""))        # amount = the number I typed, commas removed
            if amount <= 0:
                raise ValueError
        except ValueError:
            return warn("Bad amount", "Amount must be a number greater than 0.")
        return round(amount, 2)

    # PAGE 1: NEW TRANSACTION
    def build_new_transaction_page(self):
        # I build the form for recording daily transactions
        page = self.make_page(
            "New Transaction",
            "Record a DAILY transaction: who is recording it, the date, a description, the account to DEBIT, "
            "the account to CREDIT, and the amount. It is posted to the Ledger, History and Unadjusted Trial "
            "Balance automatically. (End-of-period adjustments go on the Adjustments tab.)")
        form = ttk.Frame(page)
        form.pack(anchor="w")
        # these StringVars hold whatever I type in each field
        self.var_person, self.var_desc, self.var_debit, self.var_credit, self.var_amount = \
            (tk.StringVar() for _ in range(5))
        self.var_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))   # date defaults to today

        self.add_field(form, 0, "Person (who is inputting):", self.var_person)
        self.add_field(form, 1, "Date (YYYY-MM-DD):", self.var_date)
        self.add_field(form, 2, "Description:", self.var_desc)
        self.cmb_debit = self.add_field(form, 3, "Debit Account:", self.var_debit, [], readonly=True)     # debit dropdown
        self.cmb_credit = self.add_field(form, 4, "Credit Account:", self.var_credit, [], readonly=True)  # credit dropdown
        self.add_field(form, 5, "Amount:", self.var_amount)
        ttk.Button(form, text="Record Transaction", command=self.record_transaction) \
            .grid(row=6, column=1, sticky="w", pady=12)

    def record_transaction(self):
        # I validate the form, then save the entry as a daily transaction
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
        for v in (self.var_desc, self.var_amount, self.var_debit, self.var_credit):  # keep person and date
            v.set("")
        self.refresh_all()
        messagebox.showinfo("Saved", "Transaction recorded and posted to the Ledger and Worksheet.")

    # ---------- PAGE 2: LEDGER ----------
    def build_ledger_page(self):
        # I build the ledger tab: account picker, table and totals
        page = self.make_page(
            "Ledger",
            "Choose an account to see its ledger. Each transaction is posted to the account debited "
            "(Debit column) and the account credited (Credit column). Adjusting entries are marked [ADJ].")
        self.lbl_totals = ttk.Label(page, font=("Arial", 10, "bold"))    # grand total debit/credit of all accounts
        self.lbl_totals.pack(side="bottom", anchor="e", pady=6)

        top = ttk.Frame(page)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Account:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 8))
        self.var_ledger_acc = tk.StringVar()                             # the account I picked
        self.cmb_ledger = ttk.Combobox(top, textvariable=self.var_ledger_acc, state="readonly", font=("Arial", 14))
        self.cmb_ledger.pack(side="left", fill="x", expand=True)
        self.cmb_ledger.bind("<<ComboboxSelected>>", lambda e: self.show_account_ledger())

        self.lbl_ledger_title = ttk.Label(page, font=("Arial", 11, "bold"), justify="left")   # shows account name + type
        self.lbl_ledger_title.pack(anchor="w", pady=(0, 6), fill="x")
        self.tree_ledger = self.make_table(page, ("Date", "Description", "Debit", "Credit", "Balance"),
                                           (100, 430, 130, 130, 140), right_from=2)
        self.lbl_account_totals = ttk.Label(page, font=("Arial", 10, "bold"))   # totals for the chosen account
        self.lbl_account_totals.pack(anchor="e", pady=6)

    def refresh_ledger(self):
        # I reload the account dropdown and redraw the selected account's ledger
        names = [a["name"] for a in self.accounts]
        self.cmb_ledger["values"] = names
        self.cmb_ledger.configure(height=min(max(len(names), 1), 15))
        current = self.var_ledger_acc.get()
        self.var_ledger_acc.set(current if current in names else (names[0] if names else ""))   # keep my selection if possible
        self.show_account_ledger()
        grand = sum(t["amount"] for t in self.transactions)              # grand = total of all entries (debits = credits)
        self.lbl_totals.config(text=f"All Accounts - Total Debit: {grand:,.2f}    Total Credit: {grand:,.2f}")

    def show_account_ledger(self):
        # I list every entry touching the chosen account with a running balance
        self.tree_ledger.delete(*self.tree_ledger.get_children())
        acc = self.find_account(self.var_ledger_acc.get())
        if acc is None:
            self.lbl_ledger_title.config(text="No account selected")
            self.lbl_account_totals.config(text="")
            return
        self.lbl_ledger_title.config(text=f"{acc['name']}  ({acc['type']})")

        debit_normal = acc["type"] in DEBIT_NORMAL                       # True if this account normally has a debit balance
        total_dr = total_cr = balance = 0.0                              # running totals for this account
        for t in sorted(self.transactions, key=lambda x: (x["date"], x["id"])):
            is_dr = t["debit"] == acc["name"]                            # True if the account was debited in this entry
            if not is_dr and t["credit"] != acc["name"]:
                continue                                                 # skip entries that don't involve this account
            amt = t["amount"]
            balance += amt if is_dr == debit_normal else -amt   # same side as normal balance -> increases
            if is_dr:
                total_dr += amt
            else:
                total_cr += amt
            tag = "[ADJ] " if t.get("kind") == "adjusting" else ""       # tag = marker for adjusting entries
            self.tree_ledger.insert("", "end", values=(
                t["date"], tag + t["description"],
                f"{amt:,.2f}" if is_dr else "", "" if is_dr else f"{amt:,.2f}", money(balance)))
        self.lbl_account_totals.config(
            text=f"Total Debit: {total_dr:,.2f}    Total Credit: {total_cr:,.2f}    Balance: {money(balance)}")

    # PAGE 3: ACCOUNTS
    def build_accounts_page(self):
        # I build the accounts list plus the add/delete controls
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
        self.var_new_acc = tk.StringVar()                                # name of the new account I'm adding
        self.var_new_type = tk.StringVar(value="Asset")                  # its type, Asset by default
        ttk.Label(add, text="New account name:").grid(row=0, column=0, padx=4)
        ttk.Entry(add, textvariable=self.var_new_acc, width=25).grid(row=0, column=1, padx=4)
        ttk.Label(add, text="Type:").grid(row=0, column=2, padx=4)
        ttk.Combobox(add, textvariable=self.var_new_type, values=TYPE_ORDER, width=14,
                     state="readonly").grid(row=0, column=3, padx=4)
        ttk.Button(add, text="Add Account", command=self.add_account).grid(row=0, column=4, padx=4)
        ttk.Button(add, text="Delete Selected Account", command=self.delete_account).grid(row=0, column=5, padx=20)

    def add_account(self):
        # I add a new account after checking the name isn't empty or a duplicate
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
        # I delete the selected account, but only if nothing uses it
        selected = self.tree_accounts.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click an account in the list first.")
        idx = int(selected[0])                                           # idx = position of the account in my list
        acc = self.accounts[idx]
        # uses() checks whether any item in a list (transactions/rules) references this account
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
        for var in (self.var_debit, self.var_credit):                    # clear the dropdowns if they had this account
            if var.get() == acc["name"]:
                var.set("")
        self.save()
        self.refresh_all()
        messagebox.showinfo("Deleted", "Account deleted.")

    def refresh_accounts(self):
        # I redraw the accounts table using the worksheet's computed numbers
        self.tree_accounts.delete(*self.tree_accounts.get_children())
        by_name = {r["name"]: r for r in self.ws["rows"]}                # by_name = quick lookup of worksheet rows
        for i, acc in enumerate(self.accounts):
            r = by_name[acc["name"]]
            self.tree_accounts.insert("", "end", iid=str(i), values=(
                acc["name"], acc["type"], f"{r['p_dr']:,.2f}", f"{r['p_cr']:,.2f}", money(r["balance"])))

    # PAGE 4: TRANSACTION HISTORY 
    def build_history_page(self):
        # I build the history table and the delete button
        page = self.make_page(
            "Transaction History",
            "Every entry as it was entered (daily and adjusting), including who entered it. "
            "Use it to check past entries or to delete a wrong one.")
        self.tree_history = self.make_table(
            page, ("No.", "Type", "Date", "Person", "Description", "Debit Account", "Credit Account", "Amount"),
            (50, 80, 100, 130, 300, 180, 180, 110), right_from=7)
        ttk.Button(page, text="Delete Selected Transaction", command=self.delete_transaction).pack(anchor="w", pady=8)

    def refresh_history(self):
        # I list all entries, newest first
        self.tree_history.delete(*self.tree_history.get_children())
        for t in reversed(self.transactions):
            self.tree_history.insert("", "end", values=(
                t["id"], "Adjusting" if t.get("kind") == "adjusting" else "Daily", t["date"], t["person"],
                t["description"], t["debit"], t["credit"], f"{t['amount']:,.2f}"))

    def delete_transaction(self):
        # I delete the selected entry after confirming, then renumber the rest
        selected = self.tree_history.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click a transaction in the list first.")
        trans_id = int(self.tree_history.item(selected[0], "values")[0])   # trans_id = the "No." of the chosen row
        if not messagebox.askyesno(
                "Confirm delete", f"Delete transaction No. {trans_id}?\nThis also removes it from the Ledger, "
                                  "the Worksheet and the account balances."):
            return
        self.transactions = [t for t in self.transactions if t["id"] != trans_id]   # keep everything except the deleted one
        for new_id, t in enumerate(self.transactions, start=1):   # renumber
            t["id"] = new_id
        self.save()
        self.refresh_all()
        messagebox.showinfo("Deleted", "Transaction deleted.")

    #  PAGE 5: ADJUSTMENTS 
    def build_adjustments_page(self):
        # I build the adjusting-entry form and the recurring rules table
        page = self.make_page(
            "Adjustments",
            "Post end-of-period ADJUSTING entries. Pick an adjustment type and the accounts are filled in "
            "(missing accounts are created automatically); enter the amount and post. Use 'Save as Recurring "
            "Rule' for adjustments that repeat every period, then 'Apply All Rules' posts them in one click. "
            "Adjustments flow into the Adjustments columns of the Worksheet.")
        form = ttk.Frame(page)
        form.pack(anchor="w")
        self.var_adj_template = tk.StringVar(value=list(ADJUSTMENT_TEMPLATES)[0])   # chosen adjustment type (first by default)
        self.var_adj_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d")) # period-end date, today by default
        # description, debit account, credit account and amount fields for the adjustment
        self.var_adj_desc, self.var_adj_debit, self.var_adj_credit, self.var_adj_amount = \
            (tk.StringVar() for _ in range(4))

        cmb = self.add_field(form, 0, "Adjustment type:", self.var_adj_template,
                             list(ADJUSTMENT_TEMPLATES), readonly=True, width=43)
        cmb.bind("<<ComboboxSelected>>", lambda e: self.apply_template())   # fill the form when the type changes
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
        self.apply_template()                                            # pre-fill the form with the first template

    def apply_template(self):
        # I copy the chosen template's accounts and description into the form
        d, _, c, _, desc = ADJUSTMENT_TEMPLATES[self.var_adj_template.get()]   # d = debit acct, c = credit acct
        self.var_adj_debit.set(d)
        self.var_adj_credit.set(c)
        self.var_adj_desc.set(desc)

    def read_adjustment_form(self):
        """Validate the adjustment form. Returns an entry dict or None."""
        # I read and validate the adjustment form, returning it as a dict
        date, desc = self.var_adj_date.get().strip(), self.var_adj_desc.get().strip()
        debit, credit = self.var_adj_debit.get().strip(), self.var_adj_credit.get().strip()
        amount = self.check_entry(date, desc, debit, credit, self.var_adj_amount.get())
        if amount is None:
            return None
        # A missing account may only be auto-created if it matches the template's default account
        template = self.var_adj_template.get()
        d_def, d_type, c_def, c_type, _ = ADJUSTMENT_TEMPLATES[template]   # the template's default accounts and types
        return {"template": template, "date": date, "description": desc, "debit": debit, "credit": credit,
                "amount": amount, "debit_type": d_type if debit.lower() == d_def.lower() else None,
                "credit_type": c_type if credit.lower() == c_def.lower() else None}

    def post_entry(self, e):
        """Post one adjusting entry. Returns an error message, or None on success."""
        # I post one adjusting entry, creating missing template accounts when allowed
        if e["debit"].lower() == e["credit"].lower():
            return "Debit and credit accounts must be different."
        accs = []                                                        # accs = [debit account, credit account]
        for side in ("debit", "credit"):
            acc = self.find_account(e[side])
            if acc is None and e.get(side + "_type") not in TYPE_ORDER:
                return f"Account '{e[side]}' doesn't exist. Pick an existing account or use the template's account."
            accs.append(acc)
        for i, side in enumerate(("debit", "credit")):      # auto-create missing accounts
            if accs[i] is None:
                accs[i] = {"name": e[side].strip(), "type": e[side + "_type"]}
                self.accounts.append(accs[i])
        self.transactions.append({
            "id": self.next_id(), "kind": "adjusting", "person": "System (Adjusting)", "date": e["date"],
            "description": e["description"], "debit": accs[0]["name"], "credit": accs[1]["name"],
            "amount": e["amount"]})
        return None

    def post_adjustment(self):
        # I post the form's adjustment and update the screens
        e = self.read_adjustment_form()                                  # e = the validated entry
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
        # I store the form as a recurring rule I can apply every period
        e = self.read_adjustment_form()
        if e is None:
            return
        self.rules.append({k: e[k] for k in
                           ("template", "debit", "credit", "debit_type", "credit_type", "amount", "description")})
        self.save()
        self.refresh_all()

    def delete_rule(self):
        # I remove the selected recurring rule
        selected = self.tree_rules.selection()
        if not selected:
            return messagebox.showwarning("No selection", "Click a rule in the list first.")
        del self.rules[int(selected[0])]
        self.save()
        self.refresh_all()

    def apply_rules(self):
        # I post every saved rule on the period-end date, skipping ones already posted
        date = self.var_adj_date.get().strip()
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return messagebox.showwarning("Bad date", "Enter a valid period-end date (YYYY-MM-DD) first.")
        if not self.rules:
            return messagebox.showinfo("No rules", "There are no recurring rules yet.")

        posted = skipped = 0                                             # counters for my summary message
        errors = []                                                      # problems to report at the end
        for r in self.rules:
            # duplicate = True if this exact adjustment is already posted for this date
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
        # I refresh the account dropdowns and the rules table
        names = [a["name"] for a in self.accounts]
        self.cmb_adj_debit["values"] = self.cmb_adj_credit["values"] = names
        self.tree_rules.delete(*self.tree_rules.get_children())
        for i, r in enumerate(self.rules):
            self.tree_rules.insert("", "end", iid=str(i), values=(
                r["template"], r["debit"], r["credit"], f"{r['amount']:,.2f}", r["description"]))

    #  PAGE 6: WORKSHEET (drawn as a ruled table on a canvas) 
    def build_worksheet_page(self):
        # I build a scrollable canvas where I draw the worksheet myself
        page = self.make_page(
            "Worksheet",
            "The 12-column worksheet, built automatically from your entries. Net income is pulled into the "
            "Owner's Equity columns, and ending owner's equity is pulled into the Balance Sheet columns.")
        self.lbl_ws_summary = ttk.Label(page, font=("Arial", 10, "bold"))   # summary line: net income, equity, balanced?
        self.lbl_ws_summary.pack(side="bottom", anchor="w", pady=6)

        frame = ttk.Frame(page)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        c = self.ws_canvas = tk.Canvas(frame, highlightthickness=0, background="white")   # c = the drawing area
        vs = ttk.Scrollbar(frame, orient="vertical", command=c.yview)    # vertical scrollbar
        hs = ttk.Scrollbar(frame, orient="horizontal", command=c.xview)  # horizontal scrollbar
        c.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        c.grid(row=0, column=0, sticky="nsew")
        vs.grid(row=0, column=1, sticky="ns")
        hs.grid(row=1, column=0, sticky="ew")
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))   # mouse wheel (Windows/Mac)
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))                           # scroll up (Linux)
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))                            # scroll down (Linux)

    def refresh_worksheet(self):
        # I redraw the whole worksheet from the latest computed data
        ws, c = self.ws, self.ws_canvas
        c.delete("all")
        NAME_W, COL_W, ROW_H = 230, 105, 26                              # widths/heights in pixels
        LINE, HEAD, TOTAL, PULL = "#2c3e50", "#d6eaf8", "#aed6f1", "#fcf3cf"   # colors: lines, header, totals, pulled-in rows

        def cell(x0, y0, x1, y1, text, bg, bold=False, align="e"):
            """Draw one ruled cell with text aligned 'w' (left), 'e' (right) or 'center'."""
            # I draw one box with optional text inside
            c.create_rectangle(x0 + 1, y0 + 1, x1 + 1, y1 + 1, fill=bg, outline=LINE)
            if text:
                x = {"w": x0 + 8, "e": x1 - 8, "center": (x0 + x1) / 2}[align]   # x = where the text goes
                c.create_text(x + 1, (y0 + y1) / 2 + 1, text=text, font=("Arial", 10, "bold" if bold else "normal"),
                              anchor="center" if align == "center" else align)

        # Two-line header: each statement name spans a Debit / Credit pair
        cell(0, 0, NAME_W, 2 * ROW_H, "Account", HEAD, True, "center")
        for i, name in enumerate(GROUPS):
            x0 = NAME_W + i * 2 * COL_W                                  # x0 = left edge of this group
            cell(x0, 0, x0 + 2 * COL_W, ROW_H, name, HEAD, True, "center")
            cell(x0, ROW_H, x0 + COL_W, 2 * ROW_H, "Debit", HEAD, True, "center")
            cell(x0 + COL_W, ROW_H, x0 + 2 * COL_W, 2 * ROW_H, "Credit", HEAD, True, "center")

        def put_row(r, name, d, bg="white", bold=False):
            # I draw one full worksheet row: the name plus its 12 number cells (blank if zero)
            y0, y1 = r * ROW_H, (r + 1) * ROW_H
            cell(0, y0, NAME_W, y1, name, bg, bold, "w")
            for k, col in enumerate(COLS):
                x0 = NAME_W + k * COL_W
                cell(x0, y0, x0 + COL_W, y1, "" if abs(d[col]) < EPS else f"{d[col]:,.2f}", bg, bold)

        r = 2                                                            # r = current row number (rows 0-1 are the header)
        for row in ws["rows"]:
            put_row(r, row["name"], row)
            r += 1
        put_row(r, "TOTALS", ws["totals"], TOTAL, True)
        put_row(r + 1, "Net Income" if ws["ni"] >= 0 else "Net Loss", ws["ni_row"], PULL, True)
        put_row(r + 2, "Ending Owner's Equity", ws["end_row"], PULL, True)

        f = ws["final"]                                                  # f = final totals row
        # balanced = True when debit equals credit in all six column pairs
        balanced = all(abs(f[p + "_dr"] - f[p + "_cr"]) < EPS for p in "ujaiob")
        put_row(r + 3, "FINAL TOTALS", f, "#d5f5e3" if balanced else "#f5b7b1", True)   # green if balanced, red if not
        c.configure(scrollregion=(0, 0, NAME_W + 12 * COL_W + 2, (r + 4) * ROW_H + 2))  # let me scroll the full table

        self.lbl_ws_summary.config(
            text=f"{'Net Income' if ws['ni'] >= 0 else 'Net Loss'}: {abs(ws['ni']):,.2f}     "
                 f"Ending Owner's Equity: {money(ws['equity_end'])}     "
                 f"Worksheet: {'BALANCED' if balanced else 'OUT OF BALANCE'}")

    # ---------- REFRESH ----------
    def refresh_all(self):
        # I rebuild the worksheet data, mark every tab outdated, and redraw only the visible one
        names = [a["name"] for a in self.accounts]
        self.cmb_debit["values"] = self.cmb_credit["values"] = names
        self.ws = build_worksheet(self.accounts, self.transactions)
        self.dirty = set(range(len(self.page_refreshers)))        # every tab is now out of date...
        self.refresh_tab(self.notebook.index("current"))          # ...redraw just the visible one

    def refresh_tab(self, idx):
        # I redraw tab number idx only if it's marked out of date
        if idx in self.dirty:
            if self.page_refreshers[idx]:
                self.page_refreshers[idx]()
            self.dirty.discard(idx)


if __name__ == "__main__":
    AccountingApp().mainloop()                                    # I start the app and keep the window running


# HOW EACH TAB WORKS (my summary of the whole program)
# =====================================================================


# 1. NEW TRANSACTION
#    This is where I record my daily transactions. I type who is entering it, the date,
#    a description, the account to debit, the account to credit and the amount.
#    When I click "Record Transaction", I check the inputs, save the entry as a "regular"
#    transaction, and it is posted automatically to the Ledger, the Transaction History
#    and the Unadjusted Trial Balance columns of the Worksheet.


# 2. LEDGER
#    I pick an account from the dropdown and see every entry that touched it.
#    Entries where the account was debited show in the Debit column, entries where it was
#    credited show in the Credit column, and I keep a running balance based on the
#    account's normal side (debit or credit). Adjusting entries are marked [ADJ].


# 3. ACCOUNTS
#    This is my list of all accounts with their type, total debit, total credit and current
#    balance (daily + adjusting entries). I can add a new account or delete one.
#    I block deletion if the account is already used by a transaction or a recurring rule.
#    The account TYPE matters because it decides which worksheet columns it goes to.


# 4. TRANSACTION HISTORY
#    This shows every entry exactly as entered (daily and adjusting), newest first,
#    including who entered it. If I find a wrong entry, I select it and delete it;
#    the Ledger, Accounts and Worksheet update automatically and the entry numbers are
#    renumbered.


# 5. ADJUSTMENTS
#    This is where I post end-of-period adjusting entries (depreciation, supplies used,
#    expired prepaids, accrued salaries, unearned revenue earned, accrued revenue, bad debts).
#    I pick an adjustment type and the debit/credit accounts are filled in for me (missing
#    accounts are created automatically), then I enter the amount and post it.
#    "Save as Recurring Rule" stores the entry as a rule, and "Apply All Rules" posts all
#    saved rules at once on the period-end date, skipping any that were already posted.
#    These entries go into the Adjustments columns of the Worksheet.


# 6. WORKSHEET (12 columns)
#    I build this automatically from my entries, so I never type into it:
#      - Unadjusted Trial Balance  = my daily entries only
#      - Adjustments               = my adjusting entries only
#      - Adjusted Trial Balance    = daily + adjusting entries combined
#      - Income Statement          = Revenue and Expense accounts
#      - Owner's Equity            = Equity and Drawings accounts
#      - Balance Sheet             = Asset, Contra Asset and Liability accounts
#    Each account's adjusted balance moves to one of the last three statements based on its type.
#    The Net Income (or Net Loss) row balances the Income Statement and moves the profit into
#    Owner's Equity. The Ending Owner's Equity row then moves that total into the Balance Sheet.
#    The FINAL TOTALS row turns green and says BALANCED when debits equal credits in every
#    column pair, and red (OUT OF BALANCE) if they don't.


# AUTOMATIC UPDATING: every time I add, delete or adjust something, I call refresh_all(),
# which rebuilds the worksheet and redraws only the tab I'm looking at. The other tabs
# update when I open them. Everything is saved to accounting_data.json so my data is still
# there the next time I open the program.
