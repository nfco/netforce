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
from datetime import *
from dateutil.relativedelta import *
from collections import defaultdict
from pprint import pprint


class ReportDepSchedule(Model):
    _name = "report.dep.schedule"
    _transient = True
    _fields = {
        "date_from": fields.Date("From", required=True),
        "date_to": fields.Date("To", required=True),
        "track_id": fields.Many2One("account.track.categ", "Tracking-1"),
        "track2_id": fields.Many2One("account.track.categ", "Tracking-2"),
    }

    _defaults = {
        "date_from": lambda *a: date.today().strftime("%Y-01-01"),
        "date_to": lambda *a: (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d"),
    }

    def get_report_data(self, ids, context={}):
        company_id = get_active_company()
        comp = get_model("company").browse(company_id)
        if ids:
            params = self.read(ids, load_m2o=False)[0]
        else:
            params = self.default_get(load_m2o=False, context=context)
        date_from = params["date_from"]
        date_to = params["date_to"]
        track_id = params.get("track_id")
        track2_id = params.get("track2_id")
        assets = {}
        cond = [["state", "=", "registered"],["date_purchase","<=",date_to]]
        if track_id:
            cond.append(["track_id", "=", track_id])
        if track2_id:
            cond.append(["track2_id", "=", track2_id])
        for asset in get_model("account.fixed.asset").search_browse(cond, context={"date": date_from}):
            vals = {
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_number": asset.number,
                "type_name": asset.type_id.name,
                "rate": asset.dep_rate,
                "purchase_price": asset.price_purchase,
                "purchase_date": asset.date_purchase,
                "book_val_from": asset.book_val,
                "track_id": asset.track_id.id,
                "track_name": asset.track_id.name,
                "track2_id": asset.track2_id.id,
                "track2_name": asset.track2_id.name,
            }
            assets[asset.id] = vals
        for asset in get_model("account.fixed.asset").search_browse(cond, context={"date": date_to}):
            vals = assets[asset.id]
            vals["book_val_to"] = asset.book_val
            vals["accum_dep"] = vals["book_val_from"] - vals["book_val_to"]
        lines = sorted(assets.values(), key=lambda v: (v["type_name"], v["asset_name"]))
        groups = []
        cur_group = None
        for line in lines:
            if not cur_group or line["type_name"] != cur_group["type_name"]:
                cur_group = {
                    "type_name": line["type_name"],
                    "lines": [],
                }
                groups.append(cur_group)
            cur_group["lines"].append(line)
        for group in groups:
            group['lines'] = sorted(group['lines'],key=lambda l: l['purchase_date'])
            group.update({
                "total_book_val_from": sum([l["book_val_from"] for l in group["lines"]]),
                "total_accum_dep": sum([l["accum_dep"] for l in group["lines"]]),
                "total_book_val_to": sum([l["book_val_to"] for l in group["lines"]]),
            })
        pprint(groups)
        data = {
            "company_name": comp.name,
            "date_from": date_from,
            "date_to": date_to,
            "groups": groups,
            "total_book_val_from": sum([l["book_val_from"] for l in lines]),
            "total_accum_dep": sum([l["accum_dep"] for l in lines]),
            "total_book_val_to": sum([l["book_val_to"] for l in lines]),
        }
        return data

ReportDepSchedule.register()
