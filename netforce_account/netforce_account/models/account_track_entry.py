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


class TrackEntry(Model):
    _name = "account.track.entry"
    _string = "Tracking Entries"
    _fields = {
        "track_id": fields.Many2One("account.track.categ", "Tracking Category",required=True,on_delete="cascade",search=True),
        "date": fields.Date("Date",required=True,search=True),
        "amount": fields.Decimal("Amount",required=True),
        "product_id": fields.Many2One("product","Product",search=True),
        "description": fields.Text("Description"),
        "qty": fields.Decimal("Qty"),
        "uom_id": fields.Many2One("uom","UoM"),
        "unit_price": fields.Decimal("Unit Price"),
        "related_id": fields.Reference([["account.invoice","Invoice"],["stock.picking","Stock Picking"],["work.time","Work Time"],["hr.expense","Expense Claim"]],"Related To"),
        "move_id": fields.Many2One("account.move","Journal Entry",search=True),
    }
    _order = "date desc,id desc"
    _defaults={
        "date": lambda *a: time.strftime("%Y-%m-%d"),
    }

    def onchange_product(self,context={}):
        data=context.get("data",{})
        print("#"*80)
        print("ID",data.get("id"))
        prod_id=data["product_id"]
        if not prod_id:
            return
        prod=get_model("product").browse(prod_id)
        price=prod.cost_price
        track_id=data["track_id"]
        track=get_model("account.track.categ").browse(track_id)
        if track.currency_id:
            settings=get_model("settings").browse(1)
            price=get_model("currency").convert(price,settings.currency_id.id,track.currency_id.id)
        data["unit_price"]=-price
        data["qty"]=1
        data["uom_id"]=prod.uom_id.id
        data["amount"]=data["unit_price"]
        return data

    def update_amount(self,context={}):
        data=context.get("data",{})
        unit_price=data.get("unit_price",0)
        qty=data.get("qty",0)
        data["amount"]=unit_price*qty
        return data

TrackEntry.register()
