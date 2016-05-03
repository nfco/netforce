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
from netforce.utils import get_data_path

class BarcodeIssue(Model):
    _name = "barcode.issue"
    _transient = True
    _fields = {
        "location_from_id": fields.Many2One("stock.location", "From Location", condition=[["type", "=", "internal"]]),
        "location_to_id": fields.Many2One("stock.location", "To Location", condition=[["type", "!=", "internal"]]),
        "journal_id": fields.Many2One("stock.journal", "Stock Journal"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"]], "Related To"),
        "lines": fields.One2Many("barcode.issue.line", "wizard_id", "Lines"),
        "state": fields.Selection([["pending", "Pending"], ["done", "Completed"]], "Status", required=True),
        "container_from_id": fields.Many2One("stock.container", "From Container"),
    }

    _defaults = {
        "state": "done",
    }

    def onchange_product(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["uom_id"] = prod.uom_id.id
        return data

    def onchange_related(self, context={}):
        data = context["data"]
        val = data["related_id"][0]
        relation, rel_id = val.split(",")
        rel_id = int(rel_id)
        if relation == "sale.order":
            res = get_model("stock.location").search([["type", "=", "customer"]])
            if not res:
                raise Exception("Customer location not found")
            data["location_to_id"] = res[0]
        elif relation == "purchase.order":
            res = get_model("stock.location").search([["type", "=", "supplier"]])
            if not res:
                raise Exception("Supplier location not found")
            data["location_to_id"] = res[0]
        return data

    def fill_products(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.container_from_id:
            contents = obj.container_from_id.get_contents()
            for (prod_id, lot_id, loc_id), (qty, amt, qty2) in contents.items():
                if loc_id != obj.location_from_id.id:
                    continue
                prod = get_model("product").browse(prod_id)
                vals = {
                    "wizard_id": obj.id,
                    "product_id": prod_id,
                    "lot_id": lot_id,
                    "qty": qty,
                    "uom_id": prod.uom_id.id,
                    "qty2": qty2,
                    "container_from_id": obj.container_from_id.id,
                }
                get_model("barcode.issue.line").create(vals)
            obj.write({"container_from_id": None})
        else:
            rel = obj.related_id
            if rel._model == "sale.order":
                for line in rel.lines:
                    qty_remain = line.qty - line.qty_delivered
                    if qty_remain <= 0:
                        continue
                    vals = {
                        "wizard_id": obj.id,
                        "product_id": line.product_id.id,
                        "qty": qty_remain,
                        "uom_id": line.uom_id.id,
                    }
                    get_model("barcode.issue.line").create(vals)
            elif rel._model == "purchase.order":
                for line in rel.lines:
                    if line.qty_received <= 0:
                        continue
                    vals = {
                        "wizard_id": obj.id,
                        "product_id": line.product_id.id,
                        "qty": line.qty_received,
                        "uom_id": line.uom_id.id,
                    }
                    get_model("barcode.issue.line").create(vals)

    def clear(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "location_to_id": None,
            "related_id": None,
            "lines": [("delete_all",)],
        }
        obj.write(vals)

    def validate(self, ids, context={}):
        obj = self.browse(ids)[0]
        if not obj.lines:
            raise Exception("Product list is empty")
        pick_vals = {
            "type": "out",
            "journal_id": obj.journal_id.id,
            "lines": [],
        }
        rel = obj.related_id
        if rel:
            pick_vals["related_id"] = "%s,%d" % (rel._model, rel.id)
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "lot_id": line.lot_id.id,
                "qty2": line.qty2,
                "location_from_id": obj.location_from_id.id,
                "location_to_id": obj.location_to_id.id,
                "container_from_id": line.container_from_id.id,
                "container_to_id": line.container_to_id.id,
                "related_id": "%s,%s" % (line.related_id._model, line.related_id.id),
                "notes": line.notes,
            }
            pick_vals["lines"].append(("create", line_vals))
        pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": "out"})
        if obj.state == "done":
            get_model("stock.picking").set_done([pick_id])
        elif obj.state == "pending":
            get_model("stock.picking").pending([pick_id])
        pick = get_model("stock.picking").browse(pick_id)
        obj.clear()
        return {
            "next": {
                "name": "pick_out",
                "mode": "page",
                "active_id": pick.id,
            },
            "flash": "Goods issue %s created successfully" % pick.number,
            "focus_field": "related_id",
        }

BarcodeIssue.register()
