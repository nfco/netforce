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
from netforce.access import get_active_user
import datetime


class WorkTime(Model):
    _name = "work.time"
    _string = "Work Time"
    _fields = {
        "resource_id": fields.Many2One("service.resource", "Resource", required=True, search=True, on_delete="cascade"),
        "resource_type": fields.Selection([["person","Person"],["machine","Machine"]],"Resource Type",function="_get_related",function_search="_search_related",function_context={"path":"resource_id.type"},search=True),
        "project_id": fields.Many2One("project", "Project", search=True, required=True),
        "related_id": fields.Reference([["job","Service Order"],["sale.order","Sales Order"],["rental.order","Rental Order"]],"Related To",search=True),
        "job_id": fields.Many2One("job", "Service Order", search=True), # XXX: deprecated
        "service_item_id": fields.Many2One("service.item","Service Item"), # XXX: deprecated
        "service_type_id": fields.Many2One("service.type", "Service Type", function="_get_related", function_context={"path": "job_id.service_type_id"}, function_search="_search_related", search=True),
        "date": fields.Date("Date", required=True, search=True),
        "actual_hours": fields.Decimal("Actual Hours", required=True),
        "bill_hours": fields.Decimal("Billable Hours"),
        "work_type_id": fields.Many2One("work.type", "Work Type"),
        "description": fields.Text("Description"),
        "week": fields.Date("Week", function="get_week", store=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "is_today": fields.Boolean("Today", store=False, function_search="search_today"),
        "is_this_week": fields.Boolean("This Week", store=False, function_search="search_this_week"),
        "is_last_week": fields.Boolean("Last Week", store=False, function_search="search_last_week"),
        "state": fields.Selection([["waiting_approval", "Waiting Approval"], ["approved", "Approved"], ["rejected", "Rejected"]], "Status", required=True),
        "agg_actual_hours_total": fields.Decimal("Actual Hours Total", agg_function=["sum", "actual_hours"]),
        "agg_bill_hours_total": fields.Decimal("Billable Hours Total", agg_function=["sum", "bill_hours"]),
        "track_entries": fields.One2Many("account.track.entry","related_id","Tracking Entries"),
        "track_id": fields.Many2One("account.track.categ","Tracking",function="get_track_categ"),
        "cost_amount": fields.Decimal("Cost Amount",function="get_cost_amount"),
        #"agg_cost_amount": fields.Decimal("Cost Amount", agg_function=["sum", "cost_amount"]),
        "sale_price": fields.Decimal("Hourly Rate"),
    }
    _order = "date,resource_id.name"

    def get_resource(self, context={}):
        user_id = get_active_user()
        res = get_model("service.resource").search([["user_id", "=", user_id]])
        if not res:
            return None
        return res[0]

    _defaults = {
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "resource_id": get_resource,
        "state": "waiting_approval",
    }

    def name_get(self,ids,context={}):
        res=[]
        for obj in self.browse(ids):
            res.append((obj.id,"Work Time %s / %s"%(obj.resource_id.name,obj.date)))
        return res

    def create(self, vals, **kw):
        new_id = super().create(vals, **kw)
        self.function_store([new_id])
        return new_id

    def write(self, ids, vals, **kw):
        super().write(ids, vals, **kw)
        self.function_store(ids)

    def get_week(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            d = datetime.datetime.strptime(obj.date, "%Y-%m-%d")
            d -= datetime.timedelta(d.weekday())
            vals[obj.id] = d.strftime("%Y-%m-%d")
        return vals

    def search_today(self, clause, context={}):
        t = time.strftime("%Y-%m-%d")
        return [["date", "=", t]]

    def search_this_week(self, clause, context={}):
        d = datetime.datetime.today()
        d0 = d - datetime.timedelta(days=d.weekday())
        d1 = d0 + datetime.timedelta(days=6)
        return [["date", ">=", d0.strftime("%Y-%m-%d")], ["date", "<=", d1.strftime("%Y-%m-%d")]]

    def search_last_week(self, clause, context={}):
        d = datetime.datetime.today()
        d0 = d - datetime.timedelta(days=d.weekday() + 7)
        d1 = d0 + datetime.timedelta(days=6)
        return [["date", ">=", d0.strftime("%Y-%m-%d")], ["date", "<=", d1.strftime("%Y-%m-%d")]]

    def approve(self, ids, context={}):
        res=get_model("uom").search([["name","=","Hour"]])
        if not res:
            raise Exception("Hour UoM not found")
        hour_uom_id=res[0]
        for obj in self.browse(ids):
            obj.write({"state": "approved"})
            if obj.track_id and obj.cost_amount:
                vals={
                    "track_id": obj.track_id.id,
                    "date": obj.date,
                    "amount": -obj.cost_amount,
                    "product_id": obj.resource_id.product_id.id,
                    "qty": obj.actual_hours or 0,
                    "uom_id": hour_uom_id,
                    "related_id": "work.time,%s"%obj.id,
                }
                get_model("account.track.entry").create(vals)

    def reject(self, ids, context={}):
        for obj in self.browse(ids):
            obj.write({"state": "rejected"})

    def waiting_approval(self, ids, context={}):
        for obj in self.browse(ids):
            obj.write({"state": "waiting_approval"})
            obj.track_entries.delete()

    def onchange_product(self, context={}):
        data = context["data"]
        prod_id = data["product_id"]
        prod = get_model("product").browse(prod_id)
        data["unit_price"] = prod.cost_price
        return data

    def get_track_categ(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            track_id=None
            project_id=obj.project_id
            if project_id and project_id.track_id:
                track_id=project_id.track_id.id
            rel=obj.related_id
            if rel.track_id:
                track_id=rel.track_id.id
            vals[obj.id]=track_id
        return vals

    def get_cost_amount(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            # Use standard price in product in resource
            prod=obj.resource_id.product_id
            amt=(prod.cost_price or 0)*(obj.actual_hours or 0)
            vals[obj.id]=amt
        return vals

WorkTime.register()
