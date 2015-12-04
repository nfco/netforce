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
    _inherit= "barcode.validate"

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
            production_ids = []
            for line in obj.lines:
                if not line.qty_actual:
                    raise Exception("Missing actual qty for product %s" % line.product_id.code)
                qty_loss = line.qty_planned - line.qty_actual
                if line.product_id.max_qty_loss != None and abs(qty_loss) > line.product_id.max_qty_loss and not pick.done_approved_by_id:
                    raise Exception("Qty loss is too high, need approval")
                stock_move = None
                for pick_line in pick.lines:  # XXX: for MTS, want loss to come from location_from...
                    if pick_line.product_id.id != line.product_id.id \
                        or (pick_line.related_id and line.related_id
                            and (pick_line.related_id._model != line.related_id._model
                                 or pick_line.related_id.id != line.related_id.id)):
                        continue
                    if pick_line.qty != line.qty_planned:
                        continue
                    stock_move = pick_line
                    break
                if not stock_move:
                    raise Exception("Failed to update picking")
                stock_move.write(vals={"qty": line.qty_actual}, context=context)
                production_ids += get_model("stock.move").get_production_orders([stock_move.id])
                if qty_loss > 0:
                    vals = {
                        "product_id": line.product_id.id,
                        "qty": qty_loss,
                        "uom_id": line.uom_id.id,
                        "location_from_id": line.location_from_id.id,
                        "location_to_id": obj.location_loss_id.id,
                        "picking_id": pick.id,
                        "lot_id": line.lot_id.id,
                        "container_from_id": stock_move.container_from_id.id,  # XXX
                        "related_id": "%s,%d" % (line.related_id._model, line.related_id.id) if line.related_id else None
                    }
                    move_id = get_model("stock.move").create(vals=vals, context=context)
                    production_ids += get_model("stock.move").get_production_orders([move_id])
                elif round(qty_loss, 2) < 0:
                    vals = {
                        "product_id": line.product_id.id,
                        "qty": -qty_loss,
                        "uom_id": line.uom_id.id,
                        "location_from_id": obj.location_loss_id.id,
                        "location_to_id": line.location_from_id.id,
                        "lot_id": line.lot_id.id,
                        "container_from_id": stock_move.container_from_id.id,  # XXX
                        "container_to_id": stock_move.container_from_id.id,
                        "picking_id": pick.id,
                        "related_id": "%s,%d" % (line.related_id._model, line.related_id.id) if line.related_id else None
                    }
                    move_id = get_model("stock.move").create(vals=vals, context=context)
                    production_ids += get_model("stock.move").get_production_orders([move_id])
            get_model("production.order").update_status(list(set(production_ids)))
            pick.set_done(context=context)  # XXX
            obj.clear()
            return {
                "flash": "Picking validated successfully",
                "focus_field": "picking_id",
            }

BarcodeValidate.register()

