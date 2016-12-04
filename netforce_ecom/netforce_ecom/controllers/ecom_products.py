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

from netforce.controller import Controller
from netforce.template import render
from netforce.model import get_model
from netforce.database import get_connection, get_active_db  # XXX: move this
from netforce.locale import set_active_locale, get_active_locale
from .cms_base import BaseController

def list_parent(obj, lst):
    if obj.parent_id:
        lst = list_parent(obj.parent_id, lst)
    lst.append(obj)
    return lst

def get_categs(condition):
    print("get_categs")
    res=get_model("product").read_group(["categ_id"],condition=condition)
    categ_nums={}
    for r in res:
        categ_id=r["categ_id"][0] if r["categ_id"] else None
        categ_nums.setdefault(categ_id,0)
        categ_nums[categ_id]+=r["_count"]
    res=get_model("product.categ").search_read([],["code","name","parent_id"])
    categ_ids={}
    for r in res:
        categ_ids[r["id"]]=r
    top_categs=[]
    for r in res:
        parent_id=r["parent_id"][0] if r["parent_id"] else None
        if parent_id:
            parent=categ_ids[parent_id]
            parent.setdefault("sub_categories",[]).append(r)
        else:
            top_categs.append(r)
    for categ_id,num in categ_nums.items():
        if not categ_id:
            continue
        categ=categ_ids[categ_id]
        categ["num_products"]=num
    def _set_total_num(c):
        for s in c.get("sub_categories",[]):
            _set_total_num(s)
        if c.get("num_products") is None:
            c["num_products"]=0
        for s in c.get("sub_categories",[]):
            c["num_products"]+=s["num_products"]
    for c in top_categs:
        _set_total_num(c)
    return top_categs

def get_brands(condition):
    print("get_brands")
    res=get_model("product").read_group(["brand_id"],condition=condition)
    brand_nums={}
    for r in res:
        brand_id=r["brand_id"][0] if r["brand_id"] else None
        brand_nums.setdefault(brand_id,0)
        brand_nums[brand_id]+=r["_count"]
    res=get_model("product.brand").search_read([],["code","name","parent_id"])
    brand_ids={}
    for r in res:
        brand_ids[r["id"]]=r
    top_brands=[]
    for r in res:
        parent_id=r["parent_id"][0] if r["parent_id"] else None
        if parent_id:
            parent=brand_ids[parent_id]
            parent.setdefault("sub_brands",[]).append(r)
        else:
            top_brands.append(r)
    for brand_id,num in brand_nums.items():
        if not brand_id:
            continue
        brand=brand_ids[brand_id]
        brand["num_products"]=num
    def _set_total_num(c):
        for s in c.get("sub_brands",[]):
            _set_total_num(s)
        if c.get("num_products") is None:
            c["num_products"]=0
        for s in c.get("sub_brands",[]):
            c["num_products"]+=s["num_products"]
    for c in top_brands:
        _set_total_num(c)
    return top_brands

def get_price_range(products, checked):
    if not products: return []
    price_min = int(min(map(lambda product: product.type in ["stock", "master"] and  product.sale_price or 0, products)))
    price_max = int(max(map(lambda product: product.type in ["stock", "master"] and  product.sale_price or 0, products)))
    i, price_range = 0, list(range(price_min, price_max , 500))
    for r in price_range:
        try:
            data = (str(price_range[i]), str(price_range[i + 1] - 1))
        except IndexError:
            data = (str(price_range[i]), str(price_max))
        print(checked, list(data), checked == list(data))
        price_range[i] = {"value": "%s-%s" % data, "text": "%s - %s" % data, "checked": "checked" if checked == list(data) else ""}
        i = i + 1
    return price_range

def get_supps(products=None):
    root_company  = ["All Companies"]
    if products:
        suppliers = []
        products  = filter(lambda product: product and product.company_id and product.type != "service", products)
        companies = map(lambda product: product.company_id, products)
        for company in companies:
            while company.parent_id and company.parent_id.name not in root_company: company = company.parent_id
            if company.name not in [s.name for s in set(suppliers)]: suppliers.append(company)
        return set(suppliers)
    else:
        return None

def get_events():
    res = get_model("product.group").search([["code","=","events"]])
    if res:
        return get_model("product.group").search_browse([["parent_id","=",res[0]]])
    else:
        return None

def get_last_level(categ):
    while(get_model("product.categ").search_browse([["parent_id","=",categ.id]])):
        categ = get_model("product.categ").search_browse([["parent_id","=",categ.id]],order="code")[0]
    if categ.parent_id:
        return get_model("product.categ").search_browse([["parent_id","=",categ.parent_id.id]])
    else:
        return None

class Products(BaseController):
    _path = "/ecom_products"

    def get(self):
        db = get_connection()
        try:
            description =""
            ctx = self.context
            categ_id=self.get_argument("categ_id",None)
            if categ_id:
                categ_id=int(categ_id)
            categ_code=self.get_argument("categ_code",None)
            if categ_code and not categ_id:
                res=get_model("product.categ").search([["code","=",categ_code]])
                if not res:
                    raise Exception("Product categ not found: '%s'"%categ_code)
                categ_id = res[0]
            brand_id=self.get_argument("brand_id",[])
            supp_id=self.get_argument("supp_id",[])
            if brand_id:
                bids=brand_id.split(",")
                brand_id = []
                for bid in bids:
                    bid=int(bid)
                    brand_id.append(bid)
            if supp_id:
                bids=supp_id.split(",")
                supp_id = []
                for bid in bids:
                    bid=int(bid)
                    supp_id.append(bid)
            ctx["brand_id"] = brand_id
            ctx["supp_id"] = supp_id
            price=self.get_argument("price",None)
            sort_by=self.get_argument("sort_by",None)
            cond = [["parent_id","=",None],["is_published","=",True]]
            cond_filter_categ = cond[:]
            cond_filter_brand = cond[:]
            if categ_id:
                cond.append(["categ_id","child_of",categ_id])
                ctx["list_parent_categ"] = list_parent(get_model("product.categ").browse(categ_id), lst=[]) # XXX
                cond_filter_brand.append(["categ_id","child_of",categ_id])
                categ = get_model("product.categ").browse(categ_id)
                categ_ctx = {
                    "name": categ.name, "image": categ.image if categ.sub_categories else None,
                    "last_level_categs": get_last_level(categ),
                }
                if categ.description:
                    description = categ.description
                else:
                    desc = categ
                    while desc.parent_id:
                        desc = desc.parent_id
                        if desc.description:
                            description = desc.description
                            break;
                while categ.parent_id:
                    categ = categ.parent_id
                if description:
                    ctx["title_description"] = description
                cond_filter_categ.append(["categ_id","child_of",categ.id])
                ctx["categ"] = categ_ctx
            if brand_id:
                cond.append(["brand_id","child_of",brand_id])
                cond_filter_categ.append(["brand_id","child_of",brand_id])
            if supp_id:
                cond.append(["company_id","child_of",supp_id])
                cond_filter_categ.append(["company_id","child_of",supp_id])
                cond_filter_brand.append(["company_id","child_of",supp_id])
            prices = ["0", "0"]
            if price:
                prices = price.split("-")
                if len(prices) != 2:
                    raise Exception("Incorrect Price format")
                if not prices[0].isdigit() or not prices[1].isdigit():
                    raise Exception("Min/Max prices is not digit")
                cond.append(["sale_price",">=",prices[0]])
                cond.append(["sale_price","<=",prices[1]])
                cond_filter_categ.append(["sale_price",">=",prices[0]])
                cond_filter_categ.append(["sale_price","<=",prices[1]])
                cond_filter_brand.append(["sale_price",">=",prices[0]])
                cond_filter_brand.append(["sale_price","<=",prices[1]])
            website=ctx["website"]
            browse_ctx={
                "pricelist_id": website.sale_channel_id.pricelist_id.id if website.sale_channel_id else None,
                "product_filter": cond,
            }
            user_id=self.get_cookie("user_id",None)
            if user_id:
                user_id=int(user_id)
                user=get_model("base.user").browse(user_id)
                contact = user.contact_id
                if contact.sale_price_list_id.id:
                    browse_ctx["pricelist_id"] =contact.sale_price_list_id.id 
                
            products = get_model("product").search_browse(condition=cond,order=sort_by,context=browse_ctx)

            cond_filter_supp = cond[:]
            if supp_id: cond_filter_supp.remove(["company_id","child_of", supp_id])

            ctx["products"] = products
            ctx["categs"] = get_categs(cond_filter_categ)
            ctx["brands"] = get_brands(cond_filter_brand)
            ctx["suppliers"] = get_supps(get_model("product").search_browse(condition=cond_filter_supp, order=sort_by, context=browse_ctx))
            ctx["events"] = get_events()
            ctx["pricerange"] = get_price_range(get_model("product").search_browse([],context=browse_ctx), prices)
            ctx["filter_product_groups"]=get_model("product.group").search_browse([["code","=","recommended"]],context=browse_ctx)[0]
            data={
                "categ_id": categ_id,
                "brand_id": brand_id,
                "price": price,
                "sort_by": sort_by,
                "supp_id": supp_id,
            }
            content = render("ecom_products", ctx, data=data)
            ctx["content"] = content
            html = render("cms_layout", ctx, data=data)
            self.write(html)
            db.commit()
        except:
            self.redirect("/cms_page_not_found")
            import traceback
            traceback.print_exc()
            db.rollback()

Products.register()
