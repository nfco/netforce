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


class BarcodeValidate(Model):
    _name = "barcode.validate"
    _transient = True
    _fields = {
        "picking_id": fields.Many2One("stock.picking", "Picking", condition=[["state", "=", "pending"]]),
        #"location_from_id": fields.Many2One("stock.location","From Location",condition=[["type","=","internal"]]),
        #"location_to_id": fields.Many2One("stock.location","To Location",condition=[["type","=","internal"]]),
        "mode": fields.Selection([["backorder", "Backorder"], ["loss", "Inventory Loss"]], "Mode"),
        "location_loss_id": fields.Many2One("stock.location", "Inventory Loss Location", condition=[["type", "=", "inventory"]]),
        "lines": fields.One2Many("barcode.validate.line", "wizard_id", "Lines"),
    }

    _defaults = {
        "state": "done",
    }

    def fill_products(self, ids, context={}):
        obj = self.browse(ids)[0]
        pick = obj.picking_id
        found = False
        for line in obj.lines:
            if line.wizard_id.id == obj.id:
                return
        for line in pick.lines:
            vals = {
                "wizard_id": obj.id,
                "product_id": line.product_id.id,
                "qty_planned": line.qty,
                "uom_id": line.uom_id.id,
                "lot_id": line.lot_id.id,
                "container_to_id": line.container_to_id.id,
                "location_from_id": line.location_from_id.id,
                "location_to_id": line.location_to_id.id,
                "related_id": "%s,%d" % (line.related_id._model, line.related_id.id) if line.related_id else None
            }
            get_model("barcode.validate.line").create(vals)
            found = True
        if not found:
            raise Exception("No products remaining")

    def clear(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "picking_id": None,
            #"location_from_id": None,
            #"location_to_id": None,
            "lines": [("delete_all",)],
        }
        obj.write(vals)

    def validate(self, ids, context={}):
        obj = self.browse(ids)[0]
        if not obj.lines:
            raise Exception("Product list is empty")
        pick = obj.picking_id
        if obj.mode == "backorder":
            vals = {
                "picking_id": pick.id,
                "lines": [],
            }
            for line in obj.lines:
                if not line.qty_actual:
                    raise Exception("Missing actual qty for product %s" % line.product_id.code)
                line_vals = {
                    "product_id": line.product_id.id,
                    "qty": line.qty_actual,
                    "uom_id": line.uom_id.id,
                }
                vals["lines"].append(("create", line_vals))
            val_id = get_model("pick.validate").create(vals)
            res = get_model("pick.validate").do_validate([val_id])
            obj.clear()
            return {
                "flash": res["flash"],
            }
        elif obj.mode == "loss":
            if not obj.location_loss_id:
                raise Exception("Missing inventory loss location")

            pick.set_done(context=context)  # XXX
            obj.clear()
            return {
                "flash": "Picking validated successfully",
                "focus_field": "picking_id",
            }

BarcodeValidate.register()
