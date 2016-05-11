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
from netforce.utils import get_data_path
from netforce.database import get_active_db
import time
import uuid
from netforce.access import get_active_company, set_active_user, get_active_user
from . import utils
from decimal import *


class SaleQuot(Model):
    _name = "sale.quot"
    _string = "Quotation"
    _audit_log = True
    _name_field = "number"
    _key = ["number"]
    _multi_company = True
    _fields = {
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Ref", search=True),
        "contact_id": fields.Many2One("contact", "Contact", required=True, search=True),
        "date": fields.Date("Date", required=True, search=True),
        "exp_date": fields.Date("Valid Until"),
        "state": fields.Selection([("draft", "Draft"), ("waiting_approval", "Awaiting Approval"), ("approved", "Approved"), ("won", "Won"), ("lost", "Lost"), ("revised", "Revised")], "Status", function="get_state", store=True),
        "lines": fields.One2Many("sale.quot.line", "quot_id", "Lines"),
        "amount_subtotal": fields.Decimal("Subtotal", function="get_amount", function_multi=True, store=True),
        "amount_tax": fields.Decimal("Tax Amount", function="get_amount", function_multi=True, store=True),
        "amount_total": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_total_words": fields.Char("Total Words", function="get_amount_total_words"),
        "qty_total": fields.Decimal("Total", function="get_qty_total"),
        "currency_id": fields.Many2One("currency", "Currency", required=True),
        "opport_id": fields.Many2One("sale.opportunity", "Opportunity", search=True),
        "user_id": fields.Many2One("base.user", "Owner", search=True),
        "tax_type": fields.Selection([["tax_ex", "Tax Exclusive"], ["tax_in", "Tax Inclusive"], ["no_tax", "No Tax"]], "Tax Type", required=True),
        "sales": fields.One2Many("sale.order", "quot_id", "Sales Orders"),
        "payment_terms": fields.Text("Payment Terms"),
        "other_info": fields.Text("Other Information"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "activities": fields.One2Many("activity", "related_id", "Activities"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "uuid": fields.Char("UUID"),
        "price_list_id": fields.Many2One("price.list", "Price List"),
        "emails": fields.One2Many("email.message", "related_id", "Emails"),
        "company_id": fields.Many2One("company", "Company"),
        "related_id": fields.Reference([["issue", "Issue"]], "Related To"),
        "ship_term_id": fields.Many2One("ship.term", "Shipping Terms"),
        "sequence_id": fields.Many2One("sequence", "Number Sequence"),
        "job_template_id": fields.Many2One("job.template", "Service Order Template"),
        "lost_sale_code_id": fields.Many2One("reason.code", "Lost Sale Reason Code", condition=[["type", "=", "lost_sale"]]),
        "agg_amount_total": fields.Decimal("Total Amount", agg_function=["sum", "amount_total"]),
        "agg_amount_subtotal": fields.Decimal("Total Amount w/o Tax", agg_function=["sum", "amount_subtotal"]),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
        "est_costs": fields.One2Many("quot.cost","quot_id","Costs"),
        "est_cost_amount": fields.Float("Estimated Cost Amount", function="get_est_profit", function_multi=True),
        "est_profit_amount": fields.Float("Estimated Profit Amount", function="get_est_profit", function_multi=True),
        "est_margin_percent": fields.Float("Estimated Margin %", function="get_est_profit", function_multi=True),
        "currency_rates": fields.One2Many("custom.currency.rate","related_id","Currency Rates"),
    }

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="sale_quot")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            if not num:
                return None
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    def _get_currency_rates(self,context={}):
        settings = get_model("settings").browse(1)
        lines=[]
        date = time.strftime("%Y-%m-%d")
        val = {
            "currency_id": settings.currency_id.id,
            "rate": settings.currency_id.get_rate(date,"sell") or 1
        }
        if context.get('action_name'):
            # default for new quotation create via quotation form
            lines.append(val)
        else:
            # When users create or copy quotation from other modules or methods, one2many field cannot be appended without action key
            # bacause it must be created in the database along with quotation itself.
            # If action key such as 'create', 'delete' is missing, the default line will not be created.
            # So, the action_key 'create' has to be appended into the list also.
            lines.append(("create",val))
        return lines

    _defaults = {
        "state": "draft",
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "number": _get_number,
        "currency_id": _get_currency,
        "tax_type": "tax_ex",
        "user_id": lambda self, context: get_active_user(),
        "uuid": lambda *a: str(uuid.uuid4()),
        "company_id": lambda *a: get_active_company(),
        "currency_rates": _get_currency_rates,
    }
    _constraints = ["check_fields"]
    _order = "date desc"

    def check_fields(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state in ("waiting_approval", "approved"):
                if not obj.lines:
                    raise Exception("No lines in quotation")

    def create(self, vals, **kw):
        id = super().create(vals, **kw)
        self.function_store([id])
        return id

    def write(self, ids, vals, **kw):
        opport_ids = []
        for obj in self.browse(ids):
            if obj.opport_id:
                opport_ids.append(obj.opport_id.id)
        super().write(ids, vals, **kw)
        if opport_ids:
            get_model("sale.opportunity").function_store(opport_ids)
        self.function_store(ids)

    def function_store(self, ids, field_names=None, context={}):
        super().function_store(ids, field_names, context)
        opport_ids = []
        for obj in self.browse(ids):
            if obj.opport_id:
                opport_ids.append(obj.opport_id.id)
        if opport_ids:
            get_model("sale.opportunity").function_store(opport_ids)

    def get_amount(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            vals = {}
            subtotal = 0
            tax = 0
            for line in obj.lines:
                if line.is_hidden:
                    continue
                if line.tax_id:
                    line_tax = get_model("account.tax.rate").compute_tax(
                        line.tax_id.id, line.amount, tax_type=obj.tax_type)
                else:
                    line_tax = 0
                tax += line_tax
                if obj.tax_type == "tax_in":
                    subtotal += (line.amount or 0) - line_tax
                else:
                    subtotal += line.amount or 0
            vals["amount_subtotal"] = subtotal
            vals["amount_tax"] = tax
            vals["amount_total"] = subtotal + tax
            res[obj.id] = vals
        return res

    def get_qty_total(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            qty = sum([line.qty for line in obj.lines])
            res[obj.id] = qty or 0
        return res

    def submit_for_approval(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state != "draft":
                raise Exception("Invalid state")
            obj.write({"state": "waiting_approval"})
        self.trigger(ids, "submit_for_approval")

    def approve(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state not in ("draft", "waiting_approval"):
                raise Exception("Invalid state")
            obj.write({"state": "approved"})

    def update_amounts(self, context):
        print("update_amounts")
        data = context["data"]
        data["amount_subtotal"] = 0
        data["amount_tax"] = 0
        tax_type = data["tax_type"]
        #===============>>>
        def _get_relative_currency_rate(currency_id):
            rate=None
            for r in data['currency_rates']:
                if r.get('currency_id')==currency_id:
                    rate=r.get('rate') or 0
                    break
            if rate is None:
                print(data['date'],currency_id,data['currency_id'])
                rate_from=get_model("currency").get_rate([currency_id],data['date']) or Decimal(1)
                rate_to=get_model("currency").get_rate([data['currency_id']],data['date']) or Decimal(1)
                rate=rate_from/rate_to
            return rate
        item_costs={}
        for cost in data['est_costs']:
            if not cost:
                continue
            amt=cost['amount'] or 0
            if cost.get('currency_id'):
                print(cost.get("currency_id.id"),cost.get("currency_id"))
                rate=_get_relative_currency_rate(cost.get("currency_id"))
                amt=amt*rate
            comps=[]
            if cost.get("sequence"):
                for comp in cost['sequence'].split("."):
                    comps.append(comp)
                    path=".".join(comps)
                    k=(data['id'],path)
                    item_costs.setdefault(k,0)
                    item_costs[k]+=amt
        #<<<===============
        for line in data["lines"]:
            if not line:
                continue
            amt = (line.get("qty") or 0) * (line.get("unit_price") or 0)
            if line.get("discount"):
                disc = amt * line["discount"] / Decimal(100)
                amt -= disc
            else:
                disc = 0
            line["amount"] = amt
            #===============>>>
            k=None
            if id in data:
                k=(data['id'],line.get("sequence",0))
            else:
                k=(line.get("sequence",0))
            cost=item_costs.get(k,0)
            profit=amt-cost
            margin=profit*100/amt if amt else 0
            line["est_cost_amount"]=cost
            line["est_profit_amount"]=profit
            line["est_margin_percent"]=margin
            #<<<===============
        hide_parents=[]
        for line in data["lines"]:
            if not line:
                continue
            if line.get("sequence") and line.get("hide_sub"):
                hide_parents.append(line["sequence"])
        is_hidden={}
        hide_totals={}
        for line in data["lines"]:
            if not line:
                continue
            if not line.get("sequence"):
                continue
            parent_seq=None
            for seq in hide_parents:
                if line["sequence"].startswith(seq+"."):
                    parent_seq=seq
                    break
            if parent_seq:
                is_hidden[line["sequence"]]=True
                hide_totals.setdefault(parent_seq,0)
                hide_totals[parent_seq]+=line["amount"]
        for line in data["lines"]:
            if not line:
                continue
            if line.get("sequence") and line.get("hide_sub"):
                line["amount"]=hide_totals.get(line["sequence"],0)
                if line["qty"]:
                    line["unit_price"]=line["amount"]/line["qty"]
        for line in data["lines"]:
            if is_hidden.get(line.get("sequence")):
                continue
            tax_id = line.get("tax_id")
            if tax_id:
                tax = get_model("account.tax.rate").compute_tax(tax_id, line["amount"], tax_type=tax_type)
                data["amount_tax"] += tax
            else:
                tax = 0
            if tax_type == "tax_in":
                data["amount_subtotal"] += line["amount"] - tax
            else:
                data["amount_subtotal"] += line["amount"]
        data["amount_total"] = data["amount_subtotal"] + data["amount_tax"]
        return data

    def onchange_product(self, context):
        data = context["data"]
        contact_id = data.get("contact_id")
        if contact_id:
            contact = get_model("contact").browse(contact_id)
        else:
            contact = None
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["description"] = prod.description
        line["est_margin_percent_input"] = prod.gross_profit
        line["qty"] = 1
        if prod.uom_id is not None:
            line["uom_id"] = prod.uom_id.id
        pricelist_id = data["price_list_id"]
        price = None
        if pricelist_id:
            price = get_model("price.list").get_price(pricelist_id, prod.id, 1)
            price_list = get_model("price.list").browse(pricelist_id)
            price_currency_id = price_list.currency_id.id
        if price is None:
            price = prod.sale_price
            settings = get_model("settings").browse(1)
            price_currency_id = settings.currency_id.id
        if price is not None:
            currency_id = data["currency_id"]
            price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
            line["unit_price"] = price_cur
        if prod.sale_tax_id is not None:
            line["tax_id"] = prod.sale_tax_id.id
        data = self.update_amounts(context)
        return data

    def onchange_qty(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        pricelist_id = data["price_list_id"]
        qty = line["qty"]
        if line.get("unit_price") is None:
            price = None
            if pricelist_id:
                price = get_model("price.list").get_price(pricelist_id, prod.id, qty)
                price_list = get_model("price.list").browse(pricelist_id)
                price_currency_id = price_list.currency_id.id
            if price is None:
                price = prod.sale_price
                settings = get_model("settings").browse(1)
                price_currency_id = settings.currency_id.id
            if price is not None:
                currency_id = data["currency_id"]
                price_cur = get_model("currency").convert(price, price_currency_id, currency_id)
                line["unit_price"] = price_cur
        data = self.update_amounts(context)
        return data

    def onchange_contact(self, context):
        data = context["data"]
        contact_id = data.get("contact_id")
        if not contact_id:
            return {}
        contact = get_model("contact").browse(contact_id)
        data["payment_terms"] = contact.payment_terms
        data["price_list_id"] = contact.sale_price_list_id.id
        if contact.currency_id:
            data["currency_id"] = contact.currency_id.id
        else:
            settings = get_model("settings").browse(1)
            data["currency_id"] = settings.currency_id.id
        return data

    def onchange_uom(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        uom_id = line.get("uom_id")
        if not uom_id:
            return {}
        uom = get_model("uom").browse(uom_id)
        if prod.sale_price is not None:
            line["unit_price"] = prod.sale_price * uom.ratio / prod.uom_id.ratio
        data = self.update_amounts(context)
        return data

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "ref": obj.number,
            "contact_id": obj.contact_id.id,
            "currency_id": obj.currency_id.id,
            "tax_type": obj.tax_type,
            "payment_terms": obj.payment_terms,
            "other_info": obj.other_info,
            "exp_date": obj.exp_date,
            "opport_id": obj.opport_id.id,
            "lines": [],
        }
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "discount": line.discount,
                "tax_id": line.tax_id.id,
                'amount': line.amount,
                'sequence': line.sequence,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, context=context)
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "quot",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Quotation %s copied from %s" % (new_obj.number, obj.number),
        }

    def revise(self, ids, context):
        obj = self.browse(ids)[0]
        res = self.copy(ids, context)
        obj.write({"state": "revised"})
        return res

    def copy_to_sale_order(self,ids,context):
        id=ids[0]
        obj=self.browse(id)

        if obj.state not in ("won"):
            raise Exception("You can only copy to sale order in 'Won' state")

        sale_vals={
            "ref": obj.number,
            "quot_id": obj.id,
            "contact_id": obj.contact_id.id,
            "currency_id": obj.currency_id.id,
            "tax_type": obj.tax_type,
            "lines": [],
            "user_id": obj.user_id.id,
            "other_info": obj.other_info,
            "payment_terms": obj.payment_terms,
            "price_list_id": obj.price_list_id.id,
            "job_template_id": obj.job_template_id.id,
            "est_costs": [],
            "currency_rates": [],
        }
        for line in obj.lines:
            if not line.qty or not line.uom_id or not line.unit_price:
                continue
            prod=line.product_id
            line_vals={
                "sequence": line.sequence,
                "product_id": prod.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price if not line.is_hidden else 0,
                "discount": line.discount if not line.is_hidden else 0,
                "tax_id": line.tax_id.id if not line.is_hidden else None,
                "location_id": prod.location_id.id if prod else None,
            }
            sale_vals["lines"].append(("create",line_vals))
        for cost in obj.est_costs:
            cost_vals={
                "sequence": cost.sequence,
                "product_id": cost.product_id.id,
                "description": cost.description,
                "supplier_id": cost.supplier_id.id,
                "list_price": cost.list_price,
                "purchase_price": cost.purchase_price,
                "purchase_duty_percent": cost.purchase_duty_percent,
                "purchase_ship_percent": cost.purchase_ship_percent,
                "landed_cost": cost.landed_cost,
                "qty": cost.qty,
                "currency_id": cost.currency_id.id,
            }
            sale_vals["est_costs"].append(("create",cost_vals))
        for r in obj.currency_rates:
            rate_vals={
                "currency_id": r.currency_id.id,
                "rate": r.rate,
            }
            sale_vals["currency_rates"].append(("create",rate_vals))
        sale_id=get_model("sale.order").create(sale_vals,context=context)
        sale=get_model("sale.order").browse(sale_id)
        return {
            "next": {
                "name": "sale",
                "mode": "form",
                "active_id": sale_id,
            },
            "flash": "Sale order %s created from quotation %s"%(sale.number,obj.number)
        }

    def do_won(self, ids, context={}):
        for obj in self.browse(ids):
            assert obj.state == "approved"
            obj.write({"state": "won"})

    def do_lost(self, ids, context={}):
        for obj in self.browse(ids):
            assert obj.state == "approved"
            obj.write({"state": "lost"})

    def do_reopen(self, ids, context={}):
        for obj in self.browse(ids):
            assert obj.state in ("won", "lost")
            obj.write({"state": "approved"})

    def get_state(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            state = obj.state
            if state == "approved":
                found = False
                for sale in obj.sales:
                    if sale.state in ("confirmed", "done"):
                        found = True
                        break
                if found:
                    state = "won"
            vals[obj.id] = state
        return vals

    def view_link(self, ids, context={}):
        obj = self.browse(ids)[0]
        uuid = obj.uuid
        dbname = get_active_db()
        return {
            "next": {
                "type": "url",
                "url": "/view_quot?dbname=%s&uuid=%s" % (dbname, uuid),
            }
        }

    def get_template_quot_form(self, ids, context={}):
        obj = self.browse(ids)[0]
        has_discount=False
        for line in obj.lines:
            if line.discount:
                has_discount=True
        if has_discount:
            return "quot_form_disc"
        else:
            return "quot_form"

    def to_draft(self, ids, context={}):
        obj = self.browse(ids)[0]
        obj.write({"state": "draft"})

    def get_amount_total_words(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amount_total_words = utils.num2word(obj.amount_total)
            vals[obj.id] = amount_total_words
            return vals

    def onchange_sequence(self, context={}):
        data = context["data"]
        seq_id = data["sequence_id"]
        context['date']=data['date']
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["number", "=", num]])
            if not res:
                break
            get_model("sequence").increment_number(seq_id, context=context)
        data["number"] = num
        return data

    def onchange_cost_product(self,context):
        data=context["data"]
        path=context["path"]
        line=get_data_path(data,path,parent=True)
        prod_id=line.get("product_id")
        if prod_id:
            prod=get_model("product").browse(prod_id)
            line["description"]=prod.name
            line["list_price"]=prod.purchase_price
            line["purchase_price"]=prod.purchase_price
            line["landed_cost"]=prod.landed_cost
            line["qty"]=1
            line["uom_id"]=prod.uom_id.id
            line["currency_id"]=prod.purchase_currency_id.id
            line["purchase_duty_percent"]=prod.purchase_duty_percent
            line["purchase_ship_percent"]=prod.purchase_ship_percent
            line["landed_cost"]=prod.landed_cost
            line["amount"]=line['qty']*line['landed_cost'] or 0

            if prod.suppliers:
                line["supplier_id"]=prod.suppliers[0].supplier_id.id
        return data

    def get_est_profit(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            cost=0
            for line in obj.lines:
                cost+=line.est_cost_amount or 0
            profit = (obj.amount_subtotal or 0) - cost
            margin=profit*100/obj.amount_subtotal if obj.amount_subtotal else None
            vals[obj.id] = {
                "est_cost_amount": cost,
                "est_profit_amount": profit,
                "est_margin_percent": margin,
            }
        return vals

    def create_est_costs(self,ids,context={}):
        obj=self.browse(ids[0])
        del_ids=[]
        for cost in obj.est_costs:
            if cost.product_id:
                del_ids.append(cost.id)
        get_model("quot.cost").delete(del_ids)
        #obj.write({"est_costs":[("delete_all",)]})
        for line in obj.lines:
            prod=line.product_id
            if not prod:
                continue
            if not prod.purchase_price:
                continue
            if not line.sequence:
                continue
            if "bundle" == prod.type:
                continue
            vals={
                "quot_id": obj.id,
                "sequence": line.sequence if not line.is_hidden else line.parent_sequence,
                "product_id": prod.id,
                "description": prod.name,
                "supplier_id": prod.suppliers[0].supplier_id.id if prod.suppliers else None,
                "list_price": prod.purchase_price,
                "purchase_price": prod.purchase_price,
                "landed_cost": prod.landed_cost,
                "purchase_duty_percent": prod.purchase_duty_percent,
                "purchase_ship_percent": prod.purchase_ship_percent,
                "qty": line.qty,
                "currency_id": prod.purchase_currency_id.id,
            }
            get_model("quot.cost").create(vals)

    def merge_quotations(self,ids,context={}):
        if len(ids)<2:
            raise Exception("Can not merge less than two quotations")
        contact_ids=[]
        currency_ids=[]
        tax_types=[]
        for obj in self.browse(ids):
            contact_ids.append(obj.contact_id.id)
            currency_ids.append(obj.currency_id.id)
            tax_types.append(obj.tax_type)
        contact_ids=list(set(contact_ids))
        currency_ids=list(set(currency_ids))
        tax_types=list(set(tax_types))
        if len(contact_ids)>1:
            raise Exception("Quotation customers have to be the same")
        if len(currency_ids)>1:
            raise Exception("Quotation currencies have to be the same")
        if len(tax_types)>1:
            raise Exception("Quotation tax types have to be the same")
        vals = {
            "contact_id": contact_ids[0],
            "currency_id": currency_ids[0],
            "tax_type": tax_types[0],
            "lines": [],
            "est_costs": [],
        }
        seq=0
        refs=[]
        for obj in sorted(self.browse(ids),key=lambda obj: obj.number):
            refs.append(obj.number)
            seq_map={}
            for line in obj.lines:
                seq+=1
                seq_map[line.sequence]=seq
                qty=line.qty or 0
                unit_price=line.unit_price or 0
                amt=qty*unit_price
                disc=amt*(line.discount or 0)/Decimal(100)
                line_vals = {
                    "sequence": seq,
                    "product_id": line.product_id.id,
                    "description": line.description,
                    "qty": qty,
                    "uom_id": line.uom_id.id,
                    "unit_price": unit_price,
                    "discount": disc,
                    "amount": amt,
                    "tax_id": line.tax_id.id,
                }
                vals["lines"].append(("create", line_vals))
            for cost in obj.est_costs:
                cost_vals={
                    "sequence": seq_map.get(cost.sequence),
                    "product_id": cost.product_id.id,
                    "description": cost.description,
                    "supplier_id": cost.supplier_id.id,
                    "list_price": cost.list_price,
                    "purchase_price": cost.purchase_price,
                    "landed_cost": cost.landed_cost,
                    "qty": cost.qty,
                    "currency_id": cost.currency_id.id,
                }
                vals["est_costs"].append(("create",cost_vals))
        vals['ref']=', '.join([ref for ref in refs])
        new_id = self.create(vals, context=context)
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "quot",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Quotations merged",
        }

    def onchange_est_margin(self,context={}):
        data=context["data"]
        path=context["path"]
        line=get_data_path(data,path,parent=True)
        margin=line["est_margin_percent_input"]
        amt=line["est_cost_amount"]/(1-margin/Decimal(100))
        price=round(amt/line["qty"])
        line["unit_price"]=price
        self.update_amounts(context)
        return data

    def get_relative_currency_rate(self,ids,currency_id):
        obj=self.browse(ids[0])
        rate=None
        for r in obj.currency_rates:
            if r.currency_id.id==currency_id:
                rate=r.rate
                break
        if rate is None:
            rate_from=get_model("currency").get_rate([currency_id],obj.date) or Decimal(1)
            rate_to=obj.currency_id.get_rate(obj.date) or Decimal(1)
            rate=rate_from/rate_to
        return rate

    def update_cost_amount(self,context={}):
        data=context['data']
        path=context['path']
        line=get_data_path(data,path,parent=True)
        line['amount']=(line['qty'] or 0) *(line['landed_cost'] or 0)
        return data

SaleQuot.register()
