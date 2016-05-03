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
from datetime import *
from dateutil.relativedelta import *
from netforce import access

class StockPeriod(Model):
    _name="stock.period"
    _string="Stock Period"
    _multi_company = True
    _key = ["company_id", "number"]
    _name_field="number"
    _fields={
        "number": fields.Char("Number",required=True,search=True),
        "date_from": fields.Date("Date From",required=True),
        "date_to": fields.Date("Date To",required=True,search=True),
        "state": fields.Selection([["draft","Draft"],["posted","Posted"]],"Status",required=True,readonly=True),
        "move_id": fields.Many2One("account.move","Journal Entry"),
        "comments": fields.One2Many("message","related_id","Comments"),
        "stock_moves": fields.One2Many("stock.move","period_id","Posted Stock Movements"),
        "num_stock_moves": fields.Integer("Number stock movements",function="get_num_stock_moves",function_multi=True),
        "num_posted_stock_moves": fields.Integer("Number posted stock movements",function="get_num_stock_moves",function_multi=True),
        "company_id": fields.Many2One("company", "Company"),
    }
    _order="date_from,id"
    _defaults={
        "state": "draft",
        "date_from": lambda *a: date.today().strftime("%Y-%m-01"),
        "date_to": lambda *a: (date.today()+relativedelta(day=31)).strftime("%Y-%m-%d"),
        "company_id": lambda *a: access.get_active_company(),
    }

    def post(self,ids,context={}):
        obj=self.browse(ids[0])
        accounts={}
        move_ids=get_model("stock.move").search([["date",">=",obj.date_from+" 00:00:00"],["date","<=",obj.date_to+" 23:59:59"],["state","=","done"],["product_id.type","=","stock"]])
        for move in get_model("stock.move").browse(move_ids):
            prod=move.product_id
            if move.location_from_id.type=="customer" and prod.cogs_account_id:
                acc_from_id=prod.cogs_account_id.id
            else:
                acc_from_id=move.location_from_id.account_id.id
                if not acc_from_id:
                    raise Exception("Missing account for location '%s'"%move.location_from_id.name)
            if move.location_to_id.type=="customer" and prod.cogs_account_id:
                acc_to_id=prod.cogs_account_id.id
            else:
                acc_to_id=move.location_to_id.account_id.id
                if not acc_to_id:
                    raise Exception("Missing account for location '%s' product '%s'"%(move.location_to_id.name,prod.code))
            if move.cost_price is None:
                raise Exception("Unknown cost price for stock transaction %s (date=%s, ref=%s, product=%s)"%(move.id,move.date,move.ref,prod.name))
            track_from_id=move.location_from_id.track_id.id
            track_to_id=move.location_to_id.track_id.id
            amt=round(move.qty*move.cost_price,2) # XXX: uom
            accounts.setdefault((acc_from_id,track_from_id),0)
            accounts.setdefault((acc_to_id,track_to_id),0)
            accounts[(acc_from_id,track_from_id)]-=amt
            accounts[(acc_to_id,track_to_id)]+=amt
        get_model("stock.move").write(move_ids,{"period_id":obj.id})
        lines=[]
        desc=obj.number
        for (acc_id,track_id),amt in accounts.items():
            if amt==0:
                continue
            lines.append({
                "description": desc,
                "account_id": acc_id,
                "track_id": track_id,
                "debit": amt>0 and amt or 0,
                "credit": amt<0 and -amt or 0,
            })
        vals={
            "narration": desc,
            "date": obj.date_to,
            "lines": [("create",vals) for vals in lines],
            'related_id': 'stock.period,%s'%obj.id,
        }
        from pprint import pprint
        pprint(vals)
        move_id=get_model("account.move").create(vals)
        get_model("account.move").post([move_id])
        obj.write({"move_id": move_id, "state":"posted"})
        get_model("stock.move").write(move_ids,{"move_id":move_id})

    def to_draft(self,ids,context={}):
        obj=self.browse(ids[0])
        if obj.move_id:
            obj.move_id.void()
            obj.move_id.delete()
        obj.write({"state":"draft"})
        obj.stock_moves.write({"period_id":None})

    def view_journal_entry(self,ids,context={}):
        obj=self.browse(ids)[0]
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": obj.move_id.id,
            }
        }

    def get_num_stock_moves(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            res=get_model("stock.move").read_group(condition=[["date",">=",obj.date_from+" 00:00:00"],["date","<=",obj.date_to+" 23:59:59"]])
            num_stock_moves=res[0]["_count"]
            res=get_model("stock.move").read_group(condition=[["period_id","=",obj.id]])
            num_posted_stock_moves=res[0]["_count"]
            vals[obj.id]={
                "num_stock_moves": num_stock_moves,
                "num_posted_stock_moves": num_posted_stock_moves,
            }
        return vals

StockPeriod.register()
