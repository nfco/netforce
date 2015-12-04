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
from dateutil.relativedelta import *
from datetime import *


class ReportStockMove(Model):
    _name = "report.stock.move"
    _transient = True
    _fields = {
        "pick_type": fields.Selection([["in", "Goods Receipt"], ["internal", "Goods Transfer"], ["out", "Goods Issue"]], "Type", required=True),
        "date_from": fields.Date("Date From"),
        "date_to": fields.Date("Date To"),
        "location_from_id": fields.Many2One("stock.location", "Location From"),
        "location_to_id": fields.Many2One("stock.location", "Location To"),
        "ref": fields.Char("Ref"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"], ["job", "Service Order"], ["account.invoice", "Invoice"]], "Related To"),
        "show_loss_only": fields.Boolean("Show Loss Qty Only"),
    }

    def default_get(self, field_names=None, context={}, **kw):
        pick_type = context.get("pick_type")
        defaults = context.get("defaults", {})
        date_from = defaults.get("date_from")
        date_to = defaults.get("date_to")
        if pick_type:
            defaults["pick_type"] = pick_type
        if not date_from and not date_to:
            date_from = date.today().strftime("%Y-%m-01")
            date_to = (date.today() + relativedelta(day=31)).strftime("%Y-%m-%d")
            defaults["date_from"] = date_from
            defaults["date_to"] = date_to
        elif not date_from and date_to:
            date_from = get_model("settings").get_fiscal_year_start(date=date_to)
            defaults["date_from"] = date_from
        return defaults

    def get_report_data(self, ids, context={}):
        if ids:
            params = self.read(ids, load_m2o=False)[0]
        else:
            params = self.default_get(load_m2o=False, context=context)
        cond = []
        if params.get("date_from"):
            date_from = params.get("date_from") + " 00:00:00"
            cond.append(["date", ">=", date_from])
        if params.get("date_to"):
            date_to = params.get("date_to") + " 23:59:59"
            cond.append(["date", "<=", date_to])
        if params.get("location_from_id"):
            cond.append(["location_from_id", "=", params.get("location_from_id")])
        if params.get("location_to_id"):
            cond.append(["location_to_id", "=", params.get("location_to_id")])
        if params.get("ref"):
            cond.append(["ref", "ilike", params.get("ref")])
        if params.get("related_id"):
            cond.append(["related_id", "=", params.get("related_id")])
        pick_type = params.get("pick_type")
        cond.append(["picking_id.type", "=", pick_type])
        move_list = get_model("stock.move").search_browse(cond)
        lines = []
        item_no = 0
        loss_loc_id = None
        loss_loc_ids = get_model("stock.location").search([["type", "=", "inventory"]])
        if loss_loc_ids:
            loss_loc_id = loss_loc_ids[0]
        for move in move_list:
            qty_loss = 0
            if loss_loc_id:
                loss_cri = []
                loss_cri.append(["picking_id", "=", move.picking_id.id])
                loss_cri.append(["product_id", "=", move.product_id.id])
                loss_cri.append(["location_from_id", "=", move.location_from_id.id])
                loss_cri.append(["container_from_id", "=", move.container_from_id.id])
                loss_cri.append(["location_to_id", "=", loss_loc_id])
                loss_moves = get_model("stock.move").search_browse(loss_cri)
                for loss_move in loss_moves:
                    qty_loss += loss_move.qty

            if params.get("show_loss_only") and not qty_loss:
                continue
            item_no += 1
            line = self.get_line_data(context={"move": move})
            line["_item_no"] = item_no
            line["qty_loss"] = round(qty_loss, 2)
            lines.append(line)
        title = ""
        if pick_type == "in":
            title = "Goods Receive Report"
        elif pick_type == "out":
            title = "Goods Issue Report"
        elif pick_type == "internal":
            title = "Goods Transfer Report"
        return {
            "title": title,
            "lines": lines
        }

    def get_line_data(self, context={}):
        obj = context["move"]
        state = {
            "draft": "Draft",
            "pending": "Planned",
            "approved": "Approved",
            "done": "Completed",
            "voided": "Voided",
        }
        return {
            "number": obj.picking_id.number,
            "date": obj.date,
            "related": obj.related_id.number,
            "product_code": obj.product_id.code,
            "product_name": obj.product_id.name,
            "location_from": obj.location_from_id.name,
            "qty": obj.qty,
            "uom": obj.uom_id.name,
            "location_to": obj.location_to_id.name,
            "qty2": obj.qty2,
            "container_from": obj.container_from_id.number,
            "container_to": obj.container_to_id.number,
            "lot": obj.lot_id.number,
            "state": state[obj.state],
            "ref": obj.picking_id.ref,
        }

ReportStockMove.register()
