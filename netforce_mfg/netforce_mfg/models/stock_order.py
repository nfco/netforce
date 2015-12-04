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
from netforce.database import get_connection
from netforce.logger import audit_log
from datetime import *
import time
from dateutil.relativedelta import *
import math

class StockOrder(Model):
    _inherit= "stock.order"

    def auto_create_production_orders(self,context={}):
        access.set_active_user(1)
        access.set_active_company(1) # XXX
        vals={
            "confirm_orders": True,
        }
        obj_id=self.create(vals)
        self.delete_planned_orders([obj_id])
        self.fill_products([obj_id])
        self.create_mo([obj_id])

    def delete_planned_mo(self,context={}):
        d=datetime.today().strftime("%Y-%m-%d")
        n=0
        for order in get_model("production.order").search_browse([["order_date",">=",d]]):
            if order.state in ("in_progress","done"):
                continue
            for pick in order.pickings:
                pick.void()
                pick.delete()
            order.to_draft()
            order.delete()
            n+=1
        return {
            "num_orders": n,
        }

    def get_product_order_qtys(self,context={}):
        print("StockOrder.get_product_order_qtys")
        min_qtys=self.get_min_qtys()
        print("min_qtys",min_qtys)
        qtys_unlim=self.get_plan_qtys_unlim()
        print("qtys_unlim",qtys_unlim)
        if context.get("product_ids"):
            product_ids=context["product_ids"]
        else:
            product_ids=[]
            for prod_id,qty in qtys_unlim.items():
                min_qty=min_qtys.get(prod_id,0)
                if qty<min_qty:
                    product_ids.append(prod_id)
        qtys_horiz=self.get_plan_qtys_horiz(product_ids)
        req_dates=self.get_required_dates(product_ids)
        lines=[]
        product_ids.sort() # TODO: sort by code
        for prod in get_model("product").browse(product_ids):
            plan_days=prod.stock_plan_horizon
            qty_unlim=qtys_unlim.get(prod.id,0)
            if plan_days is not None:
                qty_horiz=qtys_horiz.get(prod.id)
            else:
                qty_horiz=qty_unlim
            min_qty=min_qtys.get(prod.id,0)
            req_qty=min_qty-qty_horiz
            req_date=req_dates.get(prod.id)
            if not req_date:
                continue
            if prod.supply_method=="purchase":
                supply_method="Purchase"
                if prod.purchase_uom_id and prod.purchase_uom_id.id!=prod.uom_id.id:
                    order_uom=prod.purchase_uom_id
                    if not prod.purchase_to_stock_uom_factor:
                        raise Exception("Missing purchase to stock UoM factor for product %s"%prod.code)
                    order_qty=req_qty/prod.purchase_to_stock_uom_factor
                    if prod.purchase_min_qty and order_qty<prod.purchase_min_qty:
                        order_qty=prod.purchase_min_qty
                    if prod.purchase_qty_multiple:
                        n=math.ceil(order_qty/prod.purchase_qty_multiple)
                        order_qty=n*prod.purchase_qty_multiple
                else:
                    order_uom=prod.uom_id
                    order_qty=req_qty
                if not prod.purchase_lead_time:
                    raise Exception("Missing purchase lead time for product %s"%prod.code)
                order_date=(datetime.strptime(req_date,"%Y-%m-%d")-timedelta(days=prod.purchase_lead_time)).strftime("%Y-%m-%d")
            elif prod.supply_method=="production": # <<<
                supply_method="Production"
                order_uom=prod.uom_id
                order_qty=req_qty
                if not prod.mfg_lead_time:
                    raise Exception("Missing manufacturing lead time for product %s"%prod.code)
                order_date=(datetime.strptime(req_date,"%Y-%m-%d")-timedelta(days=prod.mfg_lead_time)).strftime("%Y-%m-%d")
            else:
                raise Exception("Invalid supply method")
            line_vals={
                "product_id": prod.id,
                "qty": order_qty,
                "uom_id": order_uom.id,
                "date": order_date,
                "supply_method": prod.supply_method,
                "supplier_id": prod.suppliers[0].supplier_id.id if prod.suppliers else None,
            }
            lines.append(line_vals)
        print("lines",lines)
        return lines

    def create_orders(self,ids,context={}):
        print("create_orders",ids)
        obj=self.browse(ids[0])
        res=obj.create_po()
        num_po=res["num_orders"]
        res=obj.create_mo()
        num_mo=res["num_orders"]
        msg="Stock ordering: %d purchase orders and %s production orders created"%(num_po,num_mo)
        audit_log(msg)
        return {
            "flash": msg,
        }

    def create_mo(self,ids,context={}):
        obj=self.browse(ids[0])
        n=0
        for line in obj.lines:
            if line.supply_method!="production":
                continue
            prod = line.product_id
            res=get_model("bom").search([["product_id","=",prod.id]])
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
            order_date=line.date
            if not prod.mfg_lead_time:
                raise Exception("Missing manufacturing lead time in product %s"%prod.code)
            due_date=(datetime.strptime(order_date,"%Y-%m-%d")+timedelta(days=prod.mfg_lead_time)).strftime("%Y-%m-%d")
            order_vals = {
                "product_id": prod.id,
                "qty_planned": line.qty,
                "uom_id": line.uom_id.id,
                "bom_id": bom_id,
                "routing_id": routing.id,
                "production_location_id": loc_prod_id,
                "location_id": loc_id,
                "order_date": order_date,
                "due_date": due_date,
                "state": "waiting_confirm",
            }
            order_id = get_model("production.order").create(order_vals)
            get_model("production.order").create_components([order_id])
            get_model("production.order").create_operations([order_id])
            if obj.confirm_orders:
                get_model("production.order").confirm([order_id])
            n+=1
        return {
            "num_orders": n,
        }

    def delete_planned_orders(self,ids,context={}):
        res=self.delete_planned_po()
        num_po=res["num_orders"]
        self.delete_planned_mo()
        num_mo=res["num_orders"]
        return {
            "flash": "%d purchase orders and %s production orders deleted"%(num_po,num_mo),
        }

StockOrder.register()
