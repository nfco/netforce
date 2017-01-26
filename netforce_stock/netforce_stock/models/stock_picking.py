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
from netforce.utils import get_data_path
from netforce.access import get_active_company, get_active_user, set_active_user


class Picking(Model):
    _name = "stock.picking"
    _string = "Stock Picking"
    _audit_log = True
    _name_field = "number"
    _key = ["company_id", "type", "number"]
    _multi_company = True
    _fields = {
        "type": fields.Selection([["in", "Goods Receipt"], ["internal", "Goods Transfer"], ["out", "Goods Issue"]], "Type", required=True),
        "journal_id": fields.Many2One("stock.journal", "Journal", required=True, search=True),
        "number": fields.Char("Number", required=True, search=True),
        "ref": fields.Char("Ref", search=True),
        "contact_id": fields.Many2One("contact", "Contact", search=True),
        "date": fields.DateTime("Date", required=True, search=True),
        "state": fields.Selection([("draft", "Draft"), ("pending", "Planned"), ("approved", "Approved"), ("done", "Completed"), ("voided", "Voided")], "Status", required=True),
        "lines": fields.One2Many("stock.move", "picking_id", "Lines"),
        "move_id": fields.Many2One("account.move", "Journal Entry"),
        "product_id": fields.Many2One("product", "Product", store=False, function_search="search_product"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"], ["project","Project"], ["job", "Service Order"], ["product.claim", "Claim Bill"], ["product.borrow", "Borrow Request"], ["stock.picking", "Picking"]], "Related To"),
        "currency_id": fields.Many2One("currency", "Currency", required=True),
        "addresses": fields.One2Many("address", "related_id", "Addresses"),
        "ship_address_id": fields.Many2One("address", "Shipping Address"),
        "qty_total": fields.Decimal("Total Quantity", function="get_qty_total"),
        "container_id": fields.Many2One("stock.container", "Container"),
        "company_id": fields.Many2One("company", "Company"),
        "gross_weight": fields.Decimal("Gross Weight"),
        "pending_by_id": fields.Many2One("base.user", "Pending By", readonly=True),
        "done_by_id": fields.Many2One("base.user", "Completed By", readonly=True),
        "done_approved_by_id": fields.Many2One("base.user", "Approved By", readonly=True),
        "employee_id": fields.Many2One("hr.employee", "Employee"),
        "ship_method_id": fields.Many2One("ship.method", "Shipping Method"),
        "ship_tracking": fields.Char("Tracking Number"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "ship_cost": fields.Decimal("Shipping Cost"),
        "ship_pay_by": fields.Selection([["company", "Company"], ["customer", "Customer"], ["supplier", "Supplier"]], "Shipping Paid By"),
        "landed_costs": fields.Many2Many("landed.cost","Landed Costs",function="get_landed_costs"),
        "messenger_id": fields.Many2One("messenger","Messenger"),
        "avail_messengers": fields.Many2Many("messenger","Available Messengers"),
        "currency_rate": fields.Decimal("Currency Rate",scale=6),
        "product_id2": fields.Many2One("product","Product",store=False,function_search="search_product2",search=True), #XXX ICC
        "sequence": fields.Decimal("Sequence",function="_get_related",function_context={"path":"ship_address_id.sequence"}),
        "delivery_slot_id": fields.Many2One("delivery.slot","Delivery Slot"),
        "note": fields.Text("Note"),
    }
    _order = "date desc,number desc"

    _sql_constraints = [
        ("key_uniq", "unique (company_id, type, number)", "The number of each company and type must be unique!")
    ]

    def _get_journal(self, context={}):
        pick_type = context.get("pick_type")
        settings = get_model("settings").browse(1)
        if pick_type == "in":
            journal_id = settings.pick_in_journal_id.id
        elif pick_type == "out":
            journal_id = settings.pick_out_journal_id.id
        elif pick_type == "internal":
            journal_id = settings.pick_internal_journal_id.id
        else:
            journal_id = None
        return journal_id

    def _get_number(self, context={}):
        pick_type = context.get("pick_type")
        journal_id = context.get("journal_id")
        seq_id = None
        if journal_id:
            journal = get_model("stock.journal").browse(journal_id)
            seq_id = journal.sequence_id.id
        if not seq_id and pick_type:
            seq_type = "pick_" + pick_type
            seq_id = get_model("sequence").find_sequence(seq_type)
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id,context=context)
            user_id = get_active_user()
            set_active_user(1)
            res = self.search([["number", "=", num]])
            set_active_user(user_id)
            if not res:
                return num
            get_model("sequence").increment_number(seq_id,context)

    def _get_type(self, context={}):
        return context.get("pick_type")

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    _defaults = {
        "state": "draft",
        "journal_id": _get_journal,
        "number": _get_number,
        "type": _get_type,
        "date": lambda *a: time.strftime("%Y-%m-%d %H:%M:%S"),
        "currency_id": _get_currency,
        "company_id": lambda *a: get_active_company(),
    }

    def delete(self, ids, **kw):
        move_ids = []
        for obj in self.browse(ids):
            for line in obj.lines:
                move_ids.append(line.id)
        get_model("stock.move").delete(move_ids)  # to update stored functions
        super().delete(ids, **kw)

    def copy_to_cust_invoice(self, ids, context):
        id = ids[0]
        return {
            "name": "cust_invoice_new",
            "from_pick_out_id": id,
        }

    def pending(self, ids, context={}):
        user_id = get_active_user()
        for obj in self.browse(ids):
            for move in obj.lines:
                move.write({"state": "pending", "date": obj.date})
                if obj.related_id and not move.related_id:
                    move.write({"related_id":"%s,%d"%(obj.related_id._model,obj.related_id.id)})
            obj.write({"state": "pending", "pending_by_id": user_id})

    def approve(self, ids, context={}):
        user_id = get_active_user()
        for obj in self.browse(ids):
            for move in obj.lines:
                move.write({"state": "approved", "date": obj.date})
            obj.write({"state": "approved"})

    def void(self, ids, context={}):
        for obj in self.browse(ids):
            for move in obj.lines:
                move.write({"state": "voided"})
                # change state in borrow requests
                if move.related_id._model=="product.borrow":
                    if not move.related_id.is_return_item:
                        move.related_id.write({"state": "approved"})
            obj.write({"state": "voided"})

    def to_draft(self,ids,context={}):
        for obj in self.browse(ids):
            move_ids=[]
            for move in obj.lines:
                move_ids.append(move.id)
            get_model("stock.move").to_draft(move_ids)
            obj.write({"state":"draft"})

    def set_done(self,ids,context={}):
        user_id=get_active_user()
        for obj in self.browse(ids):
            move_ids=[]
            for line in obj.lines:
                move_ids.append(line.id)
            desc=obj.number
            get_model("stock.move").write(move_ids,vals={"date":obj.date,"journal_id":obj.journal_id.id,"ref":obj.number},context=context)
            get_model("stock.move").set_done(move_ids,context=context)
            obj.write({"state":"done","done_by_id":user_id},context=context)
            obj.set_currency_rate()
            ## active function store at sale order
            if obj.related_id:
                if obj.related_id._model == 'sale.order':
                    so_id = obj.related_id.id
                    get_model("sale.order").function_store([so_id])
        self.check_order_qtys(ids)
        self.create_bundle_pickings(ids)
        self.trigger(ids,"done")

    def check_order_qtys(self, ids, context={}):
        obj = self.browse(ids)[0]
        if not obj.related_id:
            return
        model = obj.related_id._model
        if model == "sale.order":
            obj.related_id.check_delivered_qtys()
        elif model == "purchase.order":
            obj.related_id.check_received_qtys()

    def onchange_contact(self, context={}):
        settings = get_model("settings").browse(1)
        data = context["data"]
        contact_id = data["contact_id"]
        contact = get_model("contact").browse(contact_id)
        data["ship_address_id"] = contact.get_address(pref_type="shipping")
        if data["type"] == "in":
            data["journal_id"] = contact.pick_in_journal_id.id or settings.pick_in_journal_id.id
        elif data["type"] == "out":
            data["journal_id"] = contact.pick_out_journal_id.id or settings.pick_out_journal_id.id
        elif data["type"] == "internal":
            data["journal_id"] = contact.pick_internal_journal_id.id or settings.pick_internal_journal_id.id
        self.onchange_journal(context=context)
        return data

    def update_number(self,data):
        journal_id = data["journal_id"]
        if not journal_id:
            return data
        journal=get_model("stock.journal").browse(journal_id)
        sequence=journal.sequence_id
        if not sequence:
            return data
        prefix=sequence.prefix
        if not prefix:
            return data
        ctx={
            "pick_type": data["type"],
            "journal_id": journal_id,
            'date': data['date'][0:10],
        }
        number=data['number']
        if not number:
            data["number"] = self._get_number(context=ctx)
        else:
            prefix=get_model("sequence").get_prefix(prefix,context=ctx)
            date_format=False
            for p in ['m','y','Y']:
                p2='%('+p+')s'
                if p2 in sequence.prefix:
                    date_format=True
                    break
            if not date_format:
                return data
            pick_id=data.get('id')
            if pick_id:
                pick=self.browse(pick_id)
                if prefix in pick.number:
                    data['number']=pick.number
                    return data
            if prefix not in number:
                data["number"] = self._get_number(context=ctx)
        return data

    def onchange_journal(self, context={}):
        data = context["data"]
        journal_id = data["journal_id"]
        if not journal_id:
            return
        journal = get_model("stock.journal").browse(journal_id)
        data = self.update_number(data)
        for line in data["lines"]:
            if journal.location_from_id:
                line["location_from_id"] = journal.location_from_id.id
            if journal.location_to_id:
                line["location_to_id"] = journal.location_to_id.id
        return data

    def onchange_date(self, context={}):
        data = context["data"]
        data = self.update_number(data)
        return data

    def onchange_product(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["qty"] = 1
        if prod.uom_id is not None:
            line["uom_id"] = prod.uom_id.id
        if data["type"] == "in":
            if prod.purchase_price is not None:
                line["cost_price_cur"] = prod.purchase_price
        self.update_cost_price(context=context)
        return data

    def copy_to_invoice(self, ids, context):
        id = ids[0]
        obj = self.browse(id)
        number = get_model("account.invoice")._get_number(context={"type": obj.type, "inv_type": "invoice"})
        if obj.type == "out":
            if not obj.contact_id:
                raise Exception("Please select a customer for this goods issue first")
            inv_vals = {
                "type": "out",
                "inv_type": "invoice",
                "ref": obj.number,
                "number": number,
                "contact_id": obj.contact_id.id,
                "related_id": "%s,%s"%(obj.related_id._model,obj.related_id.id) if obj.related_id else None,
                "lines": [],
            }
            for line in obj.lines:
                prod = line.product_id
                line_vals = {
                    "product_id": prod.id,
                    "description": prod.description or "/",
                    "qty": line.qty,
                    "uom_id": line.uom_id.id,
                    "account_id": prod.sale_account_id.id,
                }
                if obj.related_id and obj.related_id._model == "sale.order":
                    so_line_id = obj.related_id.find_sale_line(prod.id)
                    so_line = get_model("sale.order.line").browse(so_line_id)
                else:
                    so_line = None
                if so_line:
                    line_vals["unit_price"] = so_line.unit_price
                    line_vals["tax_id"] = so_line.tax_id.id
                else:
                    line_vals["unit_price"] = prod.sale_price or 0
                    line_vals["tax_id"] = prod.sale_tax_id.id
                line_vals["amount"] = line_vals["unit_price"] * line_vals["qty"]
                inv_vals["lines"].append(("create", line_vals))
            inv_id = get_model("account.invoice").create(inv_vals, context={"type": "out", "inv_type": "invoice"})
            move_ids = get_model("stock.move").search([["picking_id", "=", obj.id]])
            get_model("stock.move").write(move_ids, {"invoice_id": inv_id})
            return {
                "next": {
                    "name": "view_invoice",
                    "active_id": inv_id,
                },
                "flash": "Customer invoice copied from goods issue",
            }
        elif obj.type == "in":
            if not obj.contact_id:
                raise Exception("Please select a supplier for this goods receipt first")
            inv_vals = {
                "type": "in",
                "inv_type": "invoice",
                "ref": obj.number,
                "number": number,
                "contact_id": obj.contact_id.id,
                "currency_id": obj.currency_id.id,
                "currency_rate": obj.currency_rate,
                "related_id": "%s,%s"%(obj.related_id._model,obj.related_id.id) if obj.related_id else None,
                "lines": [],
            }
            for line in obj.lines:
                prod = line.product_id
                # get account for purchase invoice
                purch_acc_id=None
                if prod:
                    # 1. get from product
                    purch_acc_id=prod.purchase_account_id and prod.purchase_account_id.id or None
                    # 2. if not get from master / parent product
                    if not purch_acc_id and prod.parent_id:
                        purch_acc_id=prod.parent_id.purchase_account_id.id
                    # 3. if not get from product category
                    categ=prod.categ_id
                    if categ and not purch_acc_id:
                        purch_acc_id= categ.purchase_account_id and categ.purchase_account_id.id or None
                line_vals = {
                    "product_id": line.product_id.id,
                    "description": prod.description or "/",
                    "qty": line.qty,
                    "uom_id": line.uom_id.id,
                    "unit_price": line.cost_price_cur,
                    "tax_id": prod.purchase_tax_id.id,
                    "account_id": purch_acc_id,
                    "amount": line.qty * line.cost_price_cur,
                }
                inv_vals["lines"].append(("create", line_vals))
            inv_id = get_model("account.invoice").create(inv_vals, context=context)
            move_ids = get_model("stock.move").search([["picking_id", "=", obj.id]])
            get_model("stock.move").write(move_ids, {"invoice_id": inv_id})
            return {
                "next": {
                    "name": "view_invoice",
                    "active_id": inv_id,
                },
                "flash": "Supplier invoice copied from goods receipt",
            }
        else:
            raise Exception("Invalid picking type")

    def copy(self, ids, from_location=None, to_location=None, state=None, type=None, context={}):
        print("picking.copy",ids)
        obj = self.browse(ids[0])
        if from_location:
            res=get_model("stock.location").search([["code","=",from_location]])
            if not res:
                raise Exception("Location code not found: %s"%from_location)
            from_loc_id=res[0]
        else:
            from_loc_id=None
        if to_location:
            res=get_model("stock.location").search([["code","=",to_location]])
            if not res:
                raise Exception("Location code not found: %s"%to_location)
            to_loc_id=res[0]
        else:
            to_loc_id=None
        vals = {
            "type": type and type or obj.type,
            "contact_id": obj.contact_id.id,
            "ref": obj.ref,
            "lines": [],
        }
        if obj.related_id:
            vals["related_id"] = "%s,%d" % (obj.related_id._model, obj.related_id.id)
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "location_from_id": from_loc_id and from_loc_id or line.location_from_id.id,
                "location_to_id": to_loc_id and to_loc_id or line.location_to_id.id,
                "lot_id": line.lot_id.id,
            }
            if line.related_id:
                line_vals["related_id"] = "%s,%d" % (line.related_id._model, line.related_id.id)
            if obj.type == "in":
                line_vals["cost_price_cur"] = line.cost_price_cur
                line_vals["cost_price"] = line.cost_price
                line_vals["cost_amount"] = line.cost_amount
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, {"pick_type": vals["type"]})
        if state in ("planned","approved"):
            self.pending([new_id])
        if state=="approved":
            self.approve([new_id])
        new_obj = self.browse(new_id)
        if obj.type == "in":
            return {
                "next": {
                    "name": "pick_in",
                    "mode": "form",
                    "active_id": new_id,
                },
                "flash": "Goods receipt %s copied to %s" % (obj.number, new_obj.number),
            }
        elif obj.type == "internal":
            return {
                "next": {
                    "name": "pick_internal",
                    "mode": "form",
                    "active_id": new_id,
                },
                "flash": "Goods transfer %s copied to %s" % (obj.number, new_obj.number),
            }
        elif obj.type == "out":
            return {
                "next": {
                    "name": "pick_out",
                    "mode": "form",
                    "active_id": new_id,
                },
                "flash": "Goods issue %s copied to %s" % (obj.number, new_obj.number),
            }

    def wkf_copy(self, context={}, **kw): # XXX
        print("#"*80)
        print("picking.wkf_copy")
        trigger_ids=context.get("trigger_ids")
        if not trigger_ids:
            raise Exception("Missing trigger ids")
        print("trigger_ids",trigger_ids)
        self.copy(trigger_ids,context=context,**kw)

    def copy_to_receipt(self, ids, context={}):
        obj = self.browse(ids)[0]
        vals = {
            "type": "in",
            "contact_id": obj.contact_id.id,
            "ref": obj.ref,
            "lines": [],
        }
        if obj.related_id:
            vals["related_id"] = "%s,%d" % (obj.related_id._model, obj.related_id.id)

        #in case goods issue copy it's reference
        else:
            vals["related_id"] = "%s,%d" % ("stock.picking", obj.id)

        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "location_from_id": line.location_to_id.id,
                "location_to_id": line.location_from_id.id,

                # try copy cost
                "cost_price": line.cost_price,
                "cost_price_cur": line.cost_price,
                "cost_amount": line.cost_price * line.qty, # why we have to compute like this
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, {"pick_type": "in"})
        new_obj = self.browse(new_id)
        return {
            "next": {
                "name": "pick_in",
                "mode": "form",
                "active_id": new_id,
            },
            "flash": "Goods receipt %s copied to %s" % (obj.number, new_obj.number),
        }

    def view_picking(self, ids, context={}):
        obj = self.browse(ids[0])
        if obj.type == "out":
            action = "pick_out"
        elif obj.type == "in":
            action = "pick_in"
        elif obj.type == "internal":
            action = "pick_internal"
        return {
            "next": {
                "name": action,
                "mode": "form",
                "active_id": obj.id,
            }
        }

    def search_product(self, clause, context={}):
        op = clause[1]
        val = clause[2]
        return ["lines.product_id.name", op, val]

    def search_product2(self, clause, context={}): #XXX ICC
        product_id = clause[2]
        product = get_model("product").browse(product_id)
        product_ids = [product_id]
        for var in product.variants:
            product_ids.append(var.id)
        for comp in product.components:
            product_ids.append(comp.component_id.id)
        picking_ids = []
        for line in get_model("stock.move").search_browse([["product_id","in",product_ids]]):
            picking_ids.append(line.picking_id.id)
        cond = [["id","in",picking_ids]]
        return cond

    def write(self, ids, vals, **kw):
        super().write(ids, vals, **kw)
        if "date" in vals:
            date = vals["date"]
            move_ids = get_model("stock.move").search([["picking_id", "in", ids]])
            get_model("stock.move").write(move_ids, {"date": date})
        #update service order cost
        job_ids=[]
        for obj in self.browse(ids):
            if obj.related_id._model == 'job':
                job_ids.append(obj.related_id.id)
        if job_ids:
            get_model('job').function_store(job_ids)

    def get_qty_total(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            qty = sum([line.qty for line in obj.lines])
            res[obj.id] = qty or 0
        return res

    def add_container(self, ids, context={}):
        obj = self.browse(ids)[0]
        return {
            "next": {
                "name": "add_container",
                "defaults": {
                    "picking_id": obj.id,
                }
            }
        }

    def onchange_container(self, context={}):
        data = context["data"]
        cont_id = data.get("container_id")
        if not cont_id:
            return
        cont = get_model("stock.container").browse(cont_id)
        contents = cont.get_contents()
        lines = []
        for (prod_id, lot_id, loc_id), (qty, amt, qty2) in contents.items():
            prod = get_model("product").browse(prod_id)
            line_vals = {
                "product_id": prod_id,
                "qty": qty,
                "uom_id": prod.uom_id.id,
                "qty2": qty2,
                "location_from_id": loc_id,
                "location_to_id": None,
                "lot_id": lot_id,
                "container_from_id": cont_id,
            }
            if data["type"] == "internal":
                line_vals["container_to_id"] = cont_id
            lines.append(line_vals)
        data["lines"] = lines
        return data

    def create_bundle_pickings(self, ids, context={}):
        for obj in self.browse(ids):
            pick_vals = {
                "type": obj.type,
                "journal_id": obj.journal_id.id,
                "date": obj.date,
                "contact_id": obj.contact_id.id,
                "ship_address_id": obj.ship_address_id.id,
                "ref": obj.ref,
                "related_id": "stock.picking,%d" % obj.id,
                "lines": [],
            }
            for move in obj.lines:
                prod = move.product_id
                if prod.type != "bundle":
                    continue
                res = get_model("bom").search([["product_id", "=", prod.id]])
                if not res:
                    raise Exception("BoM not found for bundle product %s" % prod.code)
                bom_id = res[0]
                bom = get_model("bom").browse(bom_id)
                qty = get_model("uom").convert(move.qty, move.uom_id.id, bom.uom_id.id)
                ratio = qty / bom.qty
                for comp in bom.lines:
                    line_vals = {
                        "product_id": comp.product_id.id,
                        "qty": comp.qty * ratio,
                        "uom_id": comp.uom_id.id,
                        "location_from_id": move.location_from_id.id,
                        "location_to_id": move.location_to_id.id,
                        "lot_id": move.lot_id.id,
                        "packaging_id": move.packaging_id.id,
                        "num_packages": move.num_packages,
                        "notes": move.notes,
                    }
                    pick_vals["lines"].append(("create", line_vals))
            if pick_vals["lines"]:
                pick_id = get_model("stock.picking").create(pick_vals, context={"pick_type": obj.type})
                get_model("stock.picking").set_done([pick_id])

    def approve_done(self, ids, context={}):
        obj = self.browse(ids)[0]
        user_id = get_active_user()
        obj.write({"done_approved_by_id": user_id})

    def view_journal_entry(self,ids,context={}):
        obj=self.browse(ids)[0]
        move_id=None
        for line in obj.lines:
            if line.move_id:
                if move_id is None:
                    move_id=line.move_id.id
                else:
                    if line.move_id.id!=move_id:
                        raise Exception("Stock movements have different journal entries")
        if not move_id:
            raise Exception("Journal entry not found")
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": move_id,
            }
        }

    def copy_to_landed(self, ids, context={}):
        vals={
            "cost_allocs": [],
        }
        for obj in self.browse(ids):
            for line in obj.lines:
                prod=line.product_id
                alloc_vals={
                    "move_id": line.id,
                    "est_ship": line.qty*(line.cost_price_cur or 0)*(prod.purchase_ship_percent or 0)/100,
                    "est_duty": line.qty*(line.cost_price_cur or 0)*(prod.purchase_duty_percent or 0)/100,
                }
                vals["cost_allocs"].append(("create",alloc_vals))
        landed_id=get_model("landed.cost").create(vals)
        return {
            "next": {
                "name": "landed_cost",
                "mode": "form",
                "active_id": landed_id,
            },
            "flash": "Landed costs copied from goods receipt",
        }

    def get_landed_costs(self, ids, context={}):
        vals={}
        for obj in self.browse(ids):
            landed_ids=[]
            for move in obj.lines:
                for alloc in move.alloc_costs:
                    landed_ids.append(alloc.landed_id.id)
            landed_ids=list(set(landed_ids))
            vals[obj.id]=landed_ids
        return vals

    def assign_lots(self,ids,context={}):
        print("assign_lots",ids)
        obj=self.browse(ids[0])
        delete_ids=[]
        for line in obj.lines:
            prod=line.product_id
            if prod.lot_id:
                continue
            lot_avail_qtys={}
            for bal in get_model("stock.balance").search_browse([["product_id","=",prod.id],["location_id","=",line.location_from_id.id]]):
                lot_id=bal.lot_id.id
                if not lot_id:
                    continue
                lot_avail_qtys.setdefault(lot_id,0)
                lot_avail_qtys[lot_id]+=bal.qty_virt
            print("lot_avail_qtys",lot_avail_qtys)
            if not lot_avail_qtys:
                continue
            lot_ids=lot_avail_qtys.keys()
            lots=[lot for lot in get_model("stock.lot").browse(lot_ids)]
            if prod.lot_select=="fifo":
                lots.sort(key=lambda l: l.received_date)
            elif prod.lot_select=="fefo":
                lots.sort(key=lambda l: l.expiry_date)
            remain_qty=line.qty
            lot_use_qtys={}
            for lot in lots:
                avail_qty=lot_avail_qtys[lot.id]
                use_qty=min(avail_qty,remain_qty) # XXX: uom
                lot_use_qtys[lot.id]=use_qty
                remain_qty-=use_qty
                if remain_qty<=0:
                    break
            print("lot_use_qtys",lot_use_qtys)
            if remain_qty:
                line.write({"qty":remain_qty})
            else:
                delete_ids.append(line.id)
            for lot_id,use_qty in lot_use_qtys.items():
                vals={
                    "picking_id": line.picking_id.id,
                    "product_id": line.product_id.id,
                    "qty": use_qty,
                    "uom_id": line.uom_id.id,
                    "location_from_id": line.location_from_id.id,
                    "location_to_id": line.location_to_id.id,
                    "lot_id": lot_id,
                    "track_id": line.track_id.id,
                }
                rel=line.related_id
                if rel:
                    vals["related_id"]="%s,%s"%(rel._model,rel.id)
                get_model("stock.move").create(vals)
        if delete_ids:
            get_model("stock.move").delete(delete_ids)

    def wkf_check_location(self,ids,from_location=None,to_location=None,context={}):
        print("#"*80)
        print("picking.check_location",ids,from_location,to_location)
        obj=self.browse(ids[0])
        if from_location:
            res=get_model("stock.location").search([["code","=",from_location]])
            if not res:
                raise Exception("Location code not found: %s"%from_location)
            from_loc_id=res[0]
        else:
            from_loc_id=None
        if to_location:
            res=get_model("stock.location").search([["code","=",to_location]])
            if not res:
                raise Exception("Location code not found: %s"%to_location)
            to_loc_id=res[0]
        else:
            to_loc_id=None
        for line in obj.lines:
            if from_loc_id and line.location_from_id.id!=from_loc_id:
                return []
            if to_loc_id and line.location_to_id.id!=to_loc_id:
                return []
        return ids

    def set_currency_rate(self,ids,context={}):
        obj=self.browse(ids[0])
        settings=get_model("settings").browse(1)
        if obj.currency_rate:
            currency_rate = obj.currency_rate
        else:
            if not obj.currency_id:
                raise Exception("Missing picking currency")
            if obj.currency_id.id == settings.currency_id.id:
                currency_rate = 1
            else:
                rate_from = obj.currency_id.get_rate(date=obj.date)
                if not rate_from:
                    raise Exception("Missing currency rate for %s" % obj.currency_id.code)
                if not settings.currency_id:
                    raise Exception("Missing company currency")
                rate_to = settings.currency_id.get_rate(date=obj.date)
                if not rate_to:
                    raise Exception("Missing currency rate for %s" % settings.currency_id.code)
                currency_rate = rate_from / rate_to
        obj.write({"currency_rate":currency_rate})

    def update_line_cost_price(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        qty=line["qty"] or 0
        pick_type=data.get('type')
        cost_price_cur=0
        currency_rate=0
        currency_id=None
        if pick_type=='in':
            cost_price_cur=line.get("cost_price_cur") or 0
            currency_id=data["currency_id"]
            if not currency_id:
                raise Exception("Missing currency")
            currency=get_model("currency").browse(currency_id)
            currency_rate=data["currency_rate"]
        date=data["date"]
        settings=get_model("settings").browse(1)
        if not currency_rate:
            currency=settings.currency_id
            if currency_id == settings.currency_id.id:
                currency_rate = 1
            else:
                rate_from = currency.get_rate(date=date)
                if not rate_from:
                    raise Exception("Missing currency rate for %s" % currency.code)
                rate_to = settings.currency_id.get_rate(date=date)
                if not rate_to:
                    raise Exception("Missing currency rate for %s" % settings.currency_id.code)
                currency_rate = rate_from / rate_to
        cost_price=get_model("currency").convert(cost_price_cur,currency_id,settings.currency_id.id,rate=currency_rate)
        cost_amount=cost_price*qty
        line["cost_price"]=cost_price
        line["cost_amount"]=cost_amount
        return data

    def update_cost_price(self,context={}):
        data=context['data']

        currency_rate=data.get('currency_rate',1)
        settings=get_model("settings").browse(1)
        currency_id = data.get("currency_id",settings.currency_id.id)

        for line in data['lines']:
            cost_price_cur=line.get("cost_price_cur") or 0
            cost_price=get_model("currency").convert(cost_price_cur,currency_id,settings.currency_id.id,rate=currency_rate)
            cost_amount=cost_price*(line['qty'] or 0)
            line["cost_price"]=cost_price
            line["cost_amount"]=cost_amount
        return data

    def onchange_currency(self,context={}):
        data=context['data']
        currency_rate=get_model("currency").get_rate([data['currency_id']],date=data['date'],rate_type='buy',context=context) or 1
        data['currency_rate']=currency_rate
        data=self.update_cost_price(context)
        return data

    def onchange_rate(self,context={}):
        data=context['data']
        data=self.update_cost_price(context)
        return data

Picking.register()
