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
from datetime import *
from dateutil.relativedelta import *
from netforce import database
from netforce.access import get_active_company


class ReportAccountTrans(Model):
    _name = "report.account.trans"
    _transient = True
    _fields = {
        "account_id": fields.Many2One("account.account", "Account", condition=[["type", "!=", "view"]], required=True, on_delete="cascade"),
        "date_from": fields.Date("From"),
        "date_to": fields.Date("To"),
        "contact_id": fields.Many2One("contact", "Contact"),
        "track_id": fields.Many2One("account.track.categ", "Tracking"),
        "track2_id": fields.Many2One("account.track.categ", "Tracking-2"),
        "description": fields.Char("Description"),
        "cash_basis": fields.Boolean("Cash Basis"),
    }

    def default_get(self, field_names=None, context={}, **kw):
        defaults = context.get("defaults", {})
        account_id = defaults.get("account_id")
        if account_id:
            account_id = int(account_id)
        date_from = defaults.get("date_from")
        date_to = defaults.get("date_to")
        if not date_from and not date_to:
            date_from = date.today().strftime("%Y-%m-01")
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
        track_id = defaults.get("track_id") or None
        if track_id:
            track_id = int(track_id)
        track2_id = defaults.get("track2_id") or None
        if track2_id:
            track2_id = int(track2_id)
        cash_basis = defaults.get("cash_basis")
        return {
            "account_id": account_id,
            "date_from": date_from,
            "date_to": date_to,
            "track_id": track_id,
            "track2_id": track2_id,
            "cash_basis": cash_basis,
        }

    def get_report_data(self, ids, context={}):
        company_id = get_active_company()
        comp = get_model("company").browse(company_id)
        if ids:
            params = self.read(ids, load_m2o=False)[0]
        else:
            params = self.default_get(load_m2o=False, context=context)
        settings = get_model("settings").browse(1)
        db = database.get_connection()
        if not params.get("account_id"):
            return
        account_id = int(params.get("account_id"))
        acc = get_model("account.account").browse(account_id)
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if not date_from and not date_to:
            date_from = date.today().strftime("%Y-%m-01")
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
        if not date_from:
            res = db.get(
                "SELECT min(m.date) AS min_date FROM account_move m, account_move_line l WHERE m.id=l.move_id AND l.account_id=%s", account_id)
            if res:
                date_from = res.min_date
            else:
                date_from = date.today().strftime("%Y-%m-01")
        contact_id = params.get("contact_id")
        if contact_id:
            contact_id = int(contact_id)
        description = params.get("description")
        track_id = params.get("track_id")
        if track_id:
            track_id = int(track_id)
        track2_id = params.get("track2_id")
        if track2_id:
            track2_id = int(track2_id)
        if params.get("cash_basis"):
            res = db.query(
                "SELECT l1.id,m1.date,m1.number,m1.ref,l1.description,l2.debit*(l4.credit-l4.debit)/(l3.debit-l3.credit) as debit,l2.credit*(l4.credit-l4.debit)/(l3.debit-l3.credit) as credit FROM account_move m1,account_move_line l1,account_account a1,account_move_line l2,account_move_line l3,account_move_line l4 WHERE m1.state='posted' AND m1.date>=%s AND m1.date<=%s AND m1.id=l1.move_id AND m1.id=l2.move_id AND a1.id=l1.account_id AND a1.type='bank' AND l2.reconcile_id=l3.reconcile_id AND l3.id!=l2.id AND l4.move_id=l3.move_id AND l4.id!=l3.id AND l4.account_id=%s", date_from, date_to, account_id)
            objs = []
            for r in res:
                objs.append({
                    "id": r.id,
                    "move_date": r.date,
                    "move_number": r.number,
                    "move_ref": r.ref,
                    "description": r.description,
                    "debit": r.debit,
                    "credit": r.credit,
                })
        else:
            condition = [["account_id", "=", account_id], ["move_id.state", "=", "posted"]]
            if date_from:
                condition.append(["move_id.date", ">=", date_from])
            if date_to:
                condition.append(["move_id.date", "<=", date_to])
            if contact_id:
                condition.append(["contact_id", "=", contact_id])
            if track_id:
                condition.append(["track_id", "=", track_id])
            if track2_id:
                condition.append(["track2_id", "=", track2_id])
            if description:
                condition.append(["description", "ilike", description])
            ids = get_model("account.move.line").search(condition, order="move_date")
            objs = get_model("account.move.line").read(
                ids, ["move_date", "move_number", "description", "contact_id", "move_ref", "debit", "credit", "amount_cur"])
        total_debit = sum([o["debit"] for o in objs])
        total_credit = sum([o["credit"] for o in objs])
        total_amount_cur = sum([o["amount_cur"] or 0 for o in objs])
        balance = total_debit - total_credit
        data = {
            "company_name": comp.name,
            "date_from": date_from,
            "date_to": date_to,
            "objs": objs,
            "totals": {
                "debit": total_debit,
                "credit": total_credit,
                "amount_cur": total_amount_cur,
            },
            "account_name": acc.name,
            "balance_debit": balance > 0 and balance or 0,
            "balance_credit": balance < 0 and -balance or 0,
        }
        return data

ReportAccountTrans.register()
