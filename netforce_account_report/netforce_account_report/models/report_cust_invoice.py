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
from netforce.database import get_connection
from netforce.access import get_active_company


class ReportCustInvoice(Model):
    _name = "report.cust.invoice"
    _transient = True
    _fields = {
        "date_from": fields.Date("From"),
        "date_to": fields.Date("To"),
        "contact_id": fields.Many2One("contact", "Contact", on_delete="cascade"),
        "show_details": fields.Boolean("Show Details"),
    }

    def default_get(self, field_names=None, context={}, **kw):
        defaults = context.get("defaults", {})
        contact_id = defaults.get("contact_id")
        if contact_id:
            contact_id = int(contact_id)
        datenow = datetime.now().strftime("%Y-%m-%d")
        date_from = defaults.get("date_from",datenow)
        date_to = defaults.get("date_to",datenow)
        return {
            "contact_id": contact_id,
            "date_from": date_from,
            "date_to": date_to,
        }

    def get_report_data(self, ids, context={}):
        company_id = get_active_company()
        company_ids = get_model("company").search([["id", "child_of", company_id]])
        comp = get_model("company").browse(company_id)
        if ids:
            params = self.read(ids, load_m2o=False)[0]
        else:
            params = self.default_get(load_m2o=False, context=context)
        settings = get_model("settings").browse(1)
        company_name = comp.name
        contact_id = params.get("contact_id")
        if contact_id:
            contact_id = int(contact_id)
        date_from = params.get("date_from")
        date_to = params.get("date_to")
        show_details = params.get("show_details")
        db = get_connection()
        q = "SELECT l.id,m.date AS move_date,l.contact_id,p.name AS contact_name,m.number AS move_number,l.description,COALESCE(l.due_date,m.date) AS due_date,l.debit-l.credit AS total_amount,r.number AS reconcile_number,l.reconcile_id FROM account_move_line l JOIN account_account a ON a.id=l.account_id JOIN account_move m ON m.id=l.move_id LEFT JOIN contact p ON p.id=l.contact_id LEFT JOIN account_reconcile r ON r.id=l.reconcile_id WHERE l.move_state='posted' AND a.type='receivable' AND a.company_id IN %s"
        args = [tuple(company_ids)]
        if date_from:
            q += " AND COALESCE(l.due_date,l.move_date)>=%s"
            args.append(date_from)
        if date_to:
            q += " AND COALESCE(l.due_date,l.move_date)<=%s"
            args.append(date_to)
        if contact_id:
            q += " AND l.contact_id=%s"
            args.append(contact_id)
        #else:
            #q += " AND l.contact_id IS NULL"  # XXX
        if not show_details:
            q += " AND (l.reconcile_id IS NULL OR r.balance!=0)"
        q += " ORDER BY COALESCE(l.due_date,m.date),l.id"
        res = db.query(q, *args)
        lines = []
        for r in res:
            vals = dict(r)
            if vals["reconcile_number"] and not vals["reconcile_number"].endswith("*"):
                vals["due_amount"] = 0
            else:
                vals["due_amount"] = vals["total_amount"]
            lines.append(vals)
        data = {
            "company_name": company_name,
            "date_from": date_from,
            "date_to": date_to,
            "lines": lines,
            "totals": {
                "amount_total": sum(l["due_amount"] for l in lines),
            }
        }
        return data

ReportCustInvoice.register()
