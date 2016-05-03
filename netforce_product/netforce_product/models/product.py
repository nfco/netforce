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
from netforce.database import get_active_db
from netforce import utils
import os.path
from PIL import Image, ImageChops
from netforce import access
from decimal import Decimal
import time
import math

class Product(Model):
    _name = "product"
    _string = "Product"
    _audit_log = True
    _key = ["code","state","company_id"]
    _order = "code,name"
    _export_field = "code"
    _history = True
    _fields = {
        "name": fields.Char("Name", required=True, search=True, translate=True, size=256),
        "code": fields.Char("Code", required=True, search=True),
        "type": fields.Selection([["stock", "Stockable"], ["consumable", "Consumable"], ["service", "Service"], ["master", "Master"], ["bundle", "Bundle"]], "Product Type", required=True, search=True),
        "uom_id": fields.Many2One("uom", "Default UoM", required=True),
        "parent_id": fields.Many2One("product", "Master Product"),
        "categ_id": fields.Many2One("product.categ", "Product Category", search=True),
        "description": fields.Text("Description", translate=True),
        "purchase_price": fields.Decimal("Purchase Price", scale=6),
        "sale_price": fields.Decimal("List Price (Sales Invoice UoM)", scale=6),
        "sale_price_order_uom": fields.Decimal("List Price (Sales Order UoM)", scale=6, function="get_sale_price_order_uom"),
        "tags": fields.Many2Many("tag", "Tags"),
        "image": fields.File("Image"),
        "cost_method": fields.Selection([["standard", "Standard Cost"], ["average", "Weighted Average"], ["fifo", "FIFO"], ["lifo", "LIFO"]], "Costing Method"),
        "cost_price": fields.Decimal("Cost Price", scale=6),
        "stock_in_account_id": fields.Many2One("account.account", "Stock Input Account", multi_company=True), # XXX: deprecated
        "stock_out_account_id": fields.Many2One("account.account", "Stock Output Account", multi_company=True), # XXX: deprecated
        "cogs_account_id": fields.Many2One("account.account", "Cost Of Goods Sold Account", multi_company=True),
        "purchase_account_id": fields.Many2One("account.account", "Purchase Account", multi_company=True),
        "purchase_tax_id": fields.Many2One("account.tax.rate", "Purchase Tax"),
        "supplier_id": fields.Many2One("contact", "Default Supplier"),  # XXX: deprecated
        "sale_account_id": fields.Many2One("account.account", "Sales Account", multi_company=True),
        "sale_return_account_id": fields.Many2One("account.account", "Sales Returns Account", multi_company=True),
        "sale_promotion_account_id": fields.Many2One("account.account","Sales Promotion Account",multi_company=True),
        "sale_tax_id": fields.Many2One("account.tax.rate", "Sales Tax"),
        "sale_promotion_tax_id": fields.Many2One("account.tax.rate", "Promotion Tax"),
        "location_id": fields.Many2One("stock.location", "Warehouse"), # XXX: deprecated
        "bin_location": fields.Char("Bin Location"),
        "update_balance": fields.Boolean("Update Balance"),
        "active": fields.Boolean("Active"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "categs": fields.Many2Many("product.categ", "Other Categories"),  # XXX: deprecated
        "attributes": fields.One2Many("product.attribute.value", "product_id", "Attributes"),
        "variants": fields.One2Many("product", "parent_id", "Variants"),
        #"variant_values": fields.One2Many("product.custom.option.variant.value","product_id","Variant Values"),
        "custom_options": fields.Many2Many("product.custom.option", "Custom Options"),
        "images": fields.One2Many("product.image", "product_id", "Images"),
        "store_type_id": fields.Many2One("store.type", "Storage Type"),
        "brand_id": fields.Many2One("product.brand", "Brand", search=True),
        "related_products": fields.Many2Many("product", "Related Products", relfield="product1_id", relfield_other="product2_id"),
        "min_sale_qty": fields.Decimal("Min Sale Qty"),
        "sale_unit_qty": fields.Decimal("Sale Unit Qty"),
        "shelf_life": fields.Decimal("Shelf Life (Days)"),
        "weight": fields.Decimal("Weight (Kg)"),
        "volume": fields.Decimal("Volume (M^3)"),
        "width": fields.Decimal("Width"),
        "height": fields.Decimal("Height"),
        "length": fields.Decimal("Length"),
        "packing_size": fields.Char("Packing Size"),
        "details": fields.Text("Product Details", translate=True),
        "details2": fields.Text("Product Details (2)", translate=True),
        "details2_label": fields.Char("Product Details Label (2)"),
        "details3": fields.Text("Product Details (3)", translate=True),
        "details3_label": fields.Char("Product Details Label (3)"),
        "other_url": fields.Char("Product URL",size=256),
        "purchase_currency_id": fields.Many2One("currency", "Purchase Currency"),
        "purchase_currency_rate": fields.Decimal("Purchase Currency Rate", scale=6),
        "purchase_duty_percent": fields.Decimal("Import Duty (%)"),
        "purchase_ship_percent": fields.Decimal("Shipping Charge (%)"),
        "landed_cost": fields.Decimal("Landed Cost", function="get_landed_cost",function_multi=True),
        "landed_cost_conv": fields.Decimal("Landed Cost (Conv)", function="get_landed_cost",function_multi=True),
        "gross_profit": fields.Decimal("Gross Profit (%)"),
        "auto_list_price": fields.Decimal("Auto List Price", function="get_auto_list_price"),
        "max_discount": fields.Decimal("Max Discount (%)", function="get_max_discount"),
        "price_index": fields.Decimal("Price Index", function="get_price_index"),
        "price_notes": fields.Text("Notes"),
        "price_date": fields.Date("Price Date"),
        "pricelist_items": fields.One2Many("price.list.item", "product_id", "Pricelist Items"),
        "procure_method": fields.Selection([["mto", "Make To Order"], ["mts", "Make To Stock"]], "Procurement Method"),
        "supply_method": fields.Selection([["purchase", "Purchase"], ["production", "Production"]], "Supply Method"),
        "can_sell": fields.Boolean("Can Sell"),
        "can_purchase": fields.Boolean("Can Purchase"),
        "id": fields.Integer("Database ID", readonly=True),  # MTS
        "create_time": fields.DateTime("Create Time", readonly=True),  # MTS
        "supplier_product_code": fields.Char("Supplier Product Code"),  # XXX: deprecated
        "require_qty2": fields.Boolean("Require Secondary Qty"),
        "qty2_factor": fields.Decimal("UoM -> Secondary Qty Factor", scale=6),
        "replacements": fields.Many2Many("product", "Replacement Products", reltable="m2m_product_replacement", relfield="product1_id", relfield_other="product2_id"),
        "suppliers": fields.One2Many("product.supplier", "product_id", "Suppliers"),
        "max_qty_loss": fields.Decimal("Max Qty Loss"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "ship_methods": fields.Many2Many("ship.method", "Shipping Methods"),
        "ecom_discount_percent": fields.Decimal("Ecom. Discount Percent"), # XXX: deprecated
        "ecom_special_price": fields.Decimal("Ecom. Special Price"), # XXX: deprecated
        #"ecom_sale_price": fields.Decimal("Ecom. Sale Price", function="get_ecom_sale_price", function_multi=True), # XXX: deprecated
        #"ecom_has_discount": fields.Decimal("Ecom. Has Discount", function="get_ecom_sale_price", function_multi=True), # XXX: deprecated
        "variant_attributes": fields.Json("Variant Attributes", function="get_variant_attributes"),
        "company_id": fields.Many2One("company", "Company"),
        "sale_channels": fields.Many2Many("sale.channel", "Sales Channels"),
        "customer_price": fields.Decimal("Customer Price",function="get_customer_price",function_multi=True),
        "customer_has_discount": fields.Decimal("Customer Has Discount",function="get_customer_price",function_multi=True),
        "customer_discount_text": fields.Decimal("Customer Discount Text",function="get_customer_price",function_multi=True),
        "customer_discount_percent": fields.Decimal("Customer Discount Percent",function="get_customer_price",function_multi=True),
        "sale_company_id": fields.Many2One("company","Sold By"),
        "groups": fields.Many2Many("product.group","Groups"),
        "payment_methods": fields.Many2Many("payment.method","Payment Methods"),
        "locations": fields.One2Many("product.location","product_id","Warehouses"),
        "stock_qty": fields.Decimal("Total Stock Qty",function="get_stock_qty"),
        "state": fields.Selection([["draft","Draft"],["approved","Approved"]],"Status"),
        "sale_uom_id": fields.Many2One("uom", "Sales Order UoM"),
        "sale_invoice_uom_id": fields.Many2One("uom","Sales Invoice UoM"),
        "sale_to_stock_uom_factor": fields.Decimal("Sales Order -> Stock Uom Conversion Factor", scale=6),
        "sale_to_invoice_uom_factor": fields.Decimal("Sales Order -> Sales Invoice Uom Conversion Factor", scale=6),
        "purchase_uom_id": fields.Many2One("uom", "Purchase Order UoM"),
        "purchase_invoice_uom_id": fields.Many2One("uom","Purchase Invoice UoM"),
        "purchase_to_stock_uom_factor": fields.Decimal("Purchase Order -> Stock Uom Conversion Factor", scale=6),
        "purchase_to_invoice_uom_factor": fields.Decimal("Purchase Order -> Purchase Invoice Uom Conversion Factor", scale=6),
        "purchase_lead_time": fields.Integer("Purchasing Lead Time (Days)"),
        "purchase_min_qty": fields.Decimal("Purchase Minimum Qty"),
        "purchase_qty_multiple": fields.Decimal("Purchase Qty Multiple"),
        "mfg_lead_time": fields.Integer("Manufacturing Lead Time (Days)"),
        "mfg_min_qty": fields.Decimal("Manufacturing Minimum Qty"),
        "mfg_qty_multiple": fields.Decimal("Manufacturing Qty Multiple"),
        #"purchase_price_uom_id": fields.Many2One("uom", "Purchase Price UoM"), # not needed?
        #"sale_price_uom_id": fields.Many2One("uom", "List Price UoM"), # not needed?
        "events": fields.Many2Many("sale.event","Events"),
        "is_published": fields.Boolean("Publish Product"),
        "require_lot": fields.Boolean("Require Lot"),
        "lot_select": fields.Selection([["fifo","FIFO"],["fefo","FEFO"]],"Lot Selection"),
        "components": fields.One2Many("product.component","product_id","Bundle Components"),
        "approve_date": fields.DateTime("Approve Date"),
        "service_items": fields.One2Many("service.item","product_id","Service Items"),
        "lots": fields.One2Many("stock.lot","product_id","Lots"),
        "stock_plan_horizon": fields.Integer("Inventory Planning Horizon (days)"),
        "ecom_hide_qty": fields.Boolean("Hide Stock Qty From Website"),
        "ecom_hide_unavail": fields.Boolean("Hide From Website When Out Of Stock"),
        "ecom_no_order_unavail": fields.Boolean("Prevent Orders When Out Of Stock"),
        "ecom_select_lot": fields.Boolean("Customers Select Lot When Ordering"),
        "ecom_lot_before_invoice": fields.Boolean("Require Lot Before Invoicing"),
        "product_origin": fields.Char("Product Origin"),
        "stock_balances": fields.One2Many("stock.balance","product_id","Stock Balances"),
    }

    _defaults = {
        "update_balance": True,
        "active": True,
        "can_sell": False,
        "can_purchase": False,
        "company_id": lambda *a: access.get_active_company(),
        "state": "draft",
    }

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            if obj.code:
                name = "[%s] %s" % (obj.code, obj.name)
            else:
                name = obj.name
            vals.append((obj.id, name, obj.image))
        return vals

    def name_search(self, name, condition=None, context={}, limit=None, **kw):
        search_mode = context.get("search_mode")
        print("##############################")
        print("search_mode", search_mode)
        if search_mode == "suffix":
            cond = [["code", "=ilike", "%" + name]]
        elif search_mode == "prefix":
            cond = [["code", "=ilike", name + "%"]]
        else:
            cond = [["code", "ilike", name]]
        if condition:
            cond = [cond, condition]
        ids1 = self.search(cond, limit=limit)
        if search_mode == "suffix":
            cond = [["name", "=ilike", "%" + name]]
        elif search_mode == "prefix":
            cond = [["name", "=ilike", name + "%"]]
        else:
            cond = [["name", "ilike", name]]
        if condition:
            cond = [cond, condition]
        ids2 = self.search(cond, limit=limit)
        ids = list(set(ids1 + ids2))
        return self.name_get(ids, context=context)

    def copy(self, ids, context={}):
        replace_id=context.get("replace_id")
        obj = self.browse(ids)[0]
        code = obj.code
        if not replace_id:
            for i in range(1, 10):
                code = obj.code + " (%s)" % i
                res = self.search([["code", "=", code]])
                if not res:
                    break
        vals = {
            "name": obj.name,
            "code": code,
            "type": obj.type,
            "uom_id": obj.uom_id.id,
            #"parent_id": obj.parent_id.id, XXX
            "description": obj.description,
            "image": obj.image,
            "categs": [("set", [c.id for c in obj.categs])],
            "purchase_price": obj.purchase_price,
            "purchase_account_id": obj.purchase_account_id.id,
            "purchase_tax_id": obj.purchase_tax_id.id,
            "supplier_id": obj.supplier_id.id,
            "sale_price": obj.sale_price,
            "categ_id": obj.categ_id.id,
            "sale_account_id": obj.sale_account_id.id,
            "sale_tax_id": obj.sale_tax_id.id,
            "sale_return_account_id": obj.sale_return_account_id.id,
            "sale_promotion_account_id": obj.sale_promotion_account_id.id,
            "sale_promotion_tax_id": obj.sale_promotion_tax_id.id,
            "cost_method": obj.cost_method,
            "stock_in_account_id": obj.stock_in_account_id.id,
            "stock_out_account_id": obj.stock_out_account_id.id,
            "bin_location": obj.bin_location,
            "sale_company_id": obj.sale_company_id.id,
            "attributes": [],
        }
        vals["attributes"] = [("delete_all",)]
        for attr in obj.attributes:
            vals["attributes"].append(("create", {"attribute_id": attr.attribute_id.id, "option_id": attr.option_id.id}))
        vals["pricelist_items"] = [("delete_all",)]
        for item in obj.pricelist_items:
            vals["pricelist_items"].append(("create", {"list_id": item.list_id.id, "price": item.price}))
        vals["images"] = [("delete_all",)]
        for image in obj.images:
            vals["images"].append(("create", {"image": image.image, "title": image.title}))
        print("vals", vals)
        if replace_id:
            self.write([replace_id],vals)
            new_id = replace_id
        else:
            new_id = self.create(vals)
        return {
            "next": {
                "name": "product",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "New product copied from %s" % obj.name,
        }

    def get_landed_cost(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt = Decimal(obj.purchase_price or 0) * Decimal(1 + (obj.purchase_duty_percent or 0) / 100) * Decimal(1 + (obj.purchase_ship_percent or 0) / 100)
            amt_cur = amt*Decimal(obj.purchase_currency_rate or 1)
            vals[obj.id] = {
                "landed_cost": amt,
                "landed_cost_conv": amt_cur,
            }
        return vals

    def get_auto_list_price(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.landed_cost_conv and obj.gross_profit and obj.gross_profit != 100:
                vals[obj.id] = obj.landed_cost_conv / (1 - obj.gross_profit / 100)
            else:
                vals[obj.id] = None
        return vals

    def get_max_discount(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.sale_price and obj.landed_cost_conv:
                vals[obj.id] = max(0, (obj.sale_price - obj.landed_cost_conv) / obj.sale_price * 100)
            else:
                vals[obj.id] = None
        return vals

    def get_price_index(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            if obj.sale_price and obj.landed_cost_conv:
                vals[obj.id] = obj.sale_price / obj.landed_cost_conv
            else:
                vals[obj.id] = None
        return vals

    def update_prices(self, context={}):
        print("update_prices")
        data = context["data"]
        purchase_price = data.get("purchase_price")
        purchase_currency_rate = data.get("purchase_currency_rate")
        purchase_duty_percent = data.get("purchase_duty_percent")
        purchase_ship_percent = data.get("purchase_ship_percent")
        if purchase_price:
            landed_cost = purchase_price * \
                (1 + (purchase_duty_percent or 0) / 100) * (1 + (purchase_ship_percent or 0) / 100)
            landed_cost_conv = landed_cost * (purchase_currency_rate or 1) 
        else:
            landed_cost = None
            landed_cost_conv = None
        gross_profit = data.get("gross_profit")
        if landed_cost_conv and gross_profit and gross_profit != 100:
            auto_list_price = landed_cost_conv / (1 - gross_profit / 100)
        else:
            auto_list_price = None
        sale_price = data.get("sale_price")
        if sale_price and landed_cost_conv:
            max_discount = max(0, (sale_price - landed_cost_conv) / sale_price * 100)
            price_index = sale_price / landed_cost
        else:
            max_discount = None
            price_index = None
        data.update({
            "landed_cost": landed_cost,
            "landed_cost_conv": landed_cost_conv,
            "auto_list_price": auto_list_price,
            "max_discount": max_discount,
            "price_index": price_index,
        })
        return data

    def get_ecom_sale_price(self, ids, context={}):
        raise Exception("Deprecated!")
        vals = {}
        for obj in self.browse(ids):
            if obj.ecom_discount_percent:
                p = (obj.sale_price or 0) * (1 - obj.ecom_discount_percent / 100)
                has_disc = True
            elif obj.ecom_special_price:
                p = obj.ecom_special_price
                has_disc = True
            else:
                p = obj.sale_price or 0
                has_disc = False
            vals[obj.id] = {
                "ecom_sale_price": p,
                "ecom_has_discount": has_disc,
            }
        return vals

    def create_variants(self, ids, context={}):  # deprecated
        print("##################################")
        print("product.create_variants", ids)
        obj = self.browse(ids[0])
        if obj.type != "master":
            raise Exception("Not a master product")
        if not obj.custom_options:
            raise Exception("No custom options for this product")
        variants = [{}]
        for opt in obj.custom_options:
            new_variants = []
            for variant in variants:
                for opt_val in opt.values:
                    new_variant = variant.copy()
                    new_variant[opt.code] = opt_val.code
                    new_variants.append(new_variant)
            variants = new_variants
        print("variants", len(variants), variants)
        count = 1
        for variant in variants:
            vals = {
                "code": "%s_VARIANT_%.2d" % (obj.code, count),
                "name": obj.name,
                "type": "stock",
                "uom_id": obj.uom_id.id,
                "parent_id": obj.id,
                "location_id": obj.location_id.id,
                "attributes": [],
            }
            for k, v in variant.items():
                name = "_CUST_OPT_" + k
                res = get_model("product.attribute").search([["name", "=", name]])
                if res:
                    attr_id = res[0]
                else:
                    attr_id = get_model("product.attribute").create({"name": name})
                vals["attributes"].append(("create", {
                    "attribute_id": attr_id,
                    "value": v,
                }))
            get_model("product").create(vals)
            count += 1
        return {
            "flash": "%d variants created" % len(variants),
        }

    def get_variant_attributes(self, ids, context={}):
        print("get_variant_attributes",ids)
        vals = {}
        for obj in self.browse(ids):
            attrs=[]
            attr_options={}
            for variant in obj.variants:
                for attr in variant.attributes:
                    if not attr.attribute_id or not attr.option_id:
                        continue
                    attr_code=attr.attribute_id.code
                    attr_name=attr.attribute_id.name
                    attrs.append((attr_name,attr_code))
                    opt_code=attr.option_id.code
                    opt_name=attr.option_id.name
                    opt_sequence=attr.option_id.sequence
                    if attr_code == "color":
                        opt_image=variant.image or attr.option_id.image
                    else:
                        opt_image=attr.option_id.image
                    #attr_options.setdefault(attr_code,[]).append((opt_sequence,opt_name,opt_code,opt_image))
                    attr_options.setdefault(attr_code,[]).append((opt_sequence,opt_name,opt_code))
            attrs=list(set(attrs))
            res=[]
            for attr_name,attr_code in sorted(attrs):
                attr_vals={
                    "code": attr_code,
                    "name": attr_name,
                    "values": [],
                }
                attr_options[attr_code]=list(set(attr_options[attr_code]))
                #for opt_sequence,opt_name,opt_code,opt_image in sorted(attr_options[attr_code]):
                for opt_sequence,opt_name,opt_code in sorted(attr_options[attr_code]):
                    attr_vals["values"].append({
                        "sequence": opt_sequence,
                        "code": opt_code,
                        "name": opt_name,
                        #"image": opt_image,
                    })
                res.append(attr_vals)
            vals[obj.id]=res
        print("vals",vals)
        return vals

    def get_customer_price(self,ids,context={}): # XXX: make it faster
        pricelist_id=context.get("pricelist_id")
        pricelist_ids=context.get("pricelist_ids")
        if pricelist_ids is None and pricelist_id:
            pricelist_ids=[pricelist_id]
        vals={}
        for obj in self.browse(ids):
            sale_price=None
            discount_text=None
            discount_percent=None
            if pricelist_ids:
                min_sale_price=None
                for item in obj.pricelist_items:
                    if item.list_id.id in pricelist_ids:
                        sale_price=(item.price or 0)
                        if min_sale_price is None or sale_price<min_sale_price:
                            min_sale_price=sale_price
                            discount_text=item.discount_text
                            discount_percent=item.discount_percent
                sale_price=min_sale_price
            if sale_price is None:
                sale_price=(obj.sale_price or 0)
            has_discount=sale_price<(obj.sale_price or 0)
            vals[obj.id]={
                "customer_price": sale_price,
                "customer_has_discount": has_discount,
                "customer_discount_text": discount_text,
                "customer_discount_percent": discount_percent,
            }
        return vals

    def get_stock_qty(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            qty=0
            for loc in obj.locations:
                qty+=loc.stock_qty or 0
            vals[obj.id]=qty
        return vals

    def to_draft(self,ids,context={}):
        for obj in self.browse(ids):
            obj.write({"state": "draft","is_published": False}) #XXX

    def approve(self,ids,context={}):
        for obj in self.browse(ids):
            res=self.search([["code","=",obj.code],["state","=","approved"],["company_id","=",obj.company_id.id]])
            if res:
                repl_id=res[0]
                obj.copy(context={"replace_id": repl_id})
                obj.write({"active": False})
            else:
                vals = {
                    "state": "approved",
                }
                if not obj.parent_id:
                    group_ids = [] #XXX 
                    for group in obj.groups:
                        group_ids.append(group.id)
                    res = get_model("product.group").search([["code","=","new"]])
                    if res and res[0] not in group_ids:
                        group_ids.append(res[0])
                    vals.update({
                        "is_published": True,
                        "groups": [("set",group_ids)]
                    })
                if not obj.approve_date:
                    t = time.strftime("%Y-%m-%d %H:%M:%S")
                    vals.update({"approve_date": t})
                obj.write(vals)
        return {
            "flash": "Products approved",
        }

    def ecom_preview(self,ids,context={}):
        prod_id=ids[0]
        return {
            "next": {
                "type": "url",
                "url": "/ecom_product?product_id=%s"%prod_id,
            }
        }

    def get_sale_price_order_uom(self,ids,context={}):
        vals={}
        for obj in self.browse(ids):
            factor=obj.sale_to_invoice_uom_factor or 1
            vals[obj.id]=math.ceil((obj.sale_price or 0)*factor)
        return vals

    def create_thumbnails(self,ids,context={}):
        print("Product.create_thumbnails",ids)
        for obj in self.browse(ids):
            if not obj.image:
                continue
            utils.create_thumbnails(obj.image)

Product.register()
