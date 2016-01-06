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
from netforce import access
from datetime import *
from dateutil.relativedelta import *

def is_business_day(date_s):
    d=datetime.strptime(date_s,"%Y-%m-%d").date()
    if d.weekday() in (5,6):
        return False
    res=get_model("hr.holiday").search([["date","=",date_s]])
    if res:
        return False
    return True

class StockConsign(Model):
    _name = "stock.consign"
    _string = "Consignment Stock"
    _name_field = "location_id"
    _multi_company = True
    _fields = {
        "location_id": fields.Many2One("stock.location","Stock Location",required=True,search=True),
        "contact_id": fields.Many2One("contact","Contact",required=True,search=True),
        "type": fields.Selection([["sale","Sell"],["purchase","Purchase"]],"Consignment Type",required=True,search=True),
        "company_id": fields.Many2One("company","Company",search=True),
        "periods": fields.One2Many("stock.consign.period","consign_id","Consignment Periods"),
        "order_type": fields.Selection([["stock","From Stock"],["sale","From Sales Orders"],["invoice","From Customer Invoices"]],"Create Order"),
        "new_invoice_lines": fields.Many2Many("account.invoice.line","New Invoice Lines",function="get_new_invoice_lines"),
        "purchase_orders": fields.One2Many("purchase.order","related_id","Purchase Orders"),
    }
    _defaults = {
        "company_id": lambda *a: access.get_active_company(),
        "order_type": "stock",
    }

    def create_purchase(self,ids,context={}):
        for obj in self.browse(ids):
            if obj.type!="purchase":
                raise Exception("Wrong consignment type")
            if obj.order_type in ("stock","sale"): # XXX
                for period in obj.periods:
                    if period.purchase_id:
                        continue
                    period.create_purchase()
            elif obj.order_type=="invoice":
                obj.create_purchase_from_invoice()

    def create_sale(self,ids,context={}):
        for obj in self.browse(ids):
            if obj.type!="sale":
                raise Exception("Wrong consignment type")
            for period in obj.periods:
                if period.sale_id:
                    continue
                period.create_sale()

    def create_periods(self,ids,context={}):
        for obj in self.browse(ids):
            res = get_model("stock.consign.period").search([["consign_id","=",obj.id]], order="date_to desc")
            if res:
                period_id = res[0]
                period=get_model("stock.consign.period").browse(period_id)
                date_from = datetime.strptime(period.date_to,"%Y-%m-%d").date()+timedelta(days=1)
            else:
                date_from = date.today()
            last_d=date.today()+timedelta(days=1)
            while date_from<=last_d:
                next_d=date_from+timedelta(days=1)
                while not is_business_day(next_d.strftime("%Y-%m-%d")):
                    next_d+=timedelta(days=1)
                date_to=next_d-timedelta(days=1)
                date_from_s=date_from.strftime("%Y-%m-%d")
                date_to_s=date_to.strftime("%Y-%m-%d")
                res=get_model("stock.consign.period").search([["consign_id","=",obj.id],["date_from","<=",date_to_s],["date_to",">=",date_from_s]])
                if res:
                    print("overlapping consign period already exists",obj.id,date_from_s,date_to_s)
                    continue
                vals = {
                    "consign_id": obj.id,
                    "date_from": date_from_s,
                    "date_to": date_to_s,
                }
                print("create consign period",obj.id,date_from_s,date_to_s)
                get_model("stock.consign.period").create(vals)
                date_from = date_to + timedelta(days=1)

    def get_new_invoice_lines(self,ids,context={}): 
        vals={}
        for obj in self.browse(ids):
            res=get_model("company").search([["contact_id","=",obj.contact_id.id]])
            if res:
                sup_company_id=res[0]
                inv_line_ids=get_model("account.invoice.line").search([["product_id.company_id","child_of",sup_company_id],["purchase_id","=",None],["invoice_id.state","=","paid"]])
            else:
                inv_line_ids=[]
            vals[obj.id]=inv_line_ids
        return vals

    def create_purchase_from_invoice(self,ids,context={}):
        obj=self.browse(ids[0])
        day_inv_lines={}
        for inv_line in obj.new_invoice_lines:
            inv=inv_line.invoice_id
            day_inv_lines.setdefault(inv.date,[]).append(inv_line.id)
        for d,inv_line_ids in day_inv_lines.items():
            purch_vals={
                "date": d,
                "company_id": obj.company_id.id,
                "contact_id": obj.contact_id.id,
                "tax_type": "tax_ex",
                "lines": [],
                "related_id": "stock.consign,%d"%obj.id,
            }
            prods={}
            for inv_line in get_model("account.invoice.line").browse(inv_line_ids):
                prod=inv_line.product_id
                prods.setdefault(prod.id,{
                    "qty": 0,
                    "amt": 0,
                })
                qty=inv_line.qty or 0
                amt=(prod.purchase_price or 0)*qty
                prods[prod.id]["qty"]+=qty
                prods[prod.id]["amt"]+=amt
            for prod_id,prod_vals in prods.items():
                qty=prod_vals["qty"]
                amt=prod_vals["amt"]
                price=amt/qty if qty else 0
                line_vals={
                    "product_id": prod.id,
                    "description": prod.description or "/",
                    "qty": qty,
                    "uom_id": prod.uom_id.id,
                    "unit_price": price,
                }
                purch_vals["lines"].append(("create",line_vals))
            purch_id=get_model("purchase.order").create(purch_vals)
            get_model("account.invoice.line").write(inv_line_ids,{"purchase_id":purch_id})

StockConsign.register()
