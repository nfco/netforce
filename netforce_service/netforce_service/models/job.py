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
from netforce.access import get_active_user, set_active_user
from datetime import *
from dateutil.relativedelta import relativedelta
import time
from netforce.database import get_connection
from netforce.access import get_active_company, check_permission_other
from netforce.utils import get_data_path


class Job(Model):
    _name = "job"
    _string = "Service Order"
    _name_field = "number"
    _audit_log = True
    _multi_company = True
    _fields = {
        "project_id": fields.Many2One("project", "Project", search=True),
        "contact_id": fields.Many2One("contact", "Customer", required=True, search=True),
        "template_id": fields.Many2One("job.template", "Template"),
        "service_type_id": fields.Many2One("service.type", "Service Type", search=True),
        "product_id": fields.Many2One("product", "Product"),  # XXX: deprecated
        "name": fields.Char("Order Name", search=True),
        "number": fields.Char("Order Number", required=True, search=True),
        "description": fields.Text("Description"),
        "due_date": fields.Date("Due Date", search=True),
        "close_date": fields.Date("Close Date", search=True),
        "priority": fields.Selection([["low", "Low"], ["medium", "Medium"], ["high", "High"]], "Priority", search=True),
        "state": fields.Selection([["planned", "Planned"], ["allocated", "Allocated"], ["in_progress", "In Progress"], ["done", "Completed"], ["canceled", "Canceled"]], "Status", required=True),
        "overdue": fields.Boolean("Overdue", function="get_overdue", function_search="search_overdue"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "tasks": fields.One2Many("task", "related_id", "Tasks"),
        "days_late": fields.Integer("Days Late", function="get_days_late"),
        "user_id": fields.Many2One("base.user", "Assigned To"),  # XXX: deprecated
        "resource_id": fields.Many2One("service.resource", "Assigned Resource", search=True),  # XXX: deprecated
        "skill_level_id": fields.Many2One("skill.level", "Required Skill Level", search=True),
        "request_by_id": fields.Many2One("base.user", "Requested By", search=True),
        "user_board_id": fields.Boolean("User", store=False, function_search="search_user_board_id"),
        "sharing": fields.One2Many("share.record", "related_id", "Sharing"),
        "invoice_no": fields.Char("Invoice No."),  # XXX: not used any more...
        "shared_board": fields.Boolean("Shared", store=False, function_search="search_shared_board"),
        "quotation_id": fields.Many2One("sale.quot", "Quotation"),
        "cancel_reason": fields.Text("Cancel Reason"),
        "cancel_periodic": fields.Boolean("Cancel Periodic"),
        "next_job_id": fields.Many2One("job", "Next Order"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "company_id": fields.Many2One("company", "Company"),
        "invoices": fields.One2Many("account.invoice", "related_id", "Invoices"),
        "bill_amount": fields.Decimal("Billable Amount"),
        "invoice_id": fields.Many2One("account.invoice", "Invoice"),
        "is_duplicate": fields.Boolean("Duplicate"),
        "work_time": fields.One2Many("work.time", "job_id", "Work Time"),
        "pickings": fields.One2Many("stock.picking", "related_id", "Pickings"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "parts": fields.One2Many("job.part", "job_id", "Parts"),
        "other_costs": fields.One2Many("job.cost", "job_id", "Other Costs"),
        "items": fields.One2Many("job.item", "job_id", "Service Items"),
        "allocs": fields.One2Many("service.resource.alloc", "job_id", "Resource Allocations"),
        "time_start": fields.DateTime("Planned Start Time"),
        "time_stop": fields.DateTime("Planned Stop Time"),
        "location_id": fields.Many2One("stock.location", "Job Location"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["issue", "Issue"]], "Related To"),
        "lines": fields.One2Many("job.line", "job_id", "Worksheet"),
        "complaints": fields.Text("Complaints"),
        "cause": fields.Text("Cause"),
        "correction": fields.Text("Correction"),
        "amount_total": fields.Decimal("Total Selling", function="get_total", function_multi=True),
        "amount_contract": fields.Decimal("Included In Contract", function="get_total", function_multi=True),
        "amount_job": fields.Decimal("Not Included In Contract", function="get_total", function_multi=True),
        "overdue": fields.Boolean("Overdue", function="get_overdue", function_search="search_overdue"),
        "date_open": fields.DateTime("Actual Start"),
        "date_close": fields.DateTime("Actual Stop"),
        "labor_cost": fields.Decimal("Labor Cost", function="get_cost", function_multi=True),
        "part_cost": fields.Decimal("Parts Cost", function="get_cost", function_multi=True),
        "other_cost": fields.Decimal("Other Cost", function="get_cost", function_multi=True),
        "total_cost": fields.Decimal("Total Cost", function="get_cost", function_multi=True),
        "labor_sell": fields.Decimal("Labor Selling", function="get_sell", function_multi=True),
        "part_sell": fields.Decimal("Parts Selling", function="get_sell", function_multi=True),
        "other_sell": fields.Decimal("Other Selling", function="get_sell", function_multi=True),
        "done_approved_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
        "multi_visit_code_id": fields.Many2One("reason.code", "Multi Visit Reason Code", condition=[["type", "=", "service_multi_visit"]]),
        "late_response_code_id": fields.Many2One("reason.code", "Late Response Reason Code", condition=[["type", "=", "service_late_response"]]),
        "year": fields.Char("Year", sql_function=["year", "due_date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "due_date"]),
        "month": fields.Char("Month", sql_function=["month", "due_date"]),
        "week": fields.Char("Week", sql_function=["week", "due_date"]),
        "activities": fields.One2Many("activity","related_id","Activities"),
        "track_id": fields.Many2One("account.track.categ","Tracking Code"),
        "track_entries": fields.One2Many("account.track.entry",None,"Tracking Entries",function="get_track_entries",function_write="write_track_entries"),
        "track_balance": fields.Decimal("Tracking Balance",function="_get_related",function_context={"path":"track_id.balance"}),
        "agg_total_cost": fields.Decimal("Total Cost", agg_function=["sum", "total_cost"]),
        "agg_total_sell": fields.Decimal("Total Selling", agg_function=["sum", "total_sell"]),
    }
    _order = "number"
    _sql_constraints = [
        ("number_uniq", "unique (number)", "The job number must be unique!"),
    ]

    def _get_number(self, context={}):
        while 1:
            num = get_model("sequence").get_number(type="job")
            if not num:
                return None
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment(type="job")

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = obj.number
            if obj.name:
                name += " - " + obj.name
            vals.append((obj.id, name))
        return vals

    _defaults = {
        "state": "planned",
        "number": _get_number,
        "request_by_id": lambda *a: get_active_user(),
        #"company_id": lambda *a: get_active_company(), # XXX: don't use this yet
        "date_open": lambda *a: time.strftime("%Y-%m-%d"),
    }

    def write(self, ids, vals, **kw):
        if vals.get("state") == "done":
            vals["date_close"] = time.strftime("%Y-%m-%d")
            for obj in self.browse(ids):
                if not obj.done_approved_by_id:
                    raise Exception("Service order has to be approved first")
        super().write(ids, vals, **kw)

    def get_total(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt_total = 0
            amt_contract = 0
            amt_job = 0
            for line in obj.lines:
                amt_total += line.amount
                if line.payment_type == "contract":
                    amt_contract += line.amount
                elif line.payment_type == "job":
                    amt_job += line.amount
            vals[obj.id] = {
                "amount_total": amt_total,
                "amount_contract": amt_contract,
                "amount_job": amt_job,
            }
        return vals

    def onchange_template(self, context={}):
        data = context["data"]
        template_id = data["template_id"]
        tmpl = get_model("job.template").browse(template_id)
        data["service_type_id"] = tmpl.service_type_id.id
        data["description"] = tmpl.description
        data["skill_level_id"] = tmpl.skill_level_id.id
        data["lines"] = []
        for line in tmpl.lines:
            line_vals = {
                "type": line.type,
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
            }
            data["lines"].append(line_vals)
        return data

    def get_overdue(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.due_date:
                vals[obj.id] = obj.due_date < time.strftime(
                    "%Y-%m-%d") and obj.state in ("planned", "allocated", "in_progress")
            else:
                vals[obj.id] = False
        return vals

    def search_overdue(self, clause, context={}):
        return [["due_date", "<", time.strftime("%Y-%m-%d")], ["state", "in", ["planned", "allocated", "in_progress"]]]

    def copy_to_pick_out(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "type": "out",
            "contact_id": obj.contact_id.id,
            "related_id": "job,%d" % obj.id,
            "lines": [],
        }
        res = get_model("stock.location").search([["type", "=", "customer"]])
        if not res:
            raise Exception("Customer location not found")
        cust_loc_id = res[0]
        res = get_model("stock.location").search([["type", "=", "internal"]])
        if not res:
            raise Exception("Warehouse location not found")
        wh_loc_id = res[0]
        for line in obj.lines:
            prod = line.product_id
            if prod.type not in ("stock", "consumable"):
                continue
            prod_loc_id=None
            if prod.locations:
                prod_loc_id=prod.locations[0].location_id
            line_vals = {
                "product_id": prod.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "location_from_id": prod_loc_id and prod_loc_id.id or wh_loc_id,
                "location_to_id": obj.location_id.id or cust_loc_id,
            }
            vals["lines"].append(("create", line_vals))
        if not vals["lines"]:
            raise Exception("Nothing to issue")
        new_id = get_model("stock.picking").create(vals, context={"pick_type": "out"})
        pick = get_model("stock.picking").browse(new_id)
        return {
            "flash": "Goods issue %s copied from service order %s" % (pick.number, obj.number),
            "next": {
                "name": "pick_out",
                "mode": "form",
                "active_id": new_id,
            }
        }

    def copy_to_invoice(self, ids, context={}):
        obj = self.browse(ids)[0]
        inv_vals = {
            "type": "out",
            "inv_type": "invoice",
            "ref": obj.number,
            "related_id": "job,%s" % obj.id,
            "contact_id": obj.contact_id.id,
            "lines": [],
        }
        for line in obj.lines:
            if line.payment_type != "job":
                continue
            prod = line.product_id
            line_vals = {
                "product_id": prod.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "account_id": prod.sale_account_id.id if prod else None,
                "tax_id": prod.sale_tax_id.id if prod else None,
                "amount": line.amount,
            }
            inv_vals["lines"].append(("create", line_vals))
        if not inv_vals["lines"]:
            raise Exception("Nothing to invoice")
        inv_id = get_model("account.invoice").create(inv_vals, {"type": "out", "inv_type": "invoice"})
        inv = get_model("account.invoice").browse(inv_id)
        return {
            "next": {
                "name": "view_invoice",
                "active_id": inv_id,
            },
            "flash": "Invoice %s created from job %s" % (inv.number, obj.number),
        }

    def onchange_product(self, context={}):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line["product_id"]
        prod = get_model("product").browse(prod_id)
        line["uom_id"] = prod.uom_id.id
        line["unit_price"] = prod.sale_price
        line["description"] = prod.description
        return data

    def onchange_due_date(self, context={}):
        print("onchange_due_date")
        data = context["data"]
        data['time_start'] = data['due_date']
        return data

    def onchange_close_date(self, context={}):
        print("onchange_close_date")
        data = context["data"]
        crr_date = time.strftime("%Y-%m-%d")
        close_date = data['close_date']
        due_date = data['due_date']
        if crr_date >= close_date:
            data['state'] = 'done'
        elif crr_date >= due_date and crr_date <= close_date:
            data['state'] = 'in_progress'
        return data

    def get_cost(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            labor_cost = 0
            for time in obj.work_time:
                labor_cost += time.amount or 0
            other_cost = 0
            for line in obj.lines:
                if line.type != "other":
                    continue
                prod = line.product_id
                other_cost += prod.cost_price or 0
            job_loc_id = obj.location_id.id
            if not job_loc_id:
                res = get_model("stock.location").search([["type", "=", "customer"]])
                if res:
                    job_loc_id = res[0]
            part_cost = 0
            for pick in obj.pickings:
                for move in pick.lines:
                    amt = move.qty * (move.unit_price or 0)
                    if move.location_to_id.id == job_loc_id and move.location_from_id.id != job_loc_id:
                        part_cost += amt
                    elif move.location_from_id.id == job_loc_id and move.location_to_id.id != job_loc_id:
                        part_cost -= amt
            vals[obj.id] = {
                "labor_cost": labor_cost,
                "part_cost": part_cost,
                "other_cost": other_cost,
                "total_cost": labor_cost + part_cost + other_cost,
            }
        return vals

    def get_sell(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            labor_sell = 0
            other_sell = 0
            part_sell = 0
            for line in obj.lines:
                if line.type == "labor":
                    labor_sell += line.amount
                elif line.type == "part":
                    part_sell += line.amount
                elif line.type == "other":
                    other_sell += line.amount
            vals[obj.id] = {
                "labor_sell": labor_sell,
                "part_sell": part_sell,
                "other_sell": other_sell,
            }
        return vals

    def approve_done(self, ids, context={}):
        if not check_permission_other("job_approve_done"):
            raise Exception("Permission denied")
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"done_approved_by_id": user_id})
        return {
            "next": {
                "name": "job",
                "mode": "form",
                "active_id": obj.id,
            },
            "flash": "Service order completion approved successfully",
        }

    def get_days_late(self, ids, context={}):
        vals = {}
        d = datetime.now()
        for obj in self.browse(ids):
            if obj.due_date:
                vals[obj.id] = (d - datetime.strptime(obj.due_date, "%Y-%m-%d")).days
            else:
                vals[obj.id] = None
        return vals

    def get_track_entries(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            if not obj.track_id:
                vals[obj.id]=[]
                continue
            res=get_model("account.track.entry").search([["track_id","child_of",obj.track_id.id]])
            vals[obj.id]=res
        return vals

    def write_track_entries(self,ids,field,val,context={}):
        for op in val:
            if op[0]=="create":
                rel_vals=op[1]
                for obj in self.browse(ids):
                    if not obj.track_id:
                        continue
                    rel_vals["track_id"]=obj.track_id.id
                    get_model("account.track.entry").create(rel_vals,context=context)
            elif op[0]=="write":
                rel_ids=op[1]
                rel_vals=op[2]
                get_model("account.track.entry").write(rel_ids,rel_vals,context=context)
            elif op[0]=="delete":
                rel_ids=op[1]
                get_model("account.track.entry").delete(rel_ids,context=context)

    def create_track(self,ids,context={}):
        obj=self.browse(ids[0])
        code=obj.number
        res=get_model("account.track.categ").search([["code","=",code]])
        if res:
            track_id=res[0]
        else:
            parent_id=obj.project_id.track_id.id if obj.project_id else None
            track_id=get_model("account.track.categ").create({
                    "code": code,
                    "name": code,
                    "type": "1",
                    "parent_id": parent_id,
                })
        obj.write({"track_id": track_id})

Job.register()
