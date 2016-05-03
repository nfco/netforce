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
import time
from decimal import Decimal
from netforce import config
from netforce import database
from pprint import pprint
from netforce.access import get_active_company, set_active_user, set_active_company
from netforce.utils import get_file_path


class Invoice(Model):
    _name = "account.invoice"
    _string = "Invoice"
    _audit_log = True
    _key = ["company_id", "number"]
    _name_field = "number"
    _multi_company = True
    _fields = {
        "type": fields.Selection([["out", "Receivable"], ["in", "Payable"]], "Type", required=True),
        "inv_type": fields.Selection([["invoice", "Invoice"], ["credit", "Credit Note"], ["debit", "Debit Note"], ["prepay", "Prepayment"], ["overpay", "Overpayment"]], "Subtype", required=True, search=True),
        "number": fields.Char("Number", search=True),
        "ref": fields.Char("Ref", size=256, search=True),
        "memo": fields.Char("Memo", size=1024, search=True),
        "contact_id": fields.Many2One("contact", "Contact", required=True, search=True),
        "contact_credit": fields.Decimal("Outstanding Credit", function="get_contact_credit"),
        "account_id": fields.Many2One("account.account", "Account"),
        "date": fields.Date("Date", required=True, search=True),
        "due_date": fields.Date("Due Date", search=True),
        "currency_id": fields.Many2One("currency", "Currency", required=True, search=True),
        "tax_type": fields.Selection([["tax_ex", "Tax Exclusive"], ["tax_in", "Tax Inclusive"], ["no_tax", "No Tax"]], "Tax Type", required=True),
        "state": fields.Selection([("draft", "Draft"), ("waiting_approval", "Waiting Approval"), ("waiting_payment", "Waiting Payment"), ("paid", "Paid"), ("voided", "Voided")], "Status", function="get_state", store=True, function_order=20, search=True),
        "lines": fields.One2Many("account.invoice.line", "invoice_id", "Lines"),
        "amount_subtotal": fields.Decimal("Subtotal", function="get_amount", function_multi=True, store=True),
        "amount_tax": fields.Decimal("Tax Amount", function="get_amount", function_multi=True, store=True),
        "amount_total": fields.Decimal("Total", function="get_amount", function_multi=True, store=True),
        "amount_paid": fields.Decimal("Paid Amount", function="get_amount", function_multi=True, store=True),
        "amount_due": fields.Decimal("Due Amount", function="get_amount", function_multi=True, store=True),
        "amount_credit_total": fields.Decimal("Total Credit", function="get_amount", function_multi=True, store=True),
        "amount_credit_remain": fields.Decimal("Remaining Credit", function="get_amount", function_multi=True, store=True),
        "amount_total_cur": fields.Decimal("Total Amount", function="get_amount", function_multi=True, store=True),
        "amount_due_cur": fields.Decimal("Due Amount", function="get_amount", function_multi=True, store=True),
        "amount_paid_cur": fields.Decimal("Paid Amount", function="get_amount", function_multi=True, store=True),
        "amount_credit_remain_cur": fields.Decimal("Remaining Credit", function="get_amount", function_multi=True, store=True),
        "amount_rounding": fields.Decimal("Rounding", function="get_amount", function_multi=True, store=True),
        "qty_total": fields.Decimal("Total Quantity", function="get_qty_total"),
        "attachment": fields.File("Attachment"),
        "payments": fields.One2Many("account.payment.line", "invoice_id", "Payments", condition=[["payment_id.state", "=", "posted"]]),
        "move_id": fields.Many2One("account.move", "Journal Entry"),
        "reconcile_move_line_id": fields.Many2One("account.move.line", "Reconcile Item"),
        "credit_alloc": fields.One2Many("account.credit.alloc", "credit_id", "Credit Allocation"),
        "credit_notes": fields.One2Many("account.credit.alloc", "invoice_id", "Credit Notes"),
        "currency_rate": fields.Decimal("Currency Rate", scale=6),
        "payment_id": fields.Many2One("account.payment", "Payment"),
        "related_id": fields.Reference([["sale.order", "Sales Order"], ["purchase.order", "Purchase Order"], ["production.order","Production Order"], ["project", "Project"], ["job", "Service Order"], ["service.contract", "Service Contract"]], "Related To"),
        "company_id": fields.Many2One("company", "Company"),
        "amount_discount": fields.Decimal("Discount", function="get_discount"),
        "bill_address_id": fields.Many2One("address", "Billing Address"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "documents": fields.One2Many("document", "related_id", "Documents"),
        "fixed_assets": fields.One2Many("account.fixed.asset", "invoice_id", "Fixed Assets"),
        "tax_no": fields.Char("Tax No."),
        "tax_branch_no": fields.Char("Tax Branch No."),
        "pay_method_id": fields.Many2One("payment.method", "Payment Method"),
        "journal_id": fields.Many2One("account.journal", "Journal"),
        "sequence_id": fields.Many2One("sequence", "Sequence"),
        "original_invoice_id": fields.Many2One("account.invoice", "Original Invoice"),
        "product_id": fields.Many2One("product","Product",store=False,function_search="search_product",search=True),
        "taxes": fields.One2Many("account.invoice.tax","invoice_id","Taxes"),
        "agg_amount_total": fields.Decimal("Total Amount", agg_function=["sum", "amount_total"]),
        "agg_amount_subtotal": fields.Decimal("Total Amount w/o Tax", agg_function=["sum", "amount_subtotal"]),
        "year": fields.Char("Year", sql_function=["year", "date"]),
        "quarter": fields.Char("Quarter", sql_function=["quarter", "date"]),
        "month": fields.Char("Month", sql_function=["month", "date"]),
        "week": fields.Char("Week", sql_function=["week", "date"]),
    }
    _order = "date desc,number desc"

    def _get_currency(self, context={}):
        settings = get_model("settings").browse(1)
        return settings.currency_id.id

    def _get_number(self, context={}):
        defaults = context.get("defaults")
        if defaults:  # XXX
            type = defaults.get("type")
            inv_type = defaults.get("inv_type")
        else:
            type = context.get("type")
            inv_type = context.get("inv_type")
        seq_id = context.get("sequence_id")
        if not seq_id:
            seq_type = None
            if type == "out":
                if inv_type in ("invoice", "prepay"):
                    seq_type = "cust_invoice"
                elif inv_type == "credit":
                    seq_type = "cust_credit"
                elif inv_type == "debit":
                    seq_type = "cust_debit"
            elif type == "in":
                if inv_type in ("invoice", "prepay"):
                    seq_type = "supp_invoice"
                elif inv_type == "credit":
                    seq_type = "supp_credit"
                elif inv_type == "debit":
                    seq_type = "supp_debit"
            if not seq_type:
                return
            seq_id = get_model("sequence").find_sequence(type=seq_type)
            if not seq_id:
                return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["number", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    _defaults = {
        "state": "draft",
        "currency_id": _get_currency,
        "tax_type": "tax_ex",
        "number": _get_number,
        "date": lambda *a: time.strftime("%Y-%m-%d"),
        "company_id": lambda *a: get_active_company(),
    }
    _constraints = ["check_fields"]

    def search_product(self, clause, context={}):
        product_id = clause[2]
        product = get_model("product").browse(product_id)
        product_ids = [product_id]
        for var in product.variants:
            product_ids.append(var.id)
        for comp in product.components:
            product_ids.append(comp.component_id.id)
        invoice_ids = []
        for line in get_model("account.invoice.line").search_browse([["product_id","in",product_ids]]):
            invoice_ids.append(line.invoice_id.id)
        cond = [["id","in",invoice_ids]]
        return cond

    def check_fields(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state in ("waiting_approval", "waiting_payment"):
                if obj.inv_type == "invoice":
                    if not obj.due_date:
                        raise Exception("Missing due date")
                # if not obj.lines: # XXX: in myob, lines can be empty...
                #    raise Exception("Lines are empty")

    def name_get(self, ids, context={}):
        vals = []
        for obj in self.browse(ids):
            name = obj.number
            if not name:
                if obj.inv_type == "invoice":
                    name = "Invoice"
                elif obj.inv_type == "credit":
                    name = "Credit Note"
                elif obj.inv_type == "prepay":
                    name = "Prepayment"
                elif obj.inv_type == "overpay":
                    name = "Overpayment"
            if obj.ref:
                name += " [%s]" % obj.ref
            if obj.tax_no:
                name+=", "+obj.tax_no
            vals.append((obj.id, name))
        return vals

    def create(self, vals, context={}):
        id = super(Invoice, self).create(vals, context=context)
        self.function_store([id])
        return id

    def write(self, ids, vals, **kw):
        super(Invoice, self).write(ids, vals, **kw)
        self.function_store(ids)
        sale_ids = []
        purch_ids = []
        for inv in self.browse(ids):
            for line in inv.lines:
                if line.sale_id:
                    sale_ids.append(line.sale_id.id)
                if line.purch_id:
                    purch_ids.append(line.purch_id.id)
        if sale_ids:
            get_model("sale.order").function_store(sale_ids)
        if purch_ids:
            get_model("purchase.order").function_store(purch_ids)

    def delete(self, ids, context={}):
        sale_ids = []
        purch_ids = []
        for inv in self.browse(ids):
            if inv.inv_type == "prepay" and inv.type == "out" and "can_delete" not in context:
                raise Exception("Can't delete invoice with Prepayment. Please delete by using To Draft option in payment.")
            if inv.inv_type not in ("prepay", "overpay"):
                if inv.state not in ("draft", "waiting_approval", "voided"):
                    raise Exception("Can't delete invoice with this status")
            for line in inv.lines:
                if line.sale_id:
                    sale_ids.append(line.sale_id.id)
                if line.purch_id:
                    purch_ids.append(line.purch_id.id)
        super(Invoice, self).delete(ids, context=context)
        if sale_ids:
            get_model("sale.order").function_store(sale_ids)
        if purch_ids:
            get_model("purchase.order").function_store(purch_ids)

    def function_store(self, ids, field_names=None, context={}):
        super().function_store(ids, field_names, context)
        sale_ids = []
        purch_ids = []
        for obj in self.browse(ids):
            for line in obj.lines:
                if line.sale_id:
                    sale_ids.append(line.sale_id.id)
                if line.purch_id:
                    purch_ids.append(line.purch_id.id)
        if sale_ids:
            get_model("sale.order").function_store(sale_ids)
        if purch_ids:
            get_model("purchase.order").function_store(purch_ids)

    def submit_for_approval(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.state != "draft":
                raise Exception("Invalid state")
            obj.write({"state": "waiting_approval"})
        self.trigger(ids, "submit_for_approval")
        return {
            "flash": "Invoice submitted for approval."
        }

    def approve(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state not in ("draft", "waiting_approval"):
            raise Exception("Invalid state")
        obj.post()
        if obj.inv_type == "invoice":
            msg = "Invoice approved."
            if obj.type == "in":
                obj.create_fixed_assets()
        elif obj.inv_type == "credit":
            msg = "Credit note approved."
        elif obj.inv_type == "debit":
            msg = "Debit note approved."
        return {
            "flash": msg,
        }

    def calc_taxes(self,ids,context={}):
        obj=self.browse(ids[0])
        obj.taxes.delete()
        settings = get_model("settings").browse(1)
        if obj.currency_rate:
            currency_rate = obj.currency_rate
        else:
            if obj.currency_id.id == settings.currency_id.id:
                currency_rate = 1
            else:
                rate_type=obj.type=="out" and "sell" or "buy"
                rate_from = obj.currency_id.get_rate(date=obj.date,rate_type=rate_type)
                if not rate_from:
                    raise Exception("Missing currency rate for %s" % obj.currency_id.code)
                if not settings.currency_id:
                    raise Exception("Missing default currency in Financial Settings")
                rate_to = settings.currency_id.get_rate(date=obj.date)
                if not rate_to:
                    raise Exception("Missing currency rate for %s" % settings.currency_id.code)
                currency_rate = rate_from / rate_to
            obj.write({"currency_rate": currency_rate})
        taxes = {}
        tax_nos = []
        total_amt = 0
        total_base = 0
        total_tax = 0
        for line in obj.lines:
            cur_amt = get_model("currency").convert(
                line.amount, obj.currency_id.id, settings.currency_id.id, rate=currency_rate)
            tax_id = line.tax_id
            if tax_id and obj.tax_type != "no_tax":
                base_amt = get_model("account.tax.rate").compute_base(tax_id, cur_amt, tax_type=obj.tax_type)
                if settings.rounding_account_id:
                    base_amt=get_model("currency").round(obj.currency_id.id,base_amt)
                tax_comps = get_model("account.tax.rate").compute_taxes(tax_id, base_amt, when="invoice")
                for comp_id, tax_amt in tax_comps.items():
                    tax_vals = taxes.setdefault(comp_id, {"tax_amt": 0, "base_amt": 0})
                    tax_vals["tax_amt"] += tax_amt
                    tax_vals["base_amt"] += base_amt
            else:
                base_amt = cur_amt
        for comp_id, tax_vals in taxes.items():
            comp = get_model("account.tax.component").browse(comp_id)
            acc_id = comp.account_id.id
            if not acc_id:
                raise Exception("Missing account for tax component %s" % comp.name)
            vals = {
                "invoice_id": obj.id,
                "tax_comp_id": comp_id,
                "base_amount": get_model("currency").round(obj.currency_id.id,tax_vals["base_amt"]),
                "tax_amount": get_model("currency").round(obj.currency_id.id,tax_vals["tax_amt"]),
            }
            if comp.type in ("vat", "vat_exempt"):
                if obj.type == "out":
                    if obj.tax_no:
                        tax_no = obj.tax_no
                    else:
                        tax_no = self.gen_tax_no(exclude=tax_nos, context={"date": obj.date})
                        tax_nos.append(tax_no)
                        obj.write({"tax_no": tax_no})
                    vals["tax_no"] = tax_no
                elif obj.type == "in":
                    vals["tax_no"] = obj.tax_no
            get_model("account.invoice.tax").create(vals)

    def post(self, ids, context={}):
        t0 = time.time()
        settings = get_model("settings").browse(1)
        for obj in self.browse(ids):
            obj.check_related()
            if obj.amount_total == 0:
                raise Exception("Invoice total is zero")
            if obj.amount_total < 0:
                raise Exception("Invoice total is negative")
            if not obj.taxes:
                obj.calc_taxes()
                obj=obj.browse()[0]
            contact = obj.contact_id
            if obj.type == "out":
                account_id = contact.account_receivable_id.id or settings.account_receivable_id.id
                if not account_id:
                    raise Exception("Account receivable not found")
            elif obj.type == "in":
                account_id = contact.account_payable_id.id or settings.account_payable_id.id
                if not account_id:
                    raise Exception("Account payable not found")
            sign = obj.type == "out" and 1 or -1
            if obj.inv_type == "credit":
                sign *= -1
            obj.write({"account_id": account_id})
            if obj.type == "out":
                desc = "Sale; " + contact.name
            elif obj.type == "in":
                desc = "Purchase; " + contact.name
            if obj.type == "out":
                journal_id = obj.journal_id.id or settings.sale_journal_id.id
                if not journal_id:
                    raise Exception("Sales journal not found")
            elif obj.type == "in":
                journal_id = obj.journal_id.id or settings.purchase_journal_id.id
                if not journal_id:
                    raise Exception("Purchases journal not found")
            if obj.currency_rate:
                currency_rate = obj.currency_rate
            else:
                if obj.currency_id.id == settings.currency_id.id:
                    currency_rate = 1
                else:
                    rate_type=obj.type=="out" and "sell" or "buy"
                    rate_from = obj.currency_id.get_rate(date=obj.date,rate_type=rate_type)
                    if not rate_from:
                        raise Exception("Missing currency rate for %s" % obj.currency_id.code)
                    rate_to = settings.currency_id.get_rate(date=obj.date)
                    if not rate_to:
                        raise Exception("Missing currency rate for %s" % settings.currency_id.code)
                    currency_rate = rate_from / rate_to
                obj.write({"currency_rate": currency_rate})
            move_vals = {
                "journal_id": journal_id,
                "number": obj.number,
                "date": obj.date,
                "ref": obj.ref,
                "narration": desc,
                "related_id": "account.invoice,%s" % obj.id,
                "company_id": obj.company_id.id,
            }
            lines = []
            t01 = time.time()
            for line in obj.lines:
                cur_amt = get_model("currency").convert(
                    line.amount, obj.currency_id.id, settings.currency_id.id, rate=currency_rate)
                tax_id = line.tax_id
                if tax_id and obj.tax_type != "no_tax":
                    base_amt = get_model("account.tax.rate").compute_base(tax_id, cur_amt, tax_type=obj.tax_type)
                else:
                    base_amt = cur_amt
                acc_id = line.account_id.id
                if not acc_id:
                    raise Exception("Missing line account for invoice line '%s'" % line.description)
                amt = base_amt * sign
                line_vals = {
                    "description": line.description,
                    "account_id": acc_id,
                    "credit": amt > 0 and amt or 0,
                    "debit": amt < 0 and -amt or 0,
                    "track_id": line.track_id.id,
                    "track2_id": line.track2_id.id,
                    "contact_id": contact.id,
                }
                lines.append(line_vals)
            for tax in obj.taxes:
                comp = tax.tax_comp_id
                acc_id = comp.account_id.id
                if not acc_id:
                    raise Exception("Missing account for tax component %s" % comp.name)
                amt = sign * tax.tax_amount
                line_vals = {
                    "description": desc,
                    "account_id": acc_id,
                    "credit": amt > 0 and amt or 0,
                    "debit": amt < 0 and -amt or 0,
                    "tax_comp_id": comp.id,
                    "tax_base": tax.base_amount,
                    "contact_id": contact.id,
                    "invoice_id": obj.id,
                    "tax_no": tax.tax_no,
                }
                lines.append(line_vals)
            t02 = time.time()
            dt01 = (t02 - t01) * 1000
            print("post dt01", dt01)
            groups = {}
            keys = ["description", "account_id", "track_id", "tax_comp_id", "contact_id", "invoice_id", "reconcile_id"]
            for line in lines:
                key_val = tuple(line.get(k) for k in keys)
                if key_val in groups:
                    group = groups[key_val]
                    group["debit"] += line["debit"]
                    group["credit"] += line["credit"]
                    if line.get("tax_base"):
                        if "tax_base" not in group:
                            group["tax_base"] = 0
                        group["tax_base"] += line["tax_base"]
                else:
                    groups[key_val] = line.copy()
            group_lines = sorted(groups.values(), key=lambda l: (l["debit"], l["credit"]))
            for line in group_lines:
                amt = line["debit"] - line["credit"]
                amt = get_model("currency").round(obj.currency_id.id,amt)
                if amt >= 0:
                    line["debit"] = amt
                    line["credit"] = 0
                else:
                    line["debit"] = 0
                    line["credit"] = -amt
            amt = 0
            for line in group_lines:
                amt -= line["debit"] - line["credit"]
            line_vals = {
                "description": desc,
                "account_id": account_id,
                "debit": amt > 0 and amt or 0,
                "credit": amt < 0 and -amt or 0,
                "due_date": obj.due_date,
                "contact_id": contact.id,
            }
            acc = get_model("account.account").browse(account_id)
            if acc.currency_id.id != settings.currency_id.id:
                if acc.currency_id.id != obj.currency_id.id:
                    raise Exception("Invalid account currency for this invoice: %s" % acc.code)
                line_vals["amount_cur"] = obj.amount_total * sign
            move_vals["lines"] = [("create", line_vals)]
            move_vals["lines"] += [("create", vals) for vals in group_lines]
            t03 = time.time()
            dt02 = (t03 - t02) * 1000
            print("post dt02", dt02)
            move_id = get_model("account.move").create(move_vals)
            t04 = time.time()
            dt03 = (t04 - t03) * 1000
            print("post dt03", dt03)
            get_model("account.move").post([move_id])
            t05 = time.time()
            dt04 = (t05 - t04) * 1000
            print("post dt04", dt04)
            obj.write({"move_id": move_id, "state": "waiting_payment"})
            t06 = time.time()
            dt05 = (t06 - t05) * 1000
            print("post dt05", dt05)
        t1 = time.time()
        dt = (t1 - t0) * 1000
        print("invoice.post <<< %d ms" % dt)

    def repost_invoices(self, context={}):  # XXX
        ids = self.search([["state", "in", ("waiting_payment", "paid")]], order="date")
        for obj in self.browse(ids):
            print("invoice %d..." % obj.id)
            if not obj.move_id:
                raise Exception("No journal entry for invoice #%d" % obj.id)
            obj.move_id.delete()
            obj.post()

    def void(self, ids, context={}):
        print("invoice.void", ids)
        obj = self.browse(ids)[0]
        if obj.state not in ("draft", "waiting_payment"):
            raise Exception("Invalid invoice state")
        if obj.payments:
            raise Exception("Can't void invoice because there are related payments")
        if obj.credit_alloc:
            raise Exception("Can't void invoice because there are credit allocations")
        if obj.credit_notes:
            raise Exception("Can't void invoice because there are linked credit notes")
        if obj.move_id:
            obj.move_id.void()
            obj.move_id.delete()
        obj.write({"state": "voided"})

    def to_draft(self, ids, context={}):
        obj = self.browse(ids)[0]
        if obj.state != "waiting_payment":
            raise Exception("Invalid status")
        if obj.credit_notes:
            raise Exception("There are still payment entries for this invoice")
        if obj.move_id:
            obj.move_id.void()
            obj.move_id.delete()
        obj.taxes.delete()
        obj.write({"state": "draft"})

    def get_amount(self, ids, context={}):
        t0 = time.time()
        settings = get_model("settings").browse(1)
        res = {}
        for inv in self.browse(ids):
            vals = {}
            subtotal = 0
            tax = 0
            for line in inv.lines:
                tax_id = line.tax_id
                if tax_id and inv.tax_type != "no_tax":
                    base_amt = get_model("account.tax.rate").compute_base(tax_id, line.amount, tax_type=inv.tax_type)
                    tax_comps = get_model("account.tax.rate").compute_taxes(tax_id, base_amt, when="invoice")
                    for comp_id, tax_amt in tax_comps.items():
                        tax += tax_amt
                else:
                    base_amt = line.amount
                subtotal += base_amt
            subtotal=get_model("currency").round(inv.currency_id.id,subtotal)
            tax=get_model("currency").round(inv.currency_id.id,tax)
            vals["amount_subtotal"] = subtotal
            if inv.taxes:
                tax=sum(t.tax_amount for t in inv.taxes)
            vals["amount_tax"] = tax
            if inv.tax_type == "tax_in":
                vals["amount_rounding"] = sum(l.amount for l in inv.lines) - (subtotal + tax)
            else:
                vals["amount_rounding"] = 0
            vals["amount_total"] = subtotal + tax + vals["amount_rounding"]
            vals["amount_total_cur"] = get_model("currency").convert(
                vals["amount_total"], inv.currency_id.id, settings.currency_id.id, round=True, rate=inv.currency_rate)
            vals["amount_credit_total"] = vals["amount_total"]
            paid = 0
            for pmt in inv.payments:
                if pmt.payment_id.id == inv.payment_id.id:
                    continue
                if inv.type == pmt.type:
                    paid -= pmt.amount_currency
                else:
                    paid += pmt.amount_currency
            vals["amount_paid"] = paid
            if inv.inv_type in ("invoice", "debit"):
                cred_amt = 0
                for alloc in inv.credit_notes:
                    cred_amt += alloc.amount
                vals["amount_due"] = vals["amount_total"] - paid - cred_amt
                vals["amount_paid"] = paid + cred_amt  # TODO: check this doesn't break anything...
            elif inv.inv_type in ("credit", "prepay", "overpay"):
                cred_amt = 0
                for alloc in inv.credit_alloc:
                    cred_amt += alloc.amount
                for pmt in inv.payments:
                    if pmt.payment_id.type == inv.type:
                        cred_amt += pmt.amount
                    else:
                        cred_amt -= pmt.amount  # XXX: check this
                vals["amount_credit_remain"] = vals["amount_total"] - cred_amt
                vals["amount_due"] = -vals["amount_credit_remain"]
            vals["amount_due_cur"] = get_model("currency").convert(
                vals["amount_due"], inv.currency_id.id, settings.currency_id.id, round=True, rate=inv.currency_rate)
            vals["amount_paid_cur"] = get_model("currency").convert(
                vals["amount_paid"], inv.currency_id.id, settings.currency_id.id, round=True, rate=inv.currency_rate)
            vals["amount_credit_remain_cur"] = get_model("currency").convert(
                vals.get("amount_credit_remain", 0), inv.currency_id.id, settings.currency_id.id, round=True, rate=inv.currency_rate)
            res[inv.id] = vals
        t1 = time.time()
        dt = (t1 - t0) * 1000
        print("invoice.get_amount <<< %d ms" % dt)
        return res

    def get_qty_total(self, ids, context={}):
        res = {}
        for obj in self.browse(ids):
            qty = sum([line.qty or 0 for line in obj.lines])
            res[obj.id] = qty
        return res

    def update_amounts(self, context):
        data = context["data"]
        settings=get_model("settings").browse(1)
        currency_id = data["currency_id"]
        data["amount_subtotal"] = 0
        data["amount_tax"] = 0
        tax_type = data["tax_type"]
        tax_in_total = 0
        for line in data["lines"]:
            if not line:
                continue
            if line.get("unit_price") is not None:
                amt = (line.get("qty") or 0) * (line.get("unit_price") or 0)
                if line.get("discount"):
                    disc = amt * line["discount"] / 100
                    amt -= disc
                if line.get("discount_amount"):
                    amt -= line["discount_amount"]
                line["amount"] = amt
            else:
                amt = line.get("amount") or 0
            tax_id = line.get("tax_id")
            if tax_id and tax_type != "no_tax":
                base_amt = get_model("account.tax.rate").compute_base(tax_id, amt, tax_type=tax_type)
                tax_comps = get_model("account.tax.rate").compute_taxes(tax_id, base_amt, when="invoice")
                for comp_id, tax_amt in tax_comps.items():
                    data["amount_tax"] += tax_amt
            else:
                base_amt = amt
            data["amount_subtotal"] += Decimal(base_amt)
        if tax_type == "tax_in":
            data["amount_rounding"] = sum(
                l.get("amount") or 0 for l in data["lines"] if l) - (data["amount_subtotal"] + data["amount_tax"])
        else:
            data["amount_rounding"] = 0
        data["amount_total"] = data["amount_subtotal"] + data["amount_tax"] + data["amount_rounding"]

        paid = 0
        for pmt in data['payments']:
            if pmt['payment_id'] == data['payment_id']:
                continue
            if data['type'] == pmt['type']:
                paid -= pmt['amount_currency']
            else:
                paid += pmt['amount_currency']
        if data['inv_type'] in ("invoice", "debit"):
            cred_amt = 0
            for alloc in data['credit_notes']:
                cred_amt += alloc['amount']
            data["amount_due"] = data["amount_total"] - paid - cred_amt
            data["amount_paid"] = paid + cred_amt
        elif data['inv_type'] in ("credit", "prepay", "overpay"):
            cred_amt = 0
            for alloc in data['credit_alloc']:
                cred_amt += alloc['amount']
            for pmt in data['payments']:
                payment=get_model("account.payment").browse(pmt['payment_id'])
                if payment.type == data['type']:
                    cred_amt += pmt['amount']
                else:
                    cred_amt -= pmt['amount']
            data["amount_credit_remain"] = data["amount_total"] - cred_amt
            data["amount_due"] = -data["amount_credit_remain"]
        return data

    def onchange_product(self, context):
        data = context["data"]
        type = data["type"]
        path = context["path"]
        contact_id = data["contact_id"]
        contact = get_model("contact").browse(contact_id)
        line = get_data_path(data, path, parent=True)
        prod_id = line.get("product_id")
        if not prod_id:
            return {}
        prod = get_model("product").browse(prod_id)
        line["description"] = prod.description
        line["qty"] = 1
        if prod.uom_id is not None:
            line["uom_id"] = prod.uom_id.id
        if type == "out":
            if prod.sale_price is not None:
                line["unit_price"] = prod.sale_price
            if prod.sale_account_id is not None:
                line["account_id"] = prod.sale_account_id.id
            if prod.sale_tax_id is not None:
                line["tax_id"] = contact.tax_receivable_id.id or prod.sale_tax_id.id
        elif type == "in":
            if prod.purchase_price is not None:
                line["unit_price"] = prod.purchase_price
            if prod.purchase_account_id is not None:
                line["account_id"] = prod.purchase_account_id.id
            if prod.purchase_tax_id is not None:
                line["tax_id"] = contact.tax_payable_id.id or prod.purchase_tax_id.id
        data = self.update_amounts(context)
        return data

    def onchange_account(self, context):
        data = context["data"]
        path = context["path"]
        line = get_data_path(data, path, parent=True)
        acc_id = line.get("account_id")
        if not acc_id:
            return {}
        acc = get_model("account.account").browse(acc_id)
        line["tax_id"] = acc.tax_id.id
        data = self.update_amounts(context)
        return data

    def onchange_contact(self, context):
        data = context["data"]
        contact_id = data.get("contact_id")
        if not contact_id:
            return {}
        contact = get_model("contact").browse(contact_id)
        data["bill_address_id"] = contact.get_address(pref_type="billing")
        if data["type"] == "out":
            data["journal_id"] = contact.sale_journal_id.id
        elif data["type"] == "in":
            data["journal_id"] = contact.purchase_journal_id.id
        self.onchange_journal(context=context)
        if contact.currency_id:
            data["currency_id"] = contact.currency_id.id
        else:
            settings = get_model("settings").browse(1)
            data["currency_id"] = settings.currency_id.id
        return data

    def view_invoice(self, ids, context={}):
        obj = self.browse(ids[0])
        if obj.type == "out":
            action = "cust_invoice"
            if obj.inv_type == "invoice":
                layout = "cust_invoice_form"
            elif obj.inv_type == "credit":
                layout = "cust_credit_form"
            elif obj.inv_type == "debit":
                layout = "cust_debit_form"
            elif obj.inv_type == "prepay":
                layout = "cust_prepay_form"
            elif obj.inv_type == "overpay":
                layout = "cust_overpay_form"
        elif obj.type == "in":
            action = "supp_invoice"
            if obj.inv_type == "invoice":
                layout = "supp_invoice_form"
            elif obj.inv_type == "credit":
                layout = "supp_credit_form"
            elif obj.inv_type == "debit":
                layout = "supp_debit_form"
            elif obj.inv_type == "prepay":
                layout = "supp_prepay_form"
            elif obj.inv_type == "overpay":
                layout = "supp_overpay_form"
        return {
            "next": {
                "name": action,
                "mode": "form",
                "form_view_xml": layout,
                "active_id": obj.id,
            }
        }

    def get_contact_credit(self, ids, context={}):
        obj = self.browse(ids[0])
        amt=0
        vals = {}
        if obj.contact_id:
            contact = get_model("contact").browse(obj.contact_id.id, context={"currency_id": obj.currency_id.id})
            if obj.type == "out":
                amt = contact.receivable_credit
            elif obj.type == "in":
                amt = contact.payable_credit
        vals[obj.id] = amt
        return vals

    def get_state(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            state = obj.state
            if state == "waiting_payment":
                if obj.inv_type in ("invoice", "debit"):
                    if obj.amount_due == 0:
                        state = "paid"
                elif obj.inv_type in ("credit", "prepay", "overpay"):
                    if obj.amount_credit_remain == 0:
                        state = "paid"
            elif state == "paid":
                if obj.inv_type in ("invoice", "debit"):
                    if obj.amount_due > 0:
                        state = "waiting_payment"
                elif obj.inv_type in ("credit", "prepay", "overpay"):
                    if obj.amount_credit_remain > 0:
                        state = "waiting_payment"
            vals[obj.id] = state
        return vals

    def copy(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "type": obj.type,
            "inv_type": obj.inv_type,
            "ref": obj.ref,
            "contact_id": obj.contact_id.id,
            "currency_id": obj.currency_id.id,
            "tax_type": obj.tax_type,
            "memo": obj.memo,
            "lines": [],
        }
        if obj.related_id:
            vals["related_id"] = "%s,%s" % (obj.related_id._model, obj.related_id.id)
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "tax_id": line.tax_id.id,
                "account_id": line.account_id.id,
                "sale_id": line.sale_id.id,
                "purch_id": line.purch_id.id,
                "amount": line.amount,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, context={"type": obj.type, "inv_type": obj.inv_type})
        new_obj = self.browse(new_id)
        if obj.type == "out":
            msg = "Invoice %s copied to %s" % (obj.number, new_obj.number)
        else:
            msg = "Invoice copied"
        return {
            "next": {
                "name": "view_invoice",
                "active_id": new_id,
            },
            "flash": msg,
        }

    def copy_to_credit_note(self, ids, context):
        obj = self.browse(ids)[0]
        vals = {
            "type": obj.type,
            "inv_type": "credit",
            "ref": obj.number,
            "contact_id": obj.contact_id.id,
            "bill_address_id": obj.bill_address_id.id,
            "currency_id": obj.currency_id.id,
            "currency_rate": obj.currency_rate,
            "tax_type": obj.tax_type,
            "memo": obj.memo,
            "tax_no": obj.tax_no,
            "pay_method_id": obj.pay_method_id.id,
            "original_invoice_id": obj.id,
            "lines": [],
        }
        if obj.related_id:
            vals["related_id"] = "%s,%s" % (obj.related_id._model, obj.related_id.id)
        for line in obj.lines:
            line_vals = {
                "product_id": line.product_id.id,
                "description": line.description,
                "qty": line.qty,
                "uom_id": line.uom_id.id,
                "unit_price": line.unit_price,
                "tax_id": line.tax_id.id,
                "account_id": line.account_id.id,
                "sale_id": line.sale_id.id,
                "purch_id": line.purch_id.id,
                "amount": line.amount,
            }
            vals["lines"].append(("create", line_vals))
        new_id = self.create(vals, context={"type": vals["type"], "inv_type": vals["inv_type"]})
        new_obj = self.browse(new_id)
        msg = "Credit note %s created from invoice %s" % (new_obj.number, obj.number)
        return {
            "next": {
                "name": "view_invoice",
                "active_id": new_id,
            },
            "flash": msg,
        }

    def view_journal_entry(self, ids, context={}):
        obj = self.browse(ids)[0]
        return {
            "next": {
                "name": "journal_entry",
                "mode": "form",
                "active_id": obj.move_id.id,
            }
        }

    def gen_tax_no(self, exclude=None, context={}):
        company_id = get_active_company()  # XXX: improve this?
        seq_id = get_model("sequence").find_sequence(type="tax_no")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            if exclude and num in exclude:
                get_model("sequence").increment_number(seq_id, context=context)
                continue
            res = get_model("account.move.line").search([["tax_no", "=", num], ["move_id.company_id", "=", company_id]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    def get_discount(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            amt = 0
            for line in obj.lines:
                amt += line.amount_discount
            vals[obj.id] = amt
        return vals

    def create_fixed_assets(self, ids, context={}):
        for obj in self.browse(ids):
            if obj.fixed_assets:
                raise Exception("Fixed assets already created for invoice %s" % obj.number)
            for line in obj.lines:
                acc = line.account_id
                if acc.type != "fixed_asset":
                    continue
                ass_type = acc.fixed_asset_type_id
                if not ass_type:
                    continue
                vals = {
                    "name": line.description,
                    "type_id": ass_type.id,
                    "date_purchase": obj.date,
                    "price_purchase": line.amount,  # XXX: should be tax-ex
                    "fixed_asset_account_id": acc.id,
                    "dep_rate": ass_type.dep_rate,
                    "dep_method": ass_type.dep_method,
                    "accum_dep_account_id": ass_type.accum_dep_account_id.id,
                    "dep_exp_account_id": ass_type.dep_exp_account_id.id,
                    "invoice_id": obj.id,
                }
                context['date']=obj.date
                get_model("account.fixed.asset").create(vals,context)

    def delete_alloc(self, context={}):
        alloc_id = context["alloc_id"]
        get_model("account.credit.alloc").delete([alloc_id])

    def onchange_date(self, context={}):
        data = context["data"]
        ctx = {
            "type": data["type"],
            "inv_type": data["inv_type"],
            "date": data["date"],
        }
        number = self._get_number(context=ctx)
        data["number"] = number
        return data

    def check_related(self, ids, context={}):
        obj = self.browse(ids)[0]
        rel = obj.related_id
        if not rel:
            return
        # if rel._model=="job": # XXX: doesn't work for bkkbase modules
        #    if not rel.done_approved_by_id:
        #        raise Exception("Service order has to be approved before it is invoiced")

    def get_template_invoice_form(self, ids=None, context={}):
        if ids is None:  # XXX: for backward compat with old templates
            ids = context["ids"]
        obj = get_model("account.invoice").browse(ids)[0]
        if obj.type == "out":
            if obj.amount_discount:
                return "cust_invoice_form_disc"
            else:
                return "cust_invoice_form"
        elif obj.type == "in":
            return "supp_invoice_form"

    def get_report_data(self, ids=None, context={}):  # XXX: deprecated
        print("invoice.get_report_data")
        if ids is not None:  # for new templates
            return super().get_report_data(ids, context=context)
        ids = context["ids"]
        print("ids", ids, type(ids))
        inv_id = ids[0]
        inv = get_model("account.invoice").browse(inv_id)
        dbname = database.get_active_db()
        company = inv.company_id
        settings = get_model("settings").browse(1)
        comp_addr = settings.get_address_str()
        comp_name = company.name
        comp_phone = settings.phone
        comp_fax = settings.fax
        comp_tax_no = settings.tax_no
        contact = inv.contact_id
        cust_addr = contact.get_address_str()
        cust_name = contact.name
        cust_fax = contact.fax
        cust_phone = contact.phone
        cust_tax_no = contact.tax_no
        data = {
            "comp_name": comp_name,
            "comp_addr": comp_addr,
            "comp_phone": comp_phone or "-",
            "comp_fax": comp_fax or "-",
            "comp_tax_no": comp_tax_no or "-",
            "cust_name": cust_name,
            "cust_addr": cust_addr,
            "cust_phone": cust_phone or "-",
            "cust_fax": cust_fax or "-",
            "cust_tax_no": cust_tax_no or "-",
            "date": inv.date or "-",
            "due_date": inv.due_date or "-",
            "number": inv.number or "-",
            "ref": inv.ref or "-",
            "memo": inv.memo or "",
            "lines": [],
        }
        if settings.logo:
            data["logo"] = get_file_path(settings.logo)
        for line in inv.lines:
            data["lines"].append({
                "description": line.description,
                "code": line.product_id.code,
                "qty": line.qty,
                "uom": line.uom_id.name,
                "unit_price": line.unit_price,
                "discount": line.discount,
                "tax_rate": line.tax_id.rate,
                "amount": line.amount,
            })
        is_cash = 'No'
        is_cheque = 'No'
        for obj in inv.payments:
            account_type = obj.payment_id.account_id.type
            if account_type in ("bank", "cash"):
                is_cash = 'Yes'
            if account_type in ("cheque"):
                is_cheque = 'Yes'
        data.update({
            "amount_subtotal": inv.amount_subtotal,
            "amount_discount": inv.amount_discount,
            "amount_tax": inv.amount_tax,
            "amount_total": inv.amount_total,
            "amount_paid": inv.amount_paid,
            "payment_terms": inv.related_id.payment_terms or "-",
            "is_cash": is_cash,
            "is_cheque": is_cheque,
            "currency_code": inv.currency_id.code,
            "tax_rate": get_model("currency").round(inv.currency_id.id,inv.amount_tax * 100 / inv.amount_subtotal) if inv.amount_subtotal else 0,
            "qty_total": inv.qty_total,
            "memo": inv.memo,
        })
        if inv.credit_alloc:
            data.update({
                "original_inv_subtotal": inv.credit_alloc[0].invoice_id.amount_subtotal,
            })
        return data

    def onchange_journal(self, context={}):
        data = context["data"]
        journal_id = data["journal_id"]
        if journal_id:
            journal = get_model("account.journal").browse(journal_id)
            data["sequence_id"] = journal.sequence_id.id
        else:
            data["sequence_id"] = None
        self.onchange_sequence(context=context)
        return data

    def onchange_sequence(self, context={}):
        data = context["data"]
        seq_id = data["sequence_id"]
        num = self._get_number(context={"type": data["type"], "inv_type": data["inv_type"], "date": data["date"], "sequence_id": seq_id})
        data["number"] = num
        return data

Invoice.register()
