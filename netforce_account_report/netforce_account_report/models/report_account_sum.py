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


class ReportAccountSum(Model):
    _name = "report.account.sum"
    _transient = True
    _fields = {
        "account_id": fields.Many2One("account.account", "Account", condition=[["type", "!=", "view"]], required=True, on_delete="cascade"),
        "date_from": fields.Date("From"),
        "date_to": fields.Date("To"),
        "contact_id": fields.Many2One("contact", "Contact"),
        "track_id": fields.Many2One("account.track.categ", "Tracking"),
        "track2_id": fields.Many2One("account.track.categ", "Tracking-2"),
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
        contact_id = defaults.get("contact_id") or None
        if contact_id:
            contact_id = int(contact_id)
        track_id = defaults.get("track_id") or None
        if track_id:
            track_id = int(track_id)
        track2_id = defaults.get("track2_id") or None
        if track2_id:
            track2_id = int(track2_id)
        return {
            "account_id": account_id,
            "date_from": date_from,
            "date_to": date_to,
            "contact_id": contact_id,
            "track_id": track_id,
            "track2_id": track2_id,
        }

    def get_report_data(self, ids, context={}):
        company_id = get_active_company()
        comp = get_model("company").browse(company_id)
        if ids:
            params = self.read(ids, load_m2o=False)[0]
        else:
            params = self.default_get(load_m2o=False, context=context)
        settings = get_model("settings").browse(1)
        if not params.get("account_id"):
            return
        account_id = int(params.get("account_id"))
        account = get_model("account.account").browse(account_id)
        date_from = params.get("date_from")
        if not date_from:
            db = database.get_connection()
            res = db.get(
                "SELECT min(m.date) AS min_date FROM account_move_line l,account_move m WHERE m.id=l.move_id AND l.account_id=%s AND m.state='posted'", account_id)
            if not res:
                return
            date_from = res["min_date"][:7] + "-01"
        date_to = params.get("date_to")
        if not date_to:
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
        contact_id = params.get("contact_id")
        if contact_id:
            contact_id = int(contact_id)
        track_id = params.get("track_id")
        if track_id:
            track_id = int(track_id)
        track2_id = params.get("track_id")
        if track2_id:
            track2_id = int(track2_id)
        data = {
            "company_name": comp.name,
            "date_from": date_from,
            "date_to": date_to,
            "contact_id": contact_id,
            "track_id": track_id,
            "track2_id": track2_id,
            "account_name": account.name,
            "company_currency_code": settings.currency_id.code, 
            "account_currency_code": account.currency_id.code, 
            "lines": [],
            "total": 0,
            "total_cur": 0,
        }
        d0 = datetime.strptime(date_from, "%Y-%m-%d")
        d2 = datetime.strptime(date_to, "%Y-%m-%d")
        while d0 <= d2:
            d1 = d0 + relativedelta(day=31)
            if d1 > d2:
                d1 = d2
            ctx = {
                "date_from": d0.strftime("%Y-%m-%d"),
                "date_to": d1.strftime("%Y-%m-%d"),
                "contact_id": contact_id,
                "track_id": track_id,
                "track2_id": track2_id,
            }
            acc = get_model("account.account").read([account_id], ["balance","balance_cur"], context=ctx)[0]
            balance = acc["balance"]
            balance_cur = acc["balance_cur"]
            line = {
                "account_id": account_id,
                "month": d0.strftime("%B %Y"),
                "balance": balance,
                "balance_cur": balance_cur,
                "date_from": d0.strftime("%Y-%m-%d"),
                "date_to": d1.strftime("%Y-%m-%d"),
            }
            data["lines"].append(line)
            data["total"] += line["balance"]
            data["total_cur"] += line["balance_cur"]
            d0 = d1 + timedelta(days=1)
        return data

ReportAccountSum.register()
