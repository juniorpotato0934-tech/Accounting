"""
Group 1 System:
SIMPLE ACCOUNTING SYSTEM (GUI)

Pages (tabs):
  1. New Transaction     - enter person, date, description, debit account, credit account, amount
  2. Ledger              - journal: every transaction is automatically posted here as 2 lines
  3. Accounts            - list of accounts with their running balances (you can add accounts)
  4. Transaction History - one row per transaction, exactly as it was entered

Data is saved automatically to 'accounting_data.json' (same folder) so nothing is lost on close.
Only needs Python 3 (tkinter is included with Python).
"""

import json 
import os
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime


# SECTION 1: DATA STORAGE
# Everything lives in two lists: ACCOUNTS and TRANSACTIONS. They are saved to a JSON file.

#ari gi store ang mga gi inpute na transaction, silbe ni siyang sorage for data
DATA_FILE = "accounting_data.json"

# Account types decide which side increases the balance
#diri ang sa credit ang debit, ari mo determin if unsa na account name ang paras debit ug credit.
#same rana silag amount ma input sa debit ug credit lahi lag account name
DEBIT_NORMAL = ("Asset", "Expense")            # balance goes UP with a debit
CREDIT_NORMAL = ("Liability", "Equity", "Revenue")  # balance goes UP with a credit
ACCOUNT_TYPES = DEBIT_NORMAL + CREDIT_NORMAL



# Starter accounts so the system is usable right away
#mao ni ang base account names and type, pero maka add ramog new account name and unsa siya type na account
DEFAULT_ACCOUNTS = [
    {"name": "Cash", "type": "Asset"},
    {"name": "Accounts Receivable", "type": "Asset"},
    {"name": "Equipment", "type": "Asset"},
    {"name": "Accounts Payable", "type": "Liability"},
    {"name": "Owner's Capital", "type": "Equity"},
    {"name": "Sales Revenue", "type": "Revenue"},
    {"name": "Rent Expense", "type": "Expense"},
    {"name": "Salaries Expense", "type": "Expense"},
]

#diri niya ilabay ang gi input na transaction sa soud sa data storage
def load_data():
    """Load accounts and transactions from the JSON file (or start fresh)."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data["accounts"], data["transactions"]
    return list(DEFAULT_ACCOUNTS), []
#after nimo input transaction, automatically siya masoud sa JSON which is ang storage 
def save_data(accounts, transactions):
    """Write everything to the JSON file. Called after every change."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"accounts": accounts, "transactions": transactions}, f, indent=2)



# SECTION 2: MAIN APPLICATION WINDOW
#mao ni siya ang mismong UI sa system, ang window ug mga tab sa system
class AccountingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Accounting System")
        self.geometry("900x600")

        # Load saved data into memory
        #ari mo auto save siya sa data storage ug unsay inyu i input
        self.accounts, self.transactions = load_data()

        # Tab container (the 4 pages)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        # Build each page
        #mao ni ang pages sa system
        self.build_new_transaction_page()
        self.build_ledger_page()
        self.build_accounts_page()
        self.build_history_page()

        # Fill all tables/dropdowns with current data
        self.refresh_all()

    
    # Helper: create a page (tab) with a purpose banner at the top
    #diri na part kay sa kato rani header sa 1st tab para ma guide mo unsay buhaton, naka ai rani diri na part
    def make_page(self, tab_title, purpose_text):
        page = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(page, text=tab_title)
        # The "soul purpose" entry: tells the user what this page is for
        ttk.Label(page, text=f"PURPOSE: {purpose_text}",
                  foreground="#1a5276", wraplength=850,
                  font=("Arial", 10, "italic")).pack(anchor="w", pady=(0, 10))
        return page

    # Helper: create a table (Treeview) with scrollbar
    def make_table(self, parent, columns, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col, w in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=w, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree


    # PAGE 1: NEW TRANSACTION (the input form)
    def build_new_transaction_page(self):
        page = self.make_page(
            "New Transaction",
            "Record a new transaction. Enter who is recording it, the date, a description, "
            "the account to DEBIT, the account to CREDIT, and the amount. "
            "It is posted to the Ledger and History automatically.")

        form = ttk.Frame(page)
        form.pack(anchor="w")

        # Variables that hold what the user types/chooses
        #mao ni ang murag silbe paramtere sa i input nimo for transactions
        self.var_person = tk.StringVar()
        self.var_date = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d")) #kani siya ay automatic na current time/date
        self.var_desc = tk.StringVar()
        self.var_debit = tk.StringVar()
        self.var_credit = tk.StringVar()
        self.var_amount = tk.StringVar()

        # Each row = label + input widget
        #diri mao ni kung asa ka mo input paras transaction
        ttk.Label(form, text="Person (who is inputting):").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.var_person, width=35).grid(row=0, column=1, pady=4)

        ttk.Label(form, text="Date (YYYY-MM-DD):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.var_date, width=35).grid(row=1, column=1, pady=4)

        ttk.Label(form, text="Description:").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.var_desc, width=35).grid(row=2, column=1, pady=4)

        ttk.Label(form, text="Debit Account:").grid(row=3, column=0, sticky="w", pady=4)
        self.cmb_debit = ttk.Combobox(form, textvariable=self.var_debit, width=32, state="readonly")
        self.cmb_debit.grid(row=3, column=1, pady=4)

        ttk.Label(form, text="Credit Account:").grid(row=4, column=0, sticky="w", pady=4)
        self.cmb_credit = ttk.Combobox(form, textvariable=self.var_credit, width=32, state="readonly")
        self.cmb_credit.grid(row=4, column=1, pady=4)

        ttk.Label(form, text="Amount:").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.var_amount, width=35).grid(row=5, column=1, pady=4)

        ttk.Button(form, text="Record Transaction", command=self.record_transaction)\
            .grid(row=6, column=1, sticky="w", pady=12)

    #after input transaction, ilabay dayun niya sa each pages
    def record_transaction(self):
        """Validate the form, save the transaction, then refresh every page."""
        person = self.var_person.get().strip()
        date = self.var_date.get().strip()
        desc = self.var_desc.get().strip()
        debit = self.var_debit.get()
        credit = self.var_credit.get()

        # Validation: stop and warn if something is wrong 
        #diri kay i verify if sakto ba inyu gi input or naay missing
        #diri na part most likely nag pa help rakos AI pero masabtan raman sad
        if not person or not desc:
            messagebox.showwarning("Missing info", "Please enter the person and a description.")
            return
        try:
            datetime.strptime(date, "%Y-%m-%d")  # checks the date format
        except ValueError:
            messagebox.showwarning("Bad date", "Date must look like 2026-10-22.")
            return
        if not debit or not credit:
            messagebox.showwarning("Missing account", "Please choose both a debit and a credit account.")
            return
        if debit == credit:
            messagebox.showwarning("Same account", "Debit and credit accounts must be different.")
            return
        try:
            amount = float(self.var_amount.get().replace(",", ""))
            if amount <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Bad amount", "Amount must be a number greater than 0.")
            return

        # Save: add to the transaction list (this feeds the Ledger + History) 
        """ari na part, mao nani ang transaction tab/list kung unsa imo gi input nya lahus rapud ma save sa storage.
        bisag unsaon nimo exit sa system, ma save ra ghpon tong transaction. basta ayaw i delete ang storage file"""

        self.transactions.append({
            "id": len(self.transactions) + 1,   # simple running number
            "person": person,
            "date": date,
            "description": desc,
            "debit": debit,
            "credit": credit,
            "amount": amount,
        })
        save_data(self.accounts, self.transactions)

        # Clear the form (keep the person and date for faster entry)
        #after input sa transactio, automatic na siya mo blank dayun 
        self.var_desc.set("")
        self.var_amount.set("")
        self.var_debit.set("")
        self.var_credit.set("")

        self.refresh_all()
        messagebox.showinfo("Saved", "Transaction recorded and posted to the Ledger.")#mao ni ang pop up nga na record siya

    
    # PAGE 2: LEDGER (journal view, 2 lines per transaction)
    def build_ledger_page(self):
        #heading rani na part 
        page = self.make_page(
            "Ledger",
            "The journal. Every transaction is posted automatically as two lines: "
            "the debited account and the credited account. Total debits must equal total credits.")
        self.tree_ledger = self.make_table(
            page, ("Date", "Account", "Description", "Debit", "Credit"), (100, 180, 330, 100, 100))
        
        # Totals label under the table
        self.lbl_totals = ttk.Label(page, font=("Arial", 10, "bold"))
        self.lbl_totals.pack(anchor="e", pady=6)

    def refresh_ledger(self):
        self.tree_ledger.delete(*self.tree_ledger.get_children())
        total_debit = total_credit = 0.0
        # Sort by date so the journal reads in order
        for t in sorted(self.transactions, key=lambda x: (x["date"], x["id"])):
            # Line 1: the DEBIT side (amount goes in the Debit column)
            self.tree_ledger.insert("", "end", values=(
                t["date"], t["debit"], t["description"], f"{t['amount']:,.2f}", ""))
            # Line 2: the CREDIT side (amount goes in the Credit column, name indented)
            self.tree_ledger.insert("", "end", values=(
                "", "     " + t["credit"], "", "", f"{t['amount']:,.2f}"))
            total_debit += t["amount"]
            total_credit += t["amount"]
        self.lbl_totals.config(
            text=f"Total Debit: {total_debit:,.2f}    Total Credit: {total_credit:,.2f}")
        

    # PAGE 3: ACCOUNTS (list + balances + add new account)
    def build_accounts_page(self):
        page = self.make_page(
            "Accounts",
            "Shows every account and its current balance. "
            "Balances update automatically from the transactions. You can also add a new account here.")
        self.tree_accounts = self.make_table(
            page, ("Account", "Type", "Total Debit", "Total Credit", "Balance"), (220, 100, 130, 130, 130))

        # Small form to add an account
        #ari maka add kag new account name ug unsa siya na type, pwede raka mag base sa previous activity sa acctg
        add = ttk.Frame(page)
        add.pack(anchor="w", pady=10)
        self.var_new_acc = tk.StringVar()
        self.var_new_type = tk.StringVar(value="Asset")
        ttk.Label(add, text="New account name:").grid(row=0, column=0, padx=4)
        ttk.Entry(add, textvariable=self.var_new_acc, width=25).grid(row=0, column=1, padx=4)
        ttk.Label(add, text="Type:").grid(row=0, column=2, padx=4)
        ttk.Combobox(add, textvariable=self.var_new_type, values=ACCOUNT_TYPES,
                     width=12, state="readonly").grid(row=0, column=3, padx=4)
        ttk.Button(add, text="Add Account", command=self.add_account).grid(row=0, column=4, padx=4)

#after maka add ug new account name with account type, lahus na siya ma save sa system, sulod sa storage pud.
#nya iya dayun i pasa pud sa 1st page, sa katung input transaction. makit dayun ddto sa credit ug debit na input imo new account
    def add_account(self):
        name = self.var_new_acc.get().strip()
        if not name:
            messagebox.showwarning("Missing name", "Enter an account name.")
            return
        if name.lower() in [a["name"].lower() for a in self.accounts]:
            messagebox.showwarning("Duplicate", "That account already exists.")
            return
        self.accounts.append({"name": name, "type": self.var_new_type.get()})
        save_data(self.accounts, self.transactions)
        self.var_new_acc.set("")
        self.refresh_all()

    def refresh_accounts(self):
        self.tree_accounts.delete(*self.tree_accounts.get_children())
        for acc in self.accounts:
            # Add up all debits and credits that touched this account
            deb = sum(t["amount"] for t in self.transactions if t["debit"] == acc["name"])
            cre = sum(t["amount"] for t in self.transactions if t["credit"] == acc["name"])
            # Balance depends on the account type's normal side
            balance = deb - cre if acc["type"] in DEBIT_NORMAL else cre - deb
            self.tree_accounts.insert("", "end", values=(
                acc["name"], acc["type"], f"{deb:,.2f}", f"{cre:,.2f}", f"{balance:,.2f}"))


    # PAGE 4: TRANSACTION HISTORY (one row per transaction)
    #diri nimo makita imo history sa transaction, ug kinsa na name ga input sa transaction
    #same ghpon nag need ghpon ni siyag data from the storage
    def build_history_page(self):
        page = self.make_page(
            "Transaction History",
            "A record of every transaction as it was entered, including who entered it. "
            "Use it to check or audit past entries.")
        self.tree_history = self.make_table(
            page, ("No.", "Date", "Person", "Description", "Debit Account", "Credit Account", "Amount"),
            (40, 90, 120, 220, 130, 130, 90))

    def refresh_history(self):
        self.tree_history.delete(*self.tree_history.get_children())
        # Newest first
        #gi sort ni niya na ang bag o na transaction ang maoy naas ibabaw 
        for t in reversed(self.transactions):
            self.tree_history.insert("", "end", values=(
                t["id"], t["date"], t["person"], t["description"],
                t["debit"], t["credit"], f"{t['amount']:,.2f}"))

    
    # REFRESH: one function to update everything after any change
    def refresh_all(self):
        names = [a["name"] for a in self.accounts]
        self.cmb_debit["values"] = names     # dropdowns list the current accounts
        self.cmb_credit["values"] = names
        self.refresh_ledger()
        self.refresh_accounts()
        self.refresh_history()


           
    # DELETE A TRANSACTION (added on the Transaction History page)
    #kani maoy naka nndot, if namali kag buhat transaction
    #pwede ragyud nimo ma delete, and ma affect tanan parts sa system na imo to gi delete na entry
    def add_delete_feature(self):
        """Adds a 'Delete Selected Transaction' button under the History table."""
        history_page = self.tree_history.master.master   # the History tab's frame
        ttk.Button(history_page, text="Delete Selected Transaction",
                   command=self.delete_transaction).pack(anchor="w", pady=8)

    def delete_transaction(self):
        """Delete the transaction selected in the History table."""
        selected = self.tree_history.selection()
        if not selected:
            messagebox.showwarning("No selection", "Click a transaction in the list first.")
            return

        trans_id = int(self.tree_history.item(selected[0], "values")[0])
        if not messagebox.askyesno(
                "Confirm delete",
                f"Delete transaction No. {trans_id}?\nThis also removes it from the Ledger "
                "and updates the account balances."):
            return

        # Remove it, then renumber so the "No." stays 1, 2, 3 with no gaps
        # (this keeps the existing "len(transactions) + 1" numbering working)
        self.transactions = [t for t in self.transactions if t["id"] != trans_id]
        for new_id, t in enumerate(self.transactions, start=1):
            t["id"] = new_id

    #after ma delete, na remove nato siya na entry sa mismo storage
        save_data(self.accounts, self.transactions)
        self.refresh_all()
        messagebox.showinfo("Deleted", "Transaction deleted.")




            # DELETE AN ACCOUNT (added on the Accounts page)
            #ari kay maka delete rakas account name kung mali imo na create
            #after ma delete ang account name, dinato siya ma display sa create transaction na page
    def add_delete_account_feature(self):
        """Adds a 'Delete Selected Account' button under the Accounts page."""
        accounts_page = self.tree_accounts.master.master   # the Accounts tab's frame
        ttk.Button(accounts_page, text="Delete Selected Account",
                   command=self.delete_account).pack(anchor="w", pady=4)

    def delete_account(self):
        """Delete the account (name and type) selected in the Accounts table."""
        selected = self.tree_accounts.selection()
        if not selected:
            messagebox.showwarning("No selection", "Click an account in the list first.")
            return

        # The table is filled in the same order as self.accounts, so the row position
        # tells us exactly which account was selected
        index = self.tree_accounts.index(selected[0])
        acc = self.accounts[index]

        # Protect the books: don't delete an account that has transactions
        #ari bawal ka maka delete ato na account name if naka input ka as transaction/entry
        #bawalan ka i delete ang account name, unless imo i delete ang transaction/entry history
        used = any(t["debit"] == acc["name"] or t["credit"] == acc["name"]
                   for t in self.transactions)
        if used:
            messagebox.showwarning(
                "Account in use",
                f"'{acc['name']}' has recorded transactions and can't be deleted.\n"
                "Delete those transactions first (Transaction History tab).")
            return

        if not messagebox.askyesno(
                "Confirm delete",
                f"Delete account '{acc['name']}' ({acc['type']})?"):
            return

        del self.accounts[index]

        # Clear the form dropdowns if they were showing the deleted account
        for var in (self.var_debit, self.var_credit):
            if var.get() == acc["name"]:
                var.set("")

        save_data(self.accounts, self.transactions)
        self.refresh_all()
        messagebox.showinfo("Deleted", "Account deleted.")



# SECTION 3: START THE PROGRAM
if __name__ == "__main__":
    app = AccountingApp()
    app.add_delete_feature()   # adds the delete button to the History page
    app.add_delete_account_feature()
    app.mainloop()
