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
from netforce.access import get_active_company, get_active_user
import time


class Borrow(Model):
    _name = "product.borrow"
    _string = "Borrow Request"
    _name_field = "number"
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "date": fields.Date("Date", required=True, search=True),
        "employee_id": fields.Many2One("hr.employee", "Taken By", required=True, search=True),
        "project_id": fields.Many2One("project", "Project", search=True),
        "borrow_for": fields.Char("Borrow For", required=True),
        "due_date": fields.Date("Due Date", required=True, search=True),
        "notes": fields.Text("Notes"),
        "lines": fields.One2Many("product.borrow.line", "request_id", "Lines"),
        "state": fields.Selection([["draft", "Draft"], ["approved", "Approved"], ["done", "Completed"], ["voided", "Voided"]], "Status", required=True),
        "pickings": fields.Many2Many("stock.picking", "Stock Pickings", function="get_pickings"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "is_overdue": fields.Boolean("Overdue", function="get_overdue"),
        "is_return_item": fields.Boolean("Return Item", function="get_return_item"),
    }
    _order = "number"

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence("borrow")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id)

    _defaults = {
        "number": _get_number,
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "state": "draft",
    }

    def approve(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"state": "approved"})

    def set_done(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"state": "done"})

    def void(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"state": "voided"})

    def delete(self, ids, **kw):
        for obj in self.browse(ids):
            if obj.state != "draft":
                raise Exception("Can not delete borrow request number %s in this status" % obj.number)
            if obj.stock_moves:
                raise Exception(
                    "Can not delete borrow request number %s, there are goods issued or goods received in borrow request" % obj.number)
            super().delete(ids, **kw)

    def get_overdue(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = obj.due_date < time.strftime("%Y-%m-%d") and obj.state == "approved"
        return vals

    def get_return_item(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = True
            for line in obj.lines:
                if line.issued_qty - line.returned_qty > 0:
                    vals[obj.id] = False
                    break
        return vals

    def get_pickings(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            pick_ids = []
            for move in obj.stock_moves:
                pick_id = move.picking_id.id
                if pick_id not in pick_ids:
                    pick_ids.append(pick_id)
            vals[obj.id] = pick_ids
        return vals

    def onchange_product(self, context={}):
        data = context["data"]
        lines = data["lines"]
        for line in lines:
            product_id = line.get("product_id")
            if not product_id:
                continue
            product = get_model("product").browse(product_id)
            line["qty"] = 1
            line["uom_id"] = product.uom_id.id
        return data

    def copy_to_picking(self, ids, context={}):
        obj=self.browse(ids[0])
        settings = get_model("settings").browse(1)
        if not settings.product_borrow_journal_id:
            raise Exception("Missing borrow request journal in Inventory Setting")
        if not settings.product_borrow_journal_id.location_from_id:
            raise Exception("Missing 'Location From' for journal '%s'"%settings.product_borrow_journal_id.name)
        if not settings.product_borrow_journal_id.location_to_id:
            raise Exception("Missing 'Location To' for journal '%s'"%settings.product_borrow_journal_id.name)
        user_id=get_active_user()
        user=get_model("base.user").browse(user_id)
        pick_vals = {
            "type": "out",
            "ref": obj.number,
            "journal_id": settings.product_borrow_journal_id.id,
            "related_id": "product.borrow,%s" % obj.id,
            "contact_id": user.contact_id.id,
            "lines": [],
            "state": "draft",
            "company_id": get_active_company(),
        }
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "location_from_id": settings.product_borrow_journal_id.location_from_id.id,
                "location_to_id": settings.product_borrow_journal_id.location_to_id.id,
                "lot_id": line.lot_id.id,
                "related_id": "product.borrow,%s" % obj.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        pick_id = get_model("stock.picking").create(pick_vals, context=pick_vals)
        pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_out",
                "mode": "form",
                "active_id": pick_id,
            },
                "flash": "Picking %s created from borrow request %s" % (pick.number, obj.number),
            "picking_id": pick_id,
        }

    def copy_to_pick_in(self, ids, context={}):
        obj=self.browse(ids)[0]
        settings = get_model("settings").browse(1)
        if not settings.product_borrow_journal_id:
            raise Exception("Missing borrow request journal in Inventory Setting")
        if not settings.product_borrow_journal_id.location_from_id:
            raise Exception("Missing 'Location From' for journal '%s'"%settings.product_borrow_journal_id.name)
        if not settings.product_borrow_journal_id.location_to_id:
            raise Exception("Missing 'Location To' for journal '%s'"%settings.product_borrow_journal_id.name)
        user_id=get_active_user()
        user=get_model("base.user").browse(user_id)
        pick_vals = {
            "type": "in",
            "ref": obj.number,
            "journal_id": settings.product_borrow_journal_id.id,
            "related_id": "product.borrow,%s" % obj.id,
            "contact_id": user.contact_id.id,
            "lines": [],
            "state": "draft",
            "company_id": get_active_company(),
        }
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "location_from_id": settings.product_borrow_journal_id.location_to_id.id,
                "location_to_id": settings.product_borrow_journal_id.location_from_id.id,
                "lot_id": line.lot_id.id,
                "related_id": "product.borrow,%s" % obj.id,
            }
            pick_vals["lines"].append(("create", line_vals))
        pick_id = get_model("stock.picking").create(pick_vals, context=pick_vals)
        pick = get_model("stock.picking").browse(pick_id)
        return {
            "next": {
                "name": "pick_in",
                "mode": "form",
                "active_id": pick_id,
            },
            "flash": "Picking %s created from borrow request %s" % (pick.number, obj.number),
            "picking_id": pick_id,
        }

Borrow.register()
