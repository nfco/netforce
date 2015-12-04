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


class Barcode(Model):
    _name = "stock.barcode"
    _transient = True
    _fields = {
        "station_id": fields.Many2One("barcode.station", "Barcode Station", required=True),
        "type": fields.Selection([["in", "Goods Receipt"], ["internal", "Goods Transfer"], ["out", "Goods Issue"]], "Transaction Type"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"], ["stock.picking", "Picking"]], "Related To"),
        "location_to_id": fields.Many2One("stock.location", "To Location"),
        "location_from_id": fields.Many2One("stock.location", "From Location"),
        "container_from_id": fields.Many2One("stock.container", "From Container"),
        "container_to_id": fields.Many2One("stock.container", "To Container"),
        "lot_id": fields.Many2One("stock.lot", "Lot / Serial Number"),
        "product_id": fields.Many2One("product", "Product"),
        "qty": fields.Decimal("Qty", scale=6),
        "uom_id": fields.Many2One("uom", "UoM"),
        "lines": fields.One2Many("stock.barcode.item", "barcode_id", "Lines"),
        "gross_weight": fields.Decimal("Gross Weight"),
    }

    def onchange_type(self, context={}):
        data = context["data"]
        station_id = data["station_id"]
        station = get_model("barcode.station").browse(station_id)
        type = data["type"]
        if type in ("out", "internal"):
            data["location_from_id"] = station.location_id.id
        elif type == "in":
            data["location_to_id"] = station.location_id.id
        return data

    def onchange_related(self, context={}):
        data = context["data"]
        """ Other module can use
        """
        return data

    def onchange_container_from(self, context={}):
        data = context["data"]
        cont_id = data["container_from_id"]
        data["container_to_id"] = cont_id
        return data

    def onchange_product(self, context={}):
        data = context["data"]
        prod_id = data["product_id"]
        prod = get_model("product").browse(prod_id)
        data["uom_id"] = prod.uom_id.id
        return data

    def add_container_products(self, ids, context={}):
        obj = self.browse(ids)[0]
        cont = obj.container_from_id
        if not cont:
            raise Exception("Missing container")
        contents = cont.get_contents()
        for (prod_id, lot_id, loc_id), (qty, amt, qty2) in contents.items():
            prod = get_model("product").browse(prod_id)
            if loc_id != obj.location_from_id.id:
                loc = get_model("stock.location").browse(loc_id)
                raise Exception("Invalid product location: %s @ %s" % (prod.code, loc.name))
            vals = {
                "barcode_id": obj.id,
                "product_id": prod_id,
                "qty": qty,
                "uom_id": prod.uom_id.id,
                "qty2": qty2,
                "lot_id": lot_id,
            }
            get_model("stock.barcode.item").create(vals)
        return {
            "focus_field": "gross_weight",
        }

    def add_product(self, ids, context={}):
        print("barcode.add_product", ids)
        obj = self.browse(ids)[0]
        vals = {
            "barcode_id": obj.id,
            "product_id": obj.product_id.id,
            "qty": obj.qty,
            "uom_id": obj.uom_id.id,
            "lot_id": obj.lot_id.id,
        }
        get_model("stock.barcode.item").create(vals)
        obj.write({
            "lot_id": None,
            "product_id": None,
            "qty": None,
            "uom_id": None,
        })
        return {
            "focus_field": "product_id",
        }

    def validate(self, ids, context={}):
        obj = self.browse(ids)[0]
        rel = obj.related_id
        if rel and rel._model == "stock.picking":
            vals = {
                "picking_id": rel.id,
                "lines": [],
            }
            for line in obj.lines:
                line_vals = {
                    "product_id": line.product_id.id,
                    "qty": line.qty,
                    "uom_id": line.uom_id.id,
                }
                vals["lines"].append(("create", line_vals))
            val_id = get_model("pick.validate").create(vals)
            res = get_model("pick.validate").do_validate([val_id])
            return {
                "flash": res["flash"],
            }
        else:
            pick_vals = {
                "type": obj.type,
                "lines": [],
                "gross_weight": obj.gross_weight,
            }
            if rel:
                pick_vals["related_id"] = "%s,%d" % (rel._model, rel.id)
            for line in obj.lines:
                line_vals = {
                    "product_id": line.product_id.id,
                    "qty": line.qty,
                    "uom_id": line.uom_id.id,
                    "lot_id": line.lot_id.id,
                    "location_from_id": obj.location_from_id.id,
                    "location_to_id": obj.location_to_id.id,
                    "container_from_id": obj.container_from_id.id,
                    "container_to_id": obj.container_to_id.id,
                }
                pick_vals["lines"].append(("create", line_vals))
            pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": obj.type})
            get_model("stock.picking").set_done([pick_id])
            pick = get_model("stock.picking").browse(pick_id)
            obj.write({
                "type": None,
                "related_id": None,
                "location_from_id": None,
                "location_to_id": None,
                "container_from_id": None,
                "container_to_id": None,
                "product_id": None,
                "qty": None,
                "uom_id": None,
                "lot_id": None,
                "lines": [("delete_all",)],
            })
            return {
                "flash": "Stock picking %s created successfully" % pick.number,
                "focus_field": "type",
            }

Barcode.register()
