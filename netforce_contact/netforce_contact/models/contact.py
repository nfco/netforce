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
from netforce.access import get_active_user
from netforce.database import get_connection
from netforce import utils


class Contact(Model):
    _name = "contact"
    _string = "Contact"
    _audit_log = True
    _export_field = "name"
    _fields = {
        "user_id": fields.Many2One("base.user", "User"),
        "type": fields.Selection([["person", "Individual"], ["org", "Organization"]], "Contact Type", required=True, search=True),
        "customer": fields.Boolean("Customer", search=True),
        "supplier": fields.Boolean("Supplier", search=True),
        "name": fields.Char("Name", required=True, search=True, translate=True, size=256),
        "code": fields.Char("Code", search=True),
        "phone": fields.Char("Phone", search=True),
        "fax": fields.Char("Fax"),
        "website": fields.Char("Website"),
        "industry": fields.Char("Industry"),  # XXX: deprecated
        "employees": fields.Char("Employees"),
        "revenue": fields.Char("Annual Revenue"),
        "description": fields.Text("Description"),
        "tax_no": fields.Char("Tax ID Number"),
        "tax_branch_no" : fields.Char("Tax Branch Id"),
        "bank_account_no": fields.Char("Bank Account Number"),
        "bank_account_name": fields.Char("Bank Account Name"),
        "bank_account_details": fields.Char("Bank Account Details"),
        "active": fields.Boolean("Active"),
        "account_receivable_id": fields.Many2One("account.account", "Account Receivable", multi_company=True),
        "tax_receivable_id": fields.Many2One("account.tax.rate", "Account Receivable Tax"),
        "account_payable_id": fields.Many2One("account.account", "Account Payable", multi_company=True),
        "tax_payable_id": fields.Many2One("account.tax.rate", "Account Payable Tax"),
        "currency_id": fields.Many2One("currency", "Default Currency"),
        "payables_due": fields.Decimal("Payables Due"),
        "payables_overdue": fields.Decimal("Payables Overdue"),
        "receivables_due": fields.Decimal("Receivables Due"),
        "receivables_overdue": fields.Decimal("Receivables Overdue"),
        "payable_credit": fields.Decimal("Payable Credit", function="get_credit", function_multi=True),
        "receivable_credit": fields.Decimal("Receivable Credit", function="get_credit", function_multi=True),
        "invoices": fields.One2Many("account.invoice", "contact_id", "Invoices"),
        "sale_price_list_id": fields.Many2One("price.list", "Sales Price List", condition=[["type", "=", "sale"]]),
        "purchase_price_list_id": fields.Many2One("price.list", "Purchasing Price List", condition=[["type", "=", "purchase"]]),
        "categ_id": fields.Many2One("contact.categ", "Contact Category"),
        "payment_terms": fields.Char("Payment Terms"),
        "opports": fields.One2Many("sale.opportunity", "contact_id", "Open Opportunities", condition=[["state", "=", "open"]]),
        "addresses": fields.One2Many("address", "contact_id", "Addresses"),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "bank_accounts": fields.One2Many("bank.account", "contact_id", "Bank Accounts"),
        "last_name": fields.Char("Last Name"),
        "first_name": fields.Char("First Name"),
        "first_name2": fields.Char("First Name (2)"),
        "first_name3": fields.Char("First Name (3)"),
        "title": fields.Char("Title"),
        "position": fields.Char("Position"),
        "report_to_id": fields.Many2One("contact", "Reports To"),
        "mobile": fields.Char("Mobile"),
        "email": fields.Char("Email", search=True),
        "home_phone": fields.Char("Home Phone"),
        "other_phone": fields.Char("Other Phone"),
        "assistant": fields.Char("Assistant"),
        "assistant_phone": fields.Char("Assistant Phone"),
        "birth_date": fields.Date("Birth Date"),
        "department": fields.Char("Department"),
        "job_templates": fields.Many2Many("job.template", "Job Template"),
        "projects": fields.One2Many("project", "contact_id", "Projects"),
        "documents": fields.One2Many("document", "contact_id", "Documents"),
        "assigned_to_id": fields.Many2One("base.user", "Assigned To"),
        "lead_source": fields.Char("Lead source"),
        "inquiry_type": fields.Char("Type of inquiry"),
        "relations": fields.One2Many("contact.relation", "from_contact_id", "Relations", function="_get_relations"),
        "contact_id": fields.Many2One("contact", "Parent"),  # XXX: not used any more, just there for migration
        "emails": fields.One2Many("email.message", "name_id", "Emails"),
        "default_address_id": fields.Many2One("address", "Default Address", function="get_default_address"),
        "sale_orders": fields.One2Many("sale.order", "contact_id", "Sales Orders"),
        "country_id": fields.Many2One("country", "Country", search=True),
        "region": fields.Char("Region"),  # XXX: deprecated
        "service_items": fields.One2Many("service.item", "contact_id", "Service Items", condition=[["parent_id", "=", None]]),
        "contracts": fields.One2Many("service.contract", "contact_id", "Contracts"),
        "branch": fields.Char("Branch"),  # XXX: add by Cash
        "industry_id": fields.Many2One("industry", "Industry", search=True),
        "region_id": fields.Many2One("region", "Region", search=True),
        "commission_po_percent": fields.Decimal("Commission Purchase Percentage"),
        "business_area_id": fields.Many2One("business.area", "Business Area", search=True),
        "fleet_size_id": fields.Many2One("fleet.size", "Fleet Size", search=True),
        "groups": fields.Many2Many("contact.group", "Groups", search=True),
        "sale_journal_id": fields.Many2One("account.journal", "Sales Journal"),
        "purchase_journal_id": fields.Many2One("account.journal", "Purchase Journal"),
        "pay_in_journal_id": fields.Many2One("account.journal", "Receipts Journal"),
        "pay_out_journal_id": fields.Many2One("account.journal", "Disbursements Journal"),
        "pick_in_journal_id": fields.Many2One("stock.journal", "Goods Receipt Journal"),
        "pick_out_journal_id": fields.Many2One("stock.journal", "Goods Issue Journal"),
        "coupons": fields.One2Many("sale.coupon", "contact_id", "Coupons"),
        "companies": fields.Many2Many("company", "Companies"),
        "request_product_groups": fields.Many2Many("product.group","Request Product Groups",reltable="m2m_contact_request_product_groups",relfield="contact_id",relfield_other="group_id"),
        "exclude_product_groups": fields.Many2Many("product.group","Exclude Product Groups",reltable="m2m_contact_exclude_product_groups",relfield="contact_id",relfield_other="group_id"),
        "picture": fields.File("Picture"),
        "users": fields.One2Many("base.user","contact_id","Users"),
    }

    def _get_number(self, context={}):
        seq_id = get_model("sequence").find_sequence(type="contact")
        if not seq_id:
            return None
        while 1:
            num = get_model("sequence").get_next_number(seq_id, context=context)
            res = self.search([["code", "=", num]])
            if not res:
                return num
            get_model("sequence").increment_number(seq_id, context=context)

    _defaults = {
        "active": True,
        "type": "org",
        "code": _get_number,
    }
    _order = "name"
    _constraints=["check_email","check_duplicate_code"]

    def create(self, vals, **kw):
        if not vals.get("type"):
            if vals.get("name"):
                vals["type"] = "org"
            elif vals.get("last_name"):
                vals["type"] = "person"
        if vals.get("type") == "person":
            if vals.get("first_name"):
                vals["name"] = vals["first_name"] + " " + vals["last_name"]
            else:
                vals["name"] = vals["last_name"]
        new_id = super().create(vals, **kw)
        return new_id

    def write(self, ids, vals, set_name=True, **kw):
        super().write(ids, vals, **kw)
        if set_name:
            for obj in self.browse(ids):
                if obj.type == "person":
                    if obj.first_name:
                        name = obj.first_name + " " + obj.last_name
                    else:
                        name = obj.last_name
                    obj.write({"name": name}, set_name=False)

    def get_credit(self, ids, context={}):
        print("contact.get_credit", ids)
        currency_id = context.get("currency_id")
        print("currency_id", currency_id)
        vals = {}
        for obj in self.browse(ids):
            out_credit = 0
            in_credit = 0
            for inv in obj.invoices:
                if inv.state != "waiting_payment":
                    continue
                if inv.inv_type not in ("credit", "prepay", "overpay"):
                    continue
                if currency_id and inv.currency_id.id != currency_id:
                    continue
                if inv.type == "out":
                    if currency_id:
                        out_credit += inv.amount_credit_remain or 0
                    else:
                        out_credit += inv.amount_credit_remain_cur or 0
                elif inv.type == "in":
                    if currency_id:
                        in_credit += inv.amount_credit_remain or 0
                    else:
                        in_credit += inv.amount_credit_remain_cur or 0
            vals[obj.id] = {
                "receivable_credit": out_credit,
                "payable_credit": in_credit,
            }
        return vals

    def get_address_str(self, ids, context={}):
        obj = self.browse(ids[0])
        if not obj.addresses:
            return ""
        addr = obj.addresses[0]
        return addr.name_get()[0][1]

    def _get_relations(self, ids, context={}):
        cond = ["or", ["from_contact_id", "in", ids], ["to_contact_id", "in", ids]]
        rels = get_model("contact.relation").search_read(cond, ["from_contact_id", "to_contact_id"])
        vals = {}
        for rel in rels:
            from_id = rel["from_contact_id"][0]
            to_id = rel["to_contact_id"][0]
            vals.setdefault(from_id, []).append(rel["id"])
            vals.setdefault(to_id, []).append(rel["id"])
        return vals

    def get_address(self, ids, pref_type=None, context={}):
        obj = self.browse(ids)[0]
        for addr in obj.addresses:
            if pref_type and addr.type != pref_type:
                continue
            return addr.id
        if obj.addresses:
            return obj.addresses[0].id
        return None

    def get_default_address(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            addr_id = None
            for addr in obj.addresses:
                if addr.type == "billing":
                    addr_id = addr.id
                    break
            if not addr_id and obj.addresses:
                addr_id = obj.addresses[0].id
            vals[obj.id] = addr_id
        print("XXX", vals)
        return vals

    def check_email(self,ids,context={}):
        for obj in self.browse(ids):
            if not obj.email:
                continue
            if not utils.check_email_syntax(obj.email):
                raise Exception("Invalid email for contact '%s'"%obj.name)

    def check_duplicate_code(self,ids,context={}):
        for obj in self.browse(ids):
            if not obj.code:
                continue
            res=self.search([['code','=',obj.code]])
            if res:
                raise Exception("Duplicate code for contact '%s'"%obj.name)

Contact.register()
