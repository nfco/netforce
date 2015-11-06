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
from netforce.database import get_connection
import time
import datetime
import calendar
from pprint import pprint
from datetime import datetime, timedelta
from dateutil.relativedelta import *
from netforce.access import get_active_company


def get_periods(date, period_days, num_periods):
    periods = []
    d0 = datetime.strptime(date, "%Y-%m-%d")
    date_from = d0 - timedelta(days=period_days)
    date_to = d0 - timedelta(days=1)
    periods.append({
        "date_from": date_from.strftime("%Y-%m-%d"),
        "date_to": date_to.strftime("%Y-%m-%d"),
        "period_name": "Past due %d-%d days" % ((d0 - date_to).days, (d0 - date_from).days),
        "total": 0,
    })
    for i in range(num_periods - 1):
        date_from = date_from - timedelta(days=period_days)
        date_to = date_to - timedelta(days=period_days)
        periods.append({
            "date_from": date_from.strftime("%Y-%m-%d"),
            "date_to": date_to.strftime("%Y-%m-%d"),
            "period_name": "Past due %d-%d days" % ((d0 - date_to).days, (d0 - date_from).days),
            "total": 0,
        })
    return periods


class ReportARDetails(Model):
    _name = "report.ar.details"
    _transient = True
    _fields = {
        "date": fields.Date("Date", required=True),
        "contact_id": fields.Many2One("contact", "Contact"),
        "contact_categ_id": fields.Many2One("contact.categ", "Contact Categories"),
        "period_days": fields.Integer("Period Days", required=True),
        "num_periods": fields.Integer("Number of Periods", required=True),
    }

    _defaults = {
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "period_days": 30,
        "num_periods": 3,
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
        date = params.get("date")
        if not date:
            date = time.strftime("%Y-%m-%d")
        d0 = datetime.strptime(date, "%Y-%m-%d")
        contact_id = params.get("contact_id")
        if contact_id:
            contact_id = int(contact_id)
        contact_categ_id = params.get("contact_categ_id")
        if contact_categ_id:
            contact_categ_id = int(contact_categ_id)
        period_days = params.get("period_days", 30)
        num_periods = params.get("num_periods", 3)
        periods = get_periods(date, period_days, num_periods)
        print("periods", periods)
        date_from_current = d0
        date_to_older = d0 - timedelta(days=period_days * num_periods + 1)
        db = get_connection()
        q = "SELECT l.id,m.number AS number,m.ref AS ref,i.number AS inv_number,l.move_date AS doc_date,COALESCE(i.due_date,l.due_date,l.move_date) AS due_date,p.name as contact_name,p.id as contact_id,l.debit-l.credit as amount,l.reconcile_id FROM account_move_line l JOIN account_move m ON m.id=l.move_id JOIN account_account a ON a.id=l.account_id LEFT JOIN contact p ON p.id=l.contact_id LEFT JOIN account_invoice i ON i.reconcile_move_line_id=l.id WHERE move_state='posted' AND a.type='receivable' AND a.company_id IN %s AND l.move_date<=%s"
        args = [tuple(company_ids), date]
        if contact_id:
            q += " AND l.contact_id=%s"
            args.append(contact_id)
        if contact_categ_id:
            q += " AND p.categ_id=%s"
            args.append(contact_categ_id)
        q += " ORDER BY m.date"
        res = db.query(q, *args)
        contacts = {}
        data = {
            "company_name": comp.name,
            "date": date,
            "periods": periods,
            "total_current": 0,
            "total_older": 0,
            "total": 0,
        }
        rec_bals = {}
        for r in res:
            if r.reconcile_id:
                rec_bals.setdefault(r.reconcile_id, 0)
                rec_bals[r.reconcile_id] += r.amount
        for r in res:
            if r.reconcile_id and abs(rec_bals[r.reconcile_id]) < 0.001:
                continue
            contact = contacts.get(r.contact_id)
            if contact is None:
                contact = {
                    "contact_id": r.contact_id,
                    "contact_name": r.contact_name or " N/A",
                    "amount_current": 0,
                    "amount_older": 0,
                    "amount_total": 0,
                    "periods": [],
                    "date_from_current": date_from_current.strftime("%Y-%m-%d"),
                    "date_to_older": date_to_older.strftime("%Y-%m-%d"),
                    "details": [],
                }
                for p in periods:
                    contact["periods"].append({
                        "date_from": p["date_from"],
                        "date_to": p["date_to"],
                        "amount": 0,
                    })
                contacts[r.contact_id] = contact

            period = None
            for p in periods:
                if p["date_from"] <= r.due_date and p["date_to"] >= r.due_date:
                    period = p
                    break
            if period:
                period["total"] += r.amount
            elif periods and r.due_date > periods[0]["date_to"]:
                data["total_current"] += r.amount
            elif periods and r.due_date < periods[-1]["date_from"]:
                data["total_older"] += r.amount
            data["total"] += r.amount

            period = None
            for p in contact["periods"]:
                if p["date_from"] <= r.due_date and p["date_to"] >= r.due_date:
                    period = p
                    break
            if period:
                period["amount"] += r.amount
            elif periods and r.due_date > periods[0]["date_to"]:
                contact["amount_current"] += r.amount
            elif periods and r.due_date < periods[-1]["date_from"]:
                contact["amount_older"] += r.amount
            contact["amount_total"] += r.amount

            detail_vals = {
                "id": r.id,
                "number": r.inv_number or r.number,  # XXX
                "ref": r.ref,
                "doc_date": r.doc_date,
                "due_date": r.due_date,
                "amount": r.amount,
                "periods": [],
            }
            for p in periods:
                vals = {
                    "date_from": p["date_from"],
                    "date_to": p["date_to"],
                }
                if p["date_from"] <= r.due_date and p["date_to"] >= r.due_date:
                    vals["amount"] = r.amount
                detail_vals["periods"].append(vals)
            if periods and r.due_date > periods[0]["date_to"]:
                detail_vals["amount_current"] = r.amount
            if periods and r.due_date < periods[-1]["date_from"]:
                detail_vals["amount_older"] = r.amount
            contact["details"].append(detail_vals)

        data["lines"] = list(contacts.values())
        data["lines"].sort(key=lambda c: c["contact_name"])
        pprint(data)
        return data

ReportARDetails.register()
