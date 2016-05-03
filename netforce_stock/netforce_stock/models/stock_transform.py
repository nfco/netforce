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
import time


class Transform(Model):
    _name = "stock.transform"
    _string = "Transform"
    _name_field = "number"
    _fields = {
        "date": fields.Date("Date", required=True, search=True),
        "number": fields.Char("Number", required=True, search=True),
        "location_id": fields.Many2One("stock.location", "Location", condition=[["type", "=", "internal"]], search=True, required=True),
        "container_id": fields.Many2One("stock.container", "Container"),
        "state": fields.Selection([["draft", "Draft"], ["done", "Completed"], ["voided", "Voided"]], "Status", required=True),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"],["job", "Service Order"], ["product.claim", "Claim Bill"], ["product.borrow", "Borrow Request"], ["stock.picking", "Picking"]], "Related To"),
        "stock_moves": fields.One2Many("stock.move", "related_id", "Stock Movements"),
        "source_lines": fields.One2Many("stock.transform.source", "transform_id", "Source Lines"),
        "target_lines": fields.One2Many("stock.transform.target", "transform_id", "Target Lines"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "journal_id": fields.Many2One("stock.journal", "Journal"),
    }
    _order = "date,id"

    def _get_number(self, context={}):
        seq_id = None
        seq_id = get_model("sequence").find_sequence("stock_transform")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id,context)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id,context)

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
    }

    def validate(self, ids, context={}):
        obj = self.browse(ids)[0]
        settings = get_model("settings").browse(1)
        res = get_model("stock.location").search([["type", "=", "transform"]])
        if not res:
            raise Exception("Missing transform location")
        trans_loc_id = res[0]
        move_ids = []

        for source in obj.source_lines:
            vals = {
                "journal_id": obj.journal_id.id or settings.transform_journal_id.id,
                "location_from_id": obj.location_id.id,
                "location_to_id": trans_loc_id,
                "container_from_id": source.container_id.id,
                "product_id": source.product_id.id,
                "qty": source.qty,
                "qty2": source.qty2,
                "uom_id": source.uom_id.id,
                "lot_id": source.lot_id.id if source.lot_id else None,
                "related_id": "stock.transform,%d" % obj.id,
            }
            move_id = get_model("stock.move").create(vals)
            move_ids.append(move_id)
        for target in obj.target_lines:
            vals = {
                "journal_id": obj.journal_id.id or settings.transform_journal_id.id,
                "location_from_id": trans_loc_id,
                "location_to_id": obj.location_id.id,
                "container_to_id": target.container_id.id,
                "product_id": target.product_id.id,
                "qty": target.qty,
                "qty2": target.qty2,
                "uom_id": target.uom_id.id,
                "lot_id": target.lot_id.id if target.lot_id else None,
                "related_id": "stock.transform,%d" % obj.id,
            }
            move_id = get_model("stock.move").create(vals)
            move_ids.append(move_id)
        get_model("stock.move").set_done(move_ids)
        obj.write({"state": "done"})

    def void(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.void_acc_move()
        obj.stock_moves.delete()
        obj.write({"state": "voided"})

    def void_acc_move(self,ids,context={}):
        print("void_acc_move ...")
        for id in ids:
            for acc_move in get_model("account.move").search_browse([['related_id','=','stock.transform,%s'%id]]):
                acc_move.void()
        print("done!")

    def set_draft_acc_move(self,ids,context={}):
        print("set_draft_acc_move ...")
        for id in ids:
            for acc_move in get_model("account.move").search_browse([['related_id','=','stock.transform,%s'%id]]):
                acc_move.to_draft()
        print("done!")

    def to_draft(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.set_draft_acc_move()
        obj.stock_moves.delete()
        obj.write({"state": "draft"})

    def onchange_from_product(self, context={}):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        prod = get_model("product").browse(prod_id)
        line["uom_id"] = prod.uom_id.id
        line["qty"] = 1
        return data

    def onchange_to_product(self, context={}):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        prod = get_model("product").browse(prod_id)
        line["uom_id"] = prod.uom_id.id
        line["qty"] = 1
        return data

    def onchange_container(self, context={}):
        data = context["data"]
        cont_id = data.get("container_id")
        location_id = data.get("location_id")
        if not cont_id or not location_id:
            return
        cont = get_model("stock.container").browse(cont_id)
        contents = cont.get_contents()
        lines = []
        for (prod_id, lot_id, loc_id), (qty, amt, qty2) in contents.items():
            if loc_id != location_id:
                continue
            prod = get_model("product").browse(prod_id)
            line_vals = {
                "product_id": prod_id,
                "lot_id": lot_id,
                "qty": qty,
                "uom_id": prod.uom_id.id,
                "qty2": qty2,
                "container_id": cont_id,
            }
            lines.append(line_vals)
        data["source_lines"] = lines
        return data

    def onchange_date(self, context={}):
        data = context["data"]
        context['date']=data['date']
        num=self._get_number(context=context)
        data["number"] = num
        return data

Transform.register()
