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


class ReportTaxAudit(Model):
    _name = "report.tax.audit"
    _transient = True
    _fields = {
        "tax_comp_id": fields.Many2One("account.tax.component", "Tax Component"),
        "tax_type": fields.Selection([["vat", "VAT"], ["vat_exempt", "VAT Exempt"], ["vat_defer", "Deferred VAT"], ["wht", "Withholding Tax"], ["specific_business", "Specific Business Tax"]], "Tax Type", required=True),
        "trans_type": fields.Selection([["out", "Sale"], ["in", "Purchase"]], "Transaction Type", required=True),
        "date_from": fields.Date("From",required=True),
        "date_to": fields.Date("To",required=True),
    }

    def default_get(self, field_names=None, context={}, **kw):
        defaults = context.get("defaults", {})
        tax_comp_id = defaults.get("tax_comp_id")
        if tax_comp_id:
            tax_comp_id = int(tax_comp_id)
        date_from = defaults.get("date_from")
        if not date_from:
            date_from = date.today().strftime("%Y-%m-01")
        date_to = defaults.get("date_to")
        if not date_to:
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
        return {
            "tax_comp_id": tax_comp_id,
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
        tax_comp_id = params.get("tax_comp_id")
        trans_type=params.get("trans_type")
        if tax_comp_id:
            tax_comp_id=int(tax_comp_id)
            tax_comp = get_model("account.tax.component").browse(tax_comp_id)
            tax_comp_ids=[tax_comp_id]
            tax_type=tax_comp.tax_type
        else:
            tax_type=params.get("tax_type")
            if not tax_type or not trans_type:
                return
            tax_comp_ids=get_model("account.tax.component").search([["type","=",tax_type],["trans_type", "=", trans_type]])
            tax_comp=None
        date_from = params.get("date_from")
        if not date_from:
            date_from = date.today().strftime("%Y-%m-01")
        date_to = params.get("date_to")
        if not date_to:
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
        data = {
            "company_name": comp.name,
            "rate_name": tax_comp.tax_rate_id.name if tax_comp else None,
            "comp_name": tax_comp.name if tax_comp else None,
            "tax_type": tax_type,
            "date_from": date_from,
            "date_to": date_to,
        }
        db = database.get_connection()
        res=[]
        if tax_comp_ids and company_ids:
            res = db.query("SELECT inv.tax_no, m.id AS move_id,m.date,a.name AS account_name,a.code AS account_code,m.number,m.ref,l.description,case when 'in' = %s then l.debit-l.credit else l.credit-l.debit end AS tax_amount, case when l.debit-l.credit=0 then l.tax_base else case when 'in' = %s then l.tax_base*sign(l.debit-l.credit) else l.tax_base*sign(l.credit-l.debit) end end AS base_amount,c.name as contact_name,c.id as contact_id FROM account_move_line l JOIN account_move m ON m.id=l.move_id JOIN account_account a ON a.id=l.account_id LEFT JOIN contact c ON c.id=l.contact_id  left join account_invoice as inv on inv.move_id=m.id WHERE m.state='posted' AND m.date>=%s AND m.date<=%s AND l.tax_comp_id IN %s AND m.company_id IN %s ORDER BY date, inv.tax_no",
                trans_type, trans_type, date_from, date_to, tuple(tax_comp_ids), tuple(company_ids))

        data["lines"] = [dict(r) for r in res]
        data["base_total"]=sum(l["base_amount"] or 0 for l in data["lines"])
        data["tax_total"]=sum(l["tax_amount"] or 0 for l in data["lines"])
        data["credit_lines"]=[]
        return data

ReportTaxAudit.register()
