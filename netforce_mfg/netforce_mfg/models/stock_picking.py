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
import time
from netforce import database
from netforce.access import get_active_user, set_active_user
from netforce.access import get_active_company

class StockPicking(Model):
    _inherit= "stock.picking"

    _fields = {

         "related_id": fields.Reference([["sale.order", "Sales Order"],
            ["purchase.order", "Purchase Order"],
            ["production.order", "Production Order"],
            ["project","Project"],
            ["job", "Service Order"],
            ["product.claim", "Claim Bill"],
            ["product.borrow", "Borrow Request"],
            ["stock.picking", "Picking"]], "Related To"),


        }
    def get_update_production_orders(self, ids, context={}):
        prod_ids = []
        for obj in self.browse(ids):
            for line in obj.lines:
                prod_ids.append(line.product_id.id)
        prod_ids = list(set(prod_ids))
        production_ids = []
        for comp in get_model("production.component").\
                search_browse([["product_id", "in", prod_ids]]):
            production_ids.append(comp.order_id.id)
        return list(set(production_ids))


    def set_done(self,ids,context={}):
        user_id=get_active_user()
        for obj in self.browse(ids):
            move_ids=[]
            for line in obj.lines:
                move_ids.append(line.id)
            desc=obj.number
            get_model("stock.move").write(move_ids,vals={"date":obj.date,
                "journal_id":obj.journal_id.id,
                "ref":obj.number},context=context)
            get_model("stock.move").set_done(move_ids,context=context)
            obj.write({"state":"done","done_by_id":user_id},context=context)
            obj.set_currency_rate()
        self.check_order_qtys(ids)
        self.create_bundle_pickings(ids)
        production_ids=self.get_update_production_orders(ids)
        if production_ids:
            get_model("production.order").update_status(production_ids)
        self.trigger(ids,"done")

StockPicking.register()
