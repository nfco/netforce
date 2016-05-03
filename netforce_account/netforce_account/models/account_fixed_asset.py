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
from netforce.access import get_active_company
from netforce import database
from datetime import *
from dateutil.relativedelta import *
from pprint import pprint


class FixedAsset(Model):
    _name = "account.fixed.asset"
    _string = "Fixed Asset"
    _key = ["number"]
    _multi_company = True
    _fields = {
        "name": fields.Char("Item Name", required=True, search=True, size=256),
        "number": fields.Char("Asset Number", required=True, search=True),
        "fixed_asset_account_id": fields.Many2One("account.account", "Fixed Asset Account", required=True, search=True),
        "date_purchase": fields.Date("Purchase Date", required=True, search=True),
        "date_dispose": fields.Date("Dispose Date"),
        "track_id": fields.Many2One("account.track.categ", "Tracking-1", condition=[["type", "=", "1"]], search=True),
        "track2_id": fields.Many2One("account.track.categ", "Tracking-2", condition=[["type", "=", "2"]], search=True),
        "price_purchase": fields.Decimal("Purchase Price", required=True),
        "description": fields.Text("Description"),
        "type_id": fields.Many2One("account.fixed.asset.type", "Asset Type", required=True),
        "dep_rate": fields.Decimal("Depreciation Rate (%)", required=True),
        "dep_method": fields.Selection([["line", "Straight Line"], ["decline", "Declining Balance"]], "Depreciation Method", required=True, search=True),
        "accum_dep_account_id": fields.Many2One("account.account", "Accum. Depr. Account", required=True, search=True),
        "dep_exp_account_id": fields.Many2One("account.account", "Depr. Exp. Account", required=True, search=True),
        "state": fields.Selection([["pending", "Pending"], ["registered", "Registered"], ["disposed", "Disposed"], ["sold", "Sold"]], "Status", required=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "book_val": fields.Decimal("Book Value", function="_get_book_val", function_multi=True),
        "last_dep": fields.Date("Last depreciation", function="_get_book_val", function_multi=True),
        "company_id": fields.Many2One("company", "Company"),
        "invoice_id": fields.Many2One("account.invoice", "Invoice"),
        "periods": fields.One2Many("account.fixed.asset.period", "asset_id", "Depreciation Periods"),
        "salvage_value": fields.Decimal("Salvage Value"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
    }
    _order = "number desc"

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="fixed_asset")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id,context)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id,context)

    _defaults = {
        "state": "pending",
        "number": _get_number,
        "company_id": lambda *a: get_active_company(),
    }

    def onchange_type(self, context={}):
        data = context['data']
        type_id = data['type_id']
        if not type_id:
            return
        type = get_model("account.fixed.asset.type").browse(type_id)
        data["fixed_asset_account_id"] = type.fixed_asset_account_id.id
        data["dep_rate"] = type.dep_rate
        data["dep_method"] = type.dep_method
        data["accum_dep_account_id"] = type.accum_dep_account_id.id
        data["dep_exp_account_id"] = type.dep_exp_account_id.id
        return data

    def do_register(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state != "pending":
            raise Exception("Invalid state")
        obj.write({"state": "registered"})

    def to_pending(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state not in ("registered", "sold", "disposed"):
            raise Exception("Invalid state")
        obj.write({"state": "pending"})

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "name": obj.name,
            "fixed_asset_account_id": obj.fixed_asset_account_id.id,
            "date_purchase": obj.date_purchase,
            "price_purchase": obj.price_purchase,
            "description": obj.description,
            "type_id": obj.type_id.id,
            "dep_rate": obj.dep_rate,
            "dep_method": obj.dep_method,
            "accum_dep_account_id": obj.accum_dep_account_id.id,
            "dep_exp_account_id": obj.dep_exp_account_id.id,
            "state": "pending",
            "track_id": obj.track_id.id,
            "track2_id": obj.track2_id.id,
        }
        new_id = self.create(vals)
        new_obj = self.browse(new_id)
        msg = "Fixed asset %s copied from %s" % (new_obj.number, obj.number)
        return {
            "next": {
                "name": "fixed_asset",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": msg,
        }

    def _get_book_val(self, ids, context={}):
        vals = {}
        date = context.get("date")
        for obj in self.browse(ids):
            total_dep = 0
            for period in obj.periods:
                if date and period.date_to > date:
                    continue
                total_dep += period.amount
            book_val = obj.price_purchase - total_dep
            if obj.periods:
                last_dep = obj.periods[-1].date_to
            else:
                last_dep = None
            if obj.state in ("sold", "disposed"):
                book_val = 0
            vals[obj.id] = {
                "book_val": book_val,
                "last_dep": last_dep,
            }
        return vals

    def get_daily_rate(self, ids, date_from, context={}):
        obj = self.browse(ids)[0]
        d_from = datetime.strptime(date_from, "%Y-%m-%d")
        year = d_from.year
        d0 = datetime(year, 1, 1)
        d1 = datetime(year, 12, 31)
        year_days = (d1 - d0).days + 1
        if obj.dep_method == "line":
            year_rate = (obj.price_purchase - (obj.salvage_value or 0)) * obj.dep_rate / 100
            day_rate = year_rate / year_days
        elif obj.dep_method == "decline":
            d = datetime.strptime(obj.date_purchase, "%Y-%m-%d")
            amt = obj.price_purchase - (obj.salvage_value or 0)
            year_rate = amt * obj.dep_rate / 100
            n = 0
            while d < d_from:
                d += relativedelta(months=1)
                n += 1
                if n % 12 == 0:
                    amt -= year_rate
                    year_rate = amt * obj.dep_rate / 100
            day_rate = year_rate / year_days
        else:
            raise Exception("Invalid depreciation method for fixed asset %s" % obj.number)
        return day_rate

    def depreciate(self, ids, date_to, context={}):
        period_ids = []
        for obj in self.browse(ids):
            book_val = obj.book_val
            if obj.state != "registered":
                raise Exception("Can not depreciate fixed asset %s (invalid status)" % obj.number)
            if obj.last_dep:
                d_from = datetime.strptime(obj.last_dep, "%Y-%m-%d") + timedelta(days=1)
            else:
                d_from = datetime.strptime(obj.date_purchase, "%Y-%m-%d")
            d_to = datetime.strptime(date_to, "%Y-%m-%d")
            d0 = d_from
            while d0 <= d_to:
                d1 = min(d0 + relativedelta(day=31), d_to)
                num_days = (d1 - d0).days + 1
                rate = obj.get_daily_rate(d0.strftime("%Y-%m-%d"))
                amt = get_model("currency").round(None, num_days * rate)  # XXX
                amt = min(amt, book_val - (obj.salvage_value or 0))
                if amt <= 0:
                    break
                vals = {
                    "asset_id": obj.id,
                    "date_from": d0.strftime("%Y-%m-%d"),
                    "date_to": d1.strftime("%Y-%m-%d"),
                    "amount": amt,
                }
                period_id = get_model("account.fixed.asset.period").create(vals)
                book_val -= amt
                period_ids.append(period_id)
                d0 = d1 + timedelta(days=1)
        date_periods = {}
        for period in get_model("account.fixed.asset.period").browse(period_ids):
            date_periods.setdefault(period.date_to, []).append(period.id)
        settings = get_model("settings").browse(1)
        journal_id = settings.general_journal_id.id
        if not journal_id:
            raise Exception("General journal not found")
        for d, date_period_ids in date_periods.items():
            move_vals = {
                "date": d,
                "journal_id": journal_id,
                "narration": "Fixed asset depreciation",
                "lines": [],
            }
            lines = []
            for period in get_model("account.fixed.asset.period").browse(date_period_ids):
                asset = period.asset_id
                line_vals = {
                    "description": asset.type_id.name,
                    "account_id": asset.dep_exp_account_id.id,
                    "debit": period.amount,
                    "credit": 0,
                }
                lines.append(line_vals)
                line_vals = {
                    "description": asset.type_id.name,
                    "account_id": asset.accum_dep_account_id.id,
                    "debit": 0,
                    "credit": period.amount,
                }
                lines.append(line_vals)
            groups = {}
            for line_vals in lines:
                k = (line_vals["description"], line_vals["account_id"])
                if k not in groups:
                    groups[k] = 0
                groups[k] += line_vals["debit"] - line_vals["credit"]
            for (desc, account_id), amt in sorted(groups.items()):
                move_vals["lines"].append(("create", {
                    "description": desc,
                    "account_id": account_id,
                    "debit": amt > 0 and amt or 0,
                    "credit": amt < 0 and -amt or 0,
                }))
            pprint(move_vals)
            move_id = get_model("account.move").create(move_vals)
            get_model("account.move").post([move_id])
            for period in get_model("account.fixed.asset.period").browse(date_period_ids):
                period.write({"move_id": move_id})
                asset=period.asset_id
                for mline in get_model("account.move").browse(move_id).lines:
                    mline.write({
                        'track_id': asset.track_id.id,
                        'track2_id': asset.track2_id.id,
                    })

    def onchange_date(self, context={}):
        data = context["data"]
        ctx = {
            "date": data["date_purchase"],
        }
        number = self._get_number(context=ctx)
        data["number"] = number
        return data


FixedAsset.register()
