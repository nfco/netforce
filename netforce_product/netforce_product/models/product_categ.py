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


class ProductCateg(Model):
    _name = "product.categ"
    _string = "Product Category"
    _export_field="code"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "code": fields.Char("Short Code", search=True),
        "parent_id": fields.Many2One("product.categ", "Parent Category"),
        "description": fields.Text("Description"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "products": fields.One2Many("product", "categ_id","Products", operator="child_of", condition=[["is_published","=",True]]),
        "image": fields.File("Image"),
        "sub_categories": fields.One2Many("product.categ", "parent_id", "Sub Categories"),
        "num_products": fields.Integer("Number of products", function="get_num_products"),
        "gross_profit": fields.Decimal("Gross Profit (%)"),
        "sale_account_id": fields.Many2One("account.account", "Sales Account", multi_company=True),
        "sale_tax_id": fields.Many2One("account.tax.rate", "Sales Tax"),
        "purchase_account_id": fields.Many2One("account.account", "Purchase Account", multi_company=True),
        "purchase_tax_id": fields.Many2One("account.tax.rate", "Purchase Tax"),
        "cost_method": fields.Selection([["standard", "Standard Cost"], ["average", "Weighted Average"], ["fifo", "FIFO"], ["lifo", "LIFO"]], "Costing Method"),
        "cogs_account_id": fields.Many2One("account.account", "Cost Of Goods Sold Account", multi_company=True),
    }
    _order = "name"
    _constraints = ["_check_cycle"]

    def get_full_parent_name(self, obj_id):
        obj = self.browse(obj_id)
        full = [obj.name]
        while obj.parent_id:
            obj = obj.parent_id
            full.append(obj.name)
        name = "/".join(full[::-1])
        return name

    def get_num_products(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            nums = 0
            for product in obj.products:
                if not product.parent_id:
                    nums += 1
            vals[obj.id] = nums
        return vals 

    def name_get(self, ids, context={}):
        if not access.check_permission(self._name, "read", ids):
            return [(id, "Permission denied") for id in ids]
        f_name = self._name_field or "name"
        f_image = self._image_field or "image"
        if f_image in self._fields:
            show_image = True
            fields = [f_name, f_image]
        else:
            show_image = False
            fields = [f_name]
        res = self.read(ids, fields)
        for r in res:
            r[f_name] = self.get_full_parent_name(r["id"])
        if show_image:
            return [(r["id"], r[f_name], r[f_image]) for r in res]
        else:
            return [(r["id"], r[f_name]) for r in res]

    def update_sale_prices(self, ids, context={}):
        obj=self.browse(ids[0])
        if not obj.gross_profit:
            raise Exception("Missing gross profit")
        n=0
        for prod in get_model("product").search_browse([["categ_id","=",obj.id]]):
            sale_price=round(prod.landed_cost/(1-obj.gross_profit/100),2)
            prod.write({"gross_profit":obj.gross_profit, "sale_price":sale_price})
            n+=1
        return {
            "flash": "%d products updated"%n,
        }

ProductCateg.register()
