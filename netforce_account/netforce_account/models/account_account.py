# Copyright (c) 2012-2015 Netforce Co. Ltd.
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE
# OR OTHER DEALINGS IN THE SOFTWARE.

from netforce.model import Model, fields, get_model
import time
from netforce import database
import datetime
from netforce.access import get_active_company, set_active_company
import bisect


class Account(Model):
    _name = "account.account"
    _string = "Account"
    _audit_log = True
    _key = ["code", "company_id"]
    _export_field = "code"
    _multi_company = True
    _fields = {
        "code": fields.Char("Account Code", required=True, search=True, index=True),
        "name": fields.Char("Account Name", size=256, required=True, search=True, translate=True),
        "type": fields.Selection([
            ["_group", "Assets"],
            ["cash", "Cash"],
            ["cheque", "Cheque"],
            ["bank", "Bank Account"],
            ["receivable", "Receivable"],
            ["cur_asset", "Current Asset"],
            ["fixed_asset", "Fixed Asset"],
            ["noncur_asset", "Non-current Asset"],
            ["_group", "Liabilities"],
            ["payable", "Payable"],
            ["cust_deposit", "Customer Deposit"],
            ["cur_liability", "Current Liability"],
            ["noncur_liability", "Non-current Liability"],
            ["_group", "Equity "],#add some space for prevent import wrong type
            ["equity", "Equity"],
            ["_group", "Expenses"],
            ["cost_sales", "Cost of Sales"],
            ["expense", "Expense"],
            ["other_expense", "Other Expense"],
            ["_group", "Income"],
            ["revenue", "Revenue"],
            ["other_income", "Other Income"],
            ["_group", "Other"],
            ["view", "View"],
            ["other", "Other"]], "Type", required=True, search=True, index=True),

        "parent_id": fields.Many2One("account.account", "Parent", condition=[["type", "=", "view"]]),
        "bank_type": fields.Selection([["bank", "Bank Account"], ["credit_card", "Credit Card"], ["paypal", "Paypal"]], "Bank Type"),
        "description": fields.Text("Description"),
        "tax_id": fields.Many2One("account.tax.rate", "Tax"),
        "balance": fields.Decimal("Accounting Balance", function="get_balance", function_multi=True),
        "debit": fields.Decimal("Debit", function="get_balance", function_multi=True),
        "credit": fields.Decimal("Credit", function="get_balance", function_multi=True),
        "balance_statement": fields.Decimal("Statement Balance", function="get_balance_statement"),
        "bank_name": fields.Char("Bank Name"),
        "currency_id": fields.Many2One("currency", "Account Currency", required=True),
        "bank_no": fields.Char("Bank Account Number"),
        "creditcard_no": fields.Char("Credit Card Number"),
        "balance_90d": fields.Json("Balance 90d", function="get_balance_90d"),
        "active": fields.Boolean("Active"),
        "unrec_num": fields.Integer("Unreconciled Items", function="get_unrec_num"),
        "enable_payment": fields.Boolean("Enable payments to this account"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "currency_id": fields.Many2One("currency", "Account Currency", required=True),
        "balance_cur": fields.Decimal("Accounting Balance (Cur)", function="get_balance", function_multi=True),
        "company_id": fields.Many2One("company", "Company"),
        "fixed_asset_type_id": fields.Many2One("account.fixed.asset.type", "Fixed Asset Type"),
        "statements": fields.One2Many("account.statement", "account_id", "Bank Statements"),
        "move_lines": fields.One2Many("account.move.line", "account_id", "Account Transactions", order="move_date desc"),
        "require_contact": fields.Boolean("Require Contact"),
        "require_tax_no": fields.Boolean("Require Tax No"),
        "require_track": fields.Boolean("Require Tracking Category"),
        "require_track2": fields.Boolean("Require Secondary Tracking Category"),
        "company_currency_id": fields.Many2One("currency", "Company Currency", function="get_company_currency"),
    }
    _order = "code"

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    _defaults = {
        "active": True,
        "company_id": lambda *a: get_active_company(),
        "currency_id": _get_currency,
    }
    _constraints = ["_check_cycle"]

    def name_search(self, name, condition=[], limit=None, context={}):
        if name.isdigit():
            cond = [["code", "=ilike", name + "%"], condition]
        else:
            cond = [["or", ["name", "ilike", name], ["code", "=ilike", name + "%"]], condition]
        ids = self.search(cond, limit=limit)
        return self.name_get(ids, context)

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = "[%s] %s" % (obj.code, obj.name)
            vals.append((obj.id, name))
        return vals

    def delete(self, ids, **kw):
        move_ids = []
        move_ids = get_model("account.move").search([["lines.account_id", "in", ids], ["state", "=", "posted"]])
        if move_ids:
            raise Exception("This account can't be deleted because it is used in some posted accounting transactions")
        move_ids = get_model("account.move").search([["lines.account_id", "in", ids]])
        get_model("account.move").delete(move_ids)
        super().delete(ids, **kw)

    def get_balance_statement(self, ids, context={}):
        db = database.get_connection()
        vals = {}
        for id in ids:
            res = db.get(
                "SELECT l.balance FROM account_statement_line l,account_statement s WHERE s.id=l.statement_id AND s.account_id=%s ORDER BY l.date DESC,l.id DESC LIMIT 1", id)
            bal = res.balance if res else 0
            vals[id] = bal
        return vals

    def get_balance(self, ids, context={}, nocache=False):
        print("Account.get_balance", ids, context)
        date_from = context.get("date_from")
        date_to = context.get("date_to")
        track_id = context.get("track_id")
        track2_id = context.get("track2_id")
        currency_id = context.get("currency_id")
        contact_id = context.get("contact_id")
        bank_rec_state = context.get("bank_rec_state")
        excl_date_to = context.get("excl_date_to")
        journal_id = context.get("journal_id")
        print("#########################################################################")
        print("get_balance CACHE MISS", ids)
        db = database.get_connection()

        def _get_balance(ids, date_from=None, date_to=None, track_id=None, track2_id=None, journal_id=None, contact_id=None, bank_rec_state=None, excl_date_to=None, nocache=False):
            if not ids:
                return {}
            if not nocache and not date_from and not date_to and not track_id and not track2_id and not journal_id and not contact_id and not bank_rec_state and not excl_date_to:
                acc_bals = get_model("field.cache").get_value("account.account", "balance", ids)
                remain_ids = [id for id in ids if id not in acc_bals]
                if remain_ids:
                    res = _get_balance(remain_ids, nocache=True)
                    for id, vals in res.items():
                        acc_bals[id] = vals
                        get_model("field.cache").set_value("account.account", "balance", id, vals)
                return acc_bals
            q = "SELECT l.account_id,SUM(l.debit) AS debit,SUM(l.credit) AS credit,SUM(COALESCE(l.amount_cur,l.debit-l.credit)) AS amount_cur FROM account_move_line l JOIN account_move m ON m.id=l.move_id WHERE l.account_id IN %s AND m.state='posted'"
            q_args = [tuple(ids)]
            if date_from:
                q += " AND m.date>=%s"
                q_args.append(date_from)
            if date_to:
                if excl_date_to:
                    q += " AND m.date<%s"
                else:
                    q += " AND m.date<=%s"
                q_args.append(date_to)
            if track_id:
                track_ids = get_model("account.track.categ").search([["id", "child_of", track_id]])
                q += " AND l.track_id IN %s"
                q_args.append(tuple(track_ids))
            if track2_id:
                track2_ids = get_model("account.track.categ").search([["id", "child_of", track2_id]])
                q += " AND l.track2_id IN %s"
                q_args.append(tuple(track2_ids))
            if contact_id:
                q += " AND l.contact_id=%s"
                q_args.append(contact_id)
            if bank_rec_state:
                q += " AND m.state=%s"
                q_args.append(bank_rec_state)
            if journal_id:
                q += " AND m.journal_id=%s"
                q_args.append(journal_id)
            q += " GROUP BY l.account_id"
            res = db.query(q, *q_args)
            id_res = {}
            for r in res:
                id_res[r.account_id] = r
            vals = {}
            for id in ids:
                r = id_res.get(id)
                vals[id] = {
                    "debit": r["debit"] if r else 0,
                    "credit": r["credit"] if r else 0,
                    "balance": r["debit"] - r["credit"] if r else 0,
                    "balance_cur": r["amount_cur"] if r else 0,
                }
            return vals

        def _conv_currency(bals):
            if not bals:
                return {}
            comp_cur = {}
            comp_id = get_active_company()
            for comp in get_model("company").search_browse([]):
                set_active_company(comp.id)
                comp_settings = get_model("settings").browse(1)
                comp_cur[comp.id] = comp_settings.currency_id.id
            set_active_company(comp_id)
            acc_ids = bals.keys()
            res = db.query("SELECT id,code,currency_id,company_id,type FROM account_account WHERE id IN %s", tuple(acc_ids))
            acc_cur = {}
            acc_comp = {}
            acc_rate_type = {}
            rate_sell = ["cash","cheque","bank","receivable","cur_asset","fixed_asset","noncur_asset","revenue","other_income"]
            for r in res:
                if not r["currency_id"]:
                    raise Exception("Missing currency for account %s" % r["code"])
                acc_cur[r["id"]] = r["currency_id"]
                acc_comp[r["id"]] = r["company_id"]
                if r["type"]in rate_sell:
                    acc_rate_type[r["id"]] = "sell"
                else:
                    acc_rate_type[r["id"]] = "buy"
            bals2 = {}
            settings = get_model('settings').browse(1)
            for acc_id, vals in bals.items():
                comp_id = acc_comp.get(acc_id)
                comp_currency_id = comp_cur.get(comp_id) or settings.currency_id.id
                acc_currency_id = acc_cur[acc_id]
                rate_type = acc_rate_type[acc_id]
                bals2[acc_id] = {
                    "debit": get_model("currency").convert(vals["debit"], comp_currency_id, currency_id, date=date_to, rate_type=rate_type),
                    "credit": get_model("currency").convert(vals["credit"], comp_currency_id, currency_id, date=date_to, rate_type=rate_type),
                    "balance": get_model("currency").convert(vals["balance"], comp_currency_id, currency_id, date=date_to, rate_type=rate_type),
                    "balance_cur": get_model("currency").convert(vals["balance_cur"], acc_currency_id, currency_id, date=date_to, rate_type=rate_type),
                }
            return bals2
        acc_bals = _get_balance(ids, date_from=date_from, date_to=date_to, track_id=track_id,
                                track2_id=track2_id, journal_id=journal_id, contact_id=contact_id, bank_rec_state=bank_rec_state, excl_date_to=excl_date_to)
        pl_types = ("revenue", "other_income", "cost_sales", "expense", "other_expense")
        pl_acc_ids = self.search([["type", "in", pl_types]])
        ret_acc_ids = {}
        comp_id = get_active_company()
        for comp in get_model("company").search_browse([]):
            set_active_company(comp.id)
            comp_settings = get_model("settings").browse(1)
            ret_acc_ids[comp.id] = comp_settings.retained_earnings_account_id.id
        set_active_company(comp_id)
        if (set(ids) & set(pl_acc_ids) or set(ids) & set(ret_acc_ids.values())) and not context.get("no_close"):
            pl_acc_comps = {}
            for acc in self.browse(pl_acc_ids):
                pl_acc_comps[acc.id] = acc.company_id.id
            if date_from:
                pl_date_from = get_model("settings").get_fiscal_year_start(date_from)
            else:
                pl_date_from = None
            pl_date_to = get_model("settings").get_fiscal_year_start(date_to)
            pl_date_to = (datetime.datetime.strptime(pl_date_to, "%Y-%m-%d") -
                          datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            if not pl_date_from or pl_date_from <= pl_date_to:
                pl_bals = _get_balance(pl_acc_ids, date_from=pl_date_from, date_to=pl_date_to,
                                       track_id=track_id, track2_id=track2_id, journal_id=journal_id, contact_id=contact_id, bank_rec_state=bank_rec_state)
                ret_amts = {}
                for acc_id, pl_vals in pl_bals.items():
                    comp_id = pl_acc_comps[acc_id]
                    ret_amts.setdefault(comp_id, 0)
                    ret_amts[comp_id] += pl_vals["balance"]
                    if acc_id in acc_bals:
                        acc_vals = acc_bals[acc_id]
                        bal = acc_vals["balance"] - pl_vals["balance"]
                        acc_vals["debit"] = bal > 0 and bal or 0
                        acc_vals["credit"] = bal < 0 and -bal or 0
                        acc_vals["balance"] = bal
                        acc_vals["balance_cur"] = bal
                for comp_id, ret_amt in ret_amts.items():
                    ret_acc_id = ret_acc_ids.get(comp_id)
                    if not ret_acc_id or ret_acc_id not in acc_bals:
                        continue
                    acc_vals = acc_bals[ret_acc_id]
                    bal = acc_vals["balance"] + ret_amt
                    acc_vals["debit"] = bal > 0 and bal or 0
                    acc_vals["credit"] = bal < 0 and -bal or 0
                    acc_vals["balance"] = bal
                    acc_vals["balance_cur"] = bal
        if currency_id:
            acc_bals = _conv_currency(acc_bals)
        return acc_bals

    def get_balance_90d(self, ids, context={}, nocache=False):
        if not nocache:
            min_ctime = time.strftime("%Y-%m-%d 00:00:00")
            vals = get_model("field.cache").get_value("account.account", "balance_90d", ids, min_ctime=min_ctime)
            remain_ids = [id for id in ids if id not in vals]
            if remain_ids:
                res = self.get_balance_90d(remain_ids, context=context, nocache=True)
                for id, data in res.items():
                    vals[id] = data
                    get_model("field.cache").set_value("account.account", "balance_90d", id, data)
            return vals
        print("#########################################################################")
        print("get_balance_90d CACHE MISS", ids)
        date_from = datetime.date.today() - datetime.timedelta(days=90)
        date_to = datetime.date.today()
        db = database.get_connection()
        vals = {}
        for id in ids:
            balance = self.get_balance([id], context={"date_to": date_from.strftime("%Y-%m-%d")})[id]["balance"]
            q = "SELECT move_date,debit,credit FROM account_move_line WHERE account_id=%s AND move_date>%s AND move_date<=%s AND move_state='posted' ORDER BY move_date"
            res = db.query(q, id, date_from, date_to)
            d = date_from
            data = []
            for r in res:
                while d.strftime("%Y-%m-%d") < r["move_date"]:
                    data.append([time.mktime(d.timetuple()) * 1000, balance])
                    d += datetime.timedelta(days=1)
                balance += (r["debit"] or 0) - (r["credit"] or 0)
            while d <= date_to:
                data.append([time.mktime(d.timetuple()) * 1000, balance])
                d += datetime.timedelta(days=1)
            vals[id] = data
        return vals

    def get_template(self, context={}):
        obj = self.browse(int(context["active_id"]))
        if not obj.bank_type:
            return "account_form"
        elif obj.bank_type == "bank":
            return "account_form_bank"
        elif obj.bank_type == "credit_card":
            return "account_form_credit_card"
        elif obj.bank_type == "paypal":
            return "account_form_paypal"

    def get_unrec_num(self, ids, context={}):
        db = database.get_connection()
        res = db.query(
            "SELECT st.account_id,count(*) FROM account_statement_line stl JOIN account_statement st ON st.id=stl.statement_id WHERE stl.state='not_reconciled' AND st.account_id IN %s GROUP BY st.account_id", tuple(ids))
        vals = {}
        for r in res:
            vals[r.account_id] = r.count
        return vals

    def auto_bank_reconcile(self, ids, context={}):
        print("auto_bank_reconcile", ids)
        acc_lines = {}
        for acc_line in get_model("account.move.line").search_browse([["account_id", "in", ids], ["state", "=", "not_reconciled"]], order="move_date"):
            k = "%s %.2f %.2f" % (acc_line.account_id.id, acc_line.debit, acc_line.credit)
            acc_lines.setdefault(k, []).append((acc_line.move_id.date, acc_line.description, acc_line.id))
        recs = {}
        for st_line in get_model("account.statement.line").search_browse([["statement_id.account_id", "in", ids], ["state", "=", "not_reconciled"]], order="date"):
            k = "%s %.2f %.2f" % (st_line.statement_id.account_id.id, st_line.received, st_line.spent)
            st_date = datetime.datetime.strptime(st_line.date, "%Y-%m-%d")
            for acc_date_, acc_desc, acc_line_id in acc_lines.get(k, []):
                acc_date = datetime.datetime.strptime(acc_date_, "%Y-%m-%d")
                date_diff = abs((acc_date - st_date).days)
                desc_match = acc_desc and st_line.description and acc_desc.strip(
                ).lower() == st_line.description.strip().lower()
                prev_rec = recs.get((acc_line_id, st_line.id))
                if not prev_rec or desc_match and not prev_rec["desc_match"] or date_diff < prev_rec["date_diff"]:
                    recs[(acc_line_id, st_line.id)] = {
                        "desc_match": desc_match,
                        "date_diff": date_diff,
                    }
        print("recs", recs)
        for acc_line_id, st_line_id in recs:
            get_model("account.statement.line").write([st_line_id], {"move_lines": [("set", [acc_line_id])]})

    def get_company_currency(self, ids, context={}):
        comp_cur = {}
        comp_id = get_active_company()
        for comp in get_model("company").search_browse([]):
            set_active_company(comp.id)
            comp_settings = get_model("settings").browse(1)
            comp_cur[comp.id] = comp_settings.currency_id.id
        set_active_company(comp_id)
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = comp_cur.get(obj.company_id.id)
        return vals

Account.register()
