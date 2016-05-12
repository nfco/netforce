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


class PickValidate(Model):
    _name = "pick.validate"
    _transient = True
    _fields = {
        "picking_id": fields.Many2One("stock.picking", "Picking", required=True, on_delete="cascade"),
        "lines": fields.One2Many("pick.validate.line", "validate_id", "Lines"),
    }

    def _get_picking(self, context={}):
        pick_id = context.get("refer_id")
        if not pick_id:
            return None
        return int(pick_id)

    def _get_lines(self, context={}):
        pick_id = context.get("refer_id")
        if not pick_id:
            return None
        pick_id = int(pick_id)
        pick = get_model("stock.picking").browse(pick_id)
        lines = []
        for line in pick.lines:
            lines.append({
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
            })
        return lines

    _defaults = {
        "picking_id": _get_picking,
        "lines": _get_lines,
    }

    def do_validate(self, ids, context={}):
        st=get_model("settings").browse(1) 
        obj = self.browse(ids)[0]
        pick = obj.picking_id
        remain_lines = []
        for i, line in enumerate(obj.lines):
            move = pick.lines[i]
            ########################################
            # prevent to validate stock if it's not enough
            if st.prevent_validate_neg_stock and pick.type in ('out','internal'):
                key=(move.product_id.id, None, move.location_from_id.id, None)
                keys=[key]
                bals = get_model("stock.balance").compute_key_balances(keys,context={"virt_stock":False})
                bal_qty=bals[key][0]
                if line.qty>bal_qty:
                    prod=move.product_id
                    raise Exception("Stock is not enough :Line %s [%s] %s (%s of %s)"%(i+1,prod.code,prod.name,line.qty,bal_qty))
            ########################################
            remain_qty = move.qty - get_model("uom").convert(line.qty, line.uom_id.id, move.uom_id.id)
            if remain_qty:
                remain_lines.append({
                    "date": move.date,
                    "product_id": move.product_id.id,
                    "location_from_id": move.location_from_id.id,
                    "location_to_id": move.location_to_id.id,
                    "qty": remain_qty,
                    "uom_id": move.uom_id.id,
                    "cost_price": move.cost_price,
                    'cost_price_cur': move.cost_price_cur,
                    "state": move.state,
                })
            if line.qty:
                move.write({"qty": line.qty, "uom_id": line.uom_id.id})
            else:
                move.delete()
        if remain_lines:
            vals = {
                "type": pick.type,
                "contact_id": pick.contact_id.id,
                "journal_id": pick.journal_id.id,
                "date": pick.date,
                "ref": pick.number,
                "lines": [("create", x) for x in remain_lines],
                "state": pick.state,
            }
            if pick.related_id:
                vals["related_id"]="%s,%d"%(pick.related_id._model,pick.related_id.id)
            rpick_id = get_model("stock.picking").create(vals, context={"pick_type": pick.type})
            rpick = get_model("stock.picking").browse(rpick_id)
            message = "Picking %s validated and back order %s created" % (pick.number, rpick.number)
        else:
            message = "Picking %s validated" % pick.number
        pick.set_done()
        if pick.type == "in":
            action = "pick_in"
        elif pick.type == "out":
            action = "pick_out"
        elif pick.type == "internal":
            action = "pick_internal"
        return {
            "next": {
                "name": action,
                "mode": "form",
                "active_id": pick.id,
            },
            "flash": message,
        }

PickValidate.register()
