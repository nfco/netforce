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
from netforce import database
from datetime import *
import time
from netforce import access

class StockBalance(Model):
    _inherit= "stock.balance"

    def make_mo(self, ids, context={}):
        count=0
        for obj in self.browse(ids):
            if obj.qty_virt >= obj.min_qty:
                continue
            prod = obj.product_id
            if prod.supply_method!="production":
                raise Exception("Supply method for product %s is not set to 'Production'"%prod.code)
            res = get_model("stock.orderpoint").search([["product_id", "=", prod.id]])
            if res:
                op = get_model("stock.orderpoint").browse(res)[0]
                max_qty = op.max_qty
            else:
                max_qty = 0
            mfg_qty = max_qty - obj.qty_virt
            res=get_model("bom").search([["product_id","=",prod.id]]) # TODO: select bom in separate function
            if not res:
                raise Exception("BoM not found for product '%s'" % prod.name)
            bom_id = res[0]
            bom = get_model("bom").browse(bom_id)
            loc_id = bom.location_id.id
            if not loc_id:
                raise Exception("Missing FG location in BoM %s" % bom.number)
            routing = bom.routing_id
            if not routing:
                raise Exception("Missing routing in BoM %s" % bom.number)
            loc_prod_id = routing.location_id.id
            if not loc_prod_id:
                raise Exception("Missing production location in routing %s" % routing.number)
            uom = prod.uom_id
            if not prod.mfg_lead_time:
                raise Exception("Missing manufacturing lead time for product %s"%prod.code)
            due_date=time.strftime("%Y-%m-%d")
            mfg_date=(datetime.strptime(due_date,"%Y-%m-%d")-timedelta(days=prod.mfg_lead_time)).strftime("%Y-%m-%d")
            order_vals = {
                "product_id": prod.id,
                "qty_planned": mfg_qty,
                "uom_id": uom.id,
                "bom_id": bom_id,
                "routing_id": routing.id,
                "production_location_id": loc_prod_id,
                "location_id": loc_id,
                "order_date": mfg_date,
                "due_date": due_date,
                "state": "waiting_confirm",
            }
            order_id = get_model("production.order").create(order_vals)
            get_model("production.order").create_components([order_id])
            get_model("production.order").create_operations([order_id])
            count+=1
        return {
            "next": {
                "name": "production",
                "tab": "Draft",
            },
            "flash": "%d production orders created" % count,
        }

StockBalance.register()
