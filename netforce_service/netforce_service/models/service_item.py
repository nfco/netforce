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
from datetime import *


class ServiceItem(Model):
    _name = "service.item"
    _string = "Service Item"
    _audit_log = True
    _key = ["number"]
    _code_field = "number"
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "name": fields.Char("Name", required=True, search=True),
        "product_id": fields.Many2One("product", "Product", search=True),
        "serial_no": fields.Char("Serial No.", search=True),
        "contact_id": fields.Many2One("contact", "Customer", search=True),
        "project_id": fields.Many2One("project", "Project", search=True),
        "priority": fields.Selection([["low", "Low"], ["medium", "Medium"], ["high", "High"]], "Priority"),
        "location": fields.Char("Location of Service Item"),
        "cost_price": fields.Decimal("Sales Unit Cost"),
        "sale_price": fields.Decimal("Sales Unit Price"),
        "sale_date": fields.Date("Sales Date"),
        "job_items": fields.One2Many("job.item", "service_item_id", "Service Order Items"),
        "jobs": fields.Many2Many("job", "Service Orders", function="get_jobs"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "components": fields.One2Many("service.item", "parent_id", "Components"),
        "description": fields.Text("Description"),
        "parent_id": fields.Many2One("service.item", "Parent"),
        "arrival_date": fields.Date("Arrival Date"),
        "arrival_inspection_date": fields.Date("Arrival Inspection Date"),
        "commission_date": fields.Date("Commissioning Date"),
        "warranty_exp_date": fields.Date("Warranty Exp. Date"),
        "last_service_date": fields.Date("Next Planned Service Date", function="get_last_service_date"),
        "notes": fields.Text("Notes"),
        "last_counter": fields.Integer("Last Counter"),
        "last_counter_date": fields.Date("Last Counter Date"),
        "est_counter_per_year": fields.Integer("Estimated Counter Per Year"),
        "est_counter": fields.Integer("Estimated Current Counter", function="get_est_counter"),
        "job_templates": fields.Many2Many("job.template", "Service Order Templates"),
        "industry_id": fields.Many2One("industry", "Industry", search=True),
        "application_id": fields.Many2One("service.application", "Application", search=True),
        "addresses": fields.One2Many("address", "related_id", "Addresses"),
        "last_job_id": fields.Many2One("job", "Last Job", function="get_last_job"),
        "product_categ_id": fields.Many2One("product.categ", "Product Category", function="_get_related", function_search="_search_related", function_context={"path": "product_id.categ_id"}, search=True),
        "brand_id": fields.Many2One("product.brand", "Product Brand", function="_get_related", function_search="_search_related", function_context={"path": "product_id.brand_id"}, search=True),
        "state": fields.Selection([["active", "Active"], ["stock", "Stock"]], "Status", search=True),
        "year": fields.Char("Year", sql_function=["year", "arrival_date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "arrival_date"]),
        "month": fields.Char("Month", sql_function=["month", "arrival_date"]),
        "week": fields.Char("Week", sql_function=["week", "arrival_date"]),
        "lots": fields.One2Many("stock.lot","service_item_id","Lots / Serial Numbers"),
    }
    _order = "number"

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="service_item")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    _defaults = {
        "number": _get_number,
        "state": "active",
    }

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = "%s [%s] %s" % (obj.name, obj.number, obj.serial_no or "")
            vals.append((obj.id, name))
        return vals

    def name_search(self, name, condition=None, context={}, **kw):
        cond = [["number", "ilike", "%" + name + "%"]]
        if condition:
            cond = [cond, condition]
        ids1 = self.search(cond)
        cond = [["name", "ilike", "%" + name + "%"]]
        if condition:
            cond = [cond, condition]
        ids2 = self.search(cond)
        cond = [["serial_no", "ilike", "%" + name + "%"]]
        if condition:
            cond = [cond, condition]
        ids3 = self.search(cond)
        ids = list(set(ids1 + ids2 + ids3))
        return self.name_get(ids, context=context)

    def get_last_service_date(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.job_items:
                vals[obj.id] = max([line.job_id.due_date or "" for line in obj.job_items])  # XXX
            else:
                vals[obj.id] = None
        return vals

    def get_est_counter(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.last_counter and obj.last_counter_date and obj.est_counter_per_year:
                t1 = datetime.now().date()
                t0 = datetime.strptime(obj.last_counter_date, "%Y-%m-%d").date()
                days = (t1 - t0).days
                print("days", days)
                counter = int(obj.last_counter + (obj.est_counter_per_year / 365.0) * days)
            else:
                counter = None
            vals[obj.id] = counter
        return vals

    def get_jobs(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            jobs = []
            for item in obj.job_items:
                jobs.append(item.job_id.id)
            vals[obj.id] = jobs
        return vals

    def get_last_job(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = obj.job_items[0].job_id.id if obj.job_items else None
        return vals

ServiceItem.register()
