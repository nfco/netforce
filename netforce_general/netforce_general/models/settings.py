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

from netforce.model import Model, fields
from netforce import static
import datetime
from dateutil.relativedelta import relativedelta

_days = [
    ["1", "1"],
    ["2", "2"],
    ["3", "3"],
    ["4", "4"],
    ["5", "5"],
    ["6", "6"],
    ["7", "7"],
    ["8", "8"],
    ["9", "9"],
    ["10", "10"],
    ["11", "11"],
    ["12", "12"],
    ["13", "13"],
    ["14", "14"],
    ["15", "15"],
    ["16", "16"],
    ["17", "17"],
    ["18", "18"],
    ["19", "19"],
    ["20", "20"],
    ["21", "21"],
    ["22", "22"],
    ["23", "23"],
    ["24", "24"],
    ["25", "25"],
    ["26", "26"],
    ["27", "27"],
    ["28", "28"],
    ["29", "29"],
    ["30", "30"],
    ["31", "31"],
]

_months = [
    ["1", "January"],
    ["2", "February"],
    ["3", "March"],
    ["4", "April"],
    ["5", "May"],
    ["6", "June"],
    ["7", "July"],
    ["8", "August"],
    ["9", "September"],
    ["10", "October"],
    ["11", "November"],
    ["12", "December"],
]


class Settings(Model):
    _name = "settings"
    _key = ["name"]
    _audit_log = True
    _fields = {
        "name": fields.Char("Display Name"),  # not used any more...
        "legal_name": fields.Char("Legal Name"),  # not used any more...
        "company_type_id": fields.Many2One("company.type", "Organization Type"),
        "currency_id": fields.Many2One("currency", "Default Currency", multi_company=True),
        "account_receivable_id": fields.Many2One("account.account", "Account Receivable", multi_company=True),
        "tax_receivable_id": fields.Many2One("account.tax.rate", "Account Receivable Tax"),
        "account_payable_id": fields.Many2One("account.account", "Account Payable", multi_company=True),
        "tax_payable_id": fields.Many2One("account.tax.rate", "Account Payable Tax"),
        "year_end_day": fields.Selection(_days, "Financial Year End (Day)"),
        "year_end_month": fields.Selection(_months, "Financial Year End (Month)"),
        "lock_date": fields.Date("Lock Date"),
        "nf_email": fields.Char("Email to Netforce"),  # XXX: deprecated
        "share_settings": fields.One2Many("share.access", "settings_id", "Sharing Settings"),
        "currency_gain_id": fields.Many2One("account.account", "Currency Gain Account", multi_company=True),
        "currency_loss_id": fields.Many2One("account.account", "Currency Loss Account", multi_company=True),
        "unpaid_claim_id": fields.Many2One("account.account", "Unpaid Expense Claims Account", multi_company=True),
        "retained_earnings_account_id": fields.Many2One("account.account", "Retained Earnings Account", multi_company=True),
        "logo": fields.File("Company Logo", multi_company=True),
        "package": fields.Char("Package", readonly=True),
        "version": fields.Char("Version"),
        "tax_no": fields.Char("Tax ID Number", multi_company=True),
        "branch_no": fields.Char("Branch Number", multi_company=True),
        "addresses": fields.One2Many("address", "settings_id", "Addresses"),
        "date_format": fields.Char("Date Format"),
        "use_buddhist_date": fields.Boolean("Use Buddhist Date"),
        "phone": fields.Char("Phone", multi_company=True),
        "fax": fields.Char("Fax", multi_company=True),
        "website": fields.Char("Website", multi_company=True),
        "root_url": fields.Char("Root URL"),
        "sale_journal_id": fields.Many2One("account.journal", "Sales Journal"),
        "purchase_journal_id": fields.Many2One("account.journal", "Purchase Journal"),
        "pay_in_journal_id": fields.Many2One("account.journal", "Receipts Journal"),
        "pay_out_journal_id": fields.Many2One("account.journal", "Disbursements Journal"),
        "general_journal_id": fields.Many2One("account.journal", "General Journal"),
        "default_address_id": fields.Many2One("address", "Default Address", function="get_default_address"),
        "ar_revenue_id": fields.Many2One("account.account", "Revenue Account", multi_company=True),
        # XXX: rename for report
        "input_report_id": fields.Many2One("account.account", "Input Vat Account", multi_company=True),
        # XXX: rename for report
        "output_report_id": fields.Many2One("account.account", "Output Vat Account", multi_company=True),
        # XXX: rename for report
        "wht3_report_id": fields.Many2One("account.account", "WHT3 Account", multi_company=True),
        # XXX: rename for report
        "wht53_report_id": fields.Many2One("account.account", "WHT53 Account", multi_company=True),
        "sale_copy_picking": fields.Boolean("Auto-copy sales orders to goods issue"),
        "sale_copy_invoice": fields.Boolean("Auto-copy sales orders to customer invoice"),
        "sale_copy_production": fields.Boolean("Auto-copy sales orders to production"),
        "rounding_account_id": fields.Many2One("account.account", "Rounding Account", multi_company=True),
        "production_waiting_suborder": fields.Boolean("Wait Sub-Order"),  # XXX: check this
        "anon_profile_id": fields.Many2One("profile", "Anonymous User Profile"),
        "pick_in_journal_id": fields.Many2One("stock.journal", "Goods Receipt Journal"),
        "pick_out_journal_id": fields.Many2One("stock.journal", "Goods Issue Journal"),
        "pick_internal_journal_id": fields.Many2One("stock.journal", "Goods Transfer Journal"),
        "stock_count_journal_id": fields.Many2One("stock.journal", "Stock Count Journal"),
        "landed_cost_journal_id": fields.Many2One("stock.journal", "Landed Cost Journal"),
        "transform_journal_id": fields.Many2One("stock.journal", "Transform Journal"),
        "production_journal_id": fields.Many2One("stock.journal", "Production Journal"),
        "product_borrow_journal_id": fields.Many2One("stock.journal","Borrow Request Journal"),
        "stock_cost_mode": fields.Selection([["periodic","Periodic"],["perpetual","Perpetual"]],"Inventory Costing Mode"),
        "landed_cost_variance_account_id": fields.Many2One("account.account","Landed Cost Variance Account",multi_company=True),
        "est_ship_account_id": fields.Many2One("account.account","Estimate Shipping Account",multi_company=True),
        "est_duty_account_id": fields.Many2One("account.account","Estimate Duty Account",multi_company=True),
        "act_ship_account_id": fields.Many2One("account.account","Actual Shipping Account",multi_company=True),
        "act_duty_account_id": fields.Many2One("account.account","Actual Duty Account",multi_company=True),
        "menu_icon": fields.File("Menu Icon"),
        "stock_cost_auto_compute": fields.Boolean("Auto Compute Cost"),
        "purchase_copy_picking": fields.Boolean("Auto-copy purchase orders to goods receipt"),
        "purchase_copy_invoice": fields.Boolean("Auto-copy purchase orders to supplier invoice"),
        "lot_expiry_journal_id": fields.Many2One("stock.journal", "Lot Expiry Journal"),
    }
    _defaults = {
        "package": "free",
        'stock_cost_auto_compute': True,
    }

    def get_address_str(self, ids, context={}):
        obj = self.browse(ids[0])
        if not obj.addresses:
            return ""
        addr = obj.addresses[0]
        return addr.name_get()[0][1]

    def write(self, ids, vals, **kw):
        res = super().write(ids, vals, **kw)
        if "date_format" in vals or "use_buddhist_date" in vals:
            static.clear_translations()  # XXX: rename this

    def get_fiscal_year_end(self, date=None):
        if date:
            d0 = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        else:
            d0 = datetime.date.today()
        settings = self.browse(1)
        if not settings.year_end_month or not settings.year_end_day:
            raise Exception("Missing fiscal year end")
        month = int(settings.year_end_month)
        day = int(settings.year_end_day)
        d = datetime.date(d0.year, month, day)
        if d < d0:
            d += relativedelta(years=1)
        return d.strftime("%Y-%m-%d")

    def get_fiscal_year_start(self, date=None):
        d1 = self.get_fiscal_year_end(date)
        d = datetime.datetime.strptime(d1, "%Y-%m-%d") - relativedelta(years=1) + datetime.timedelta(days=1)
        return d.strftime("%Y-%m-%d")

    def get_default_address(self, ids, context={}):
        vals = {}
        for obj in self.browse(ids):
            vals[obj.id] = obj.addresses and obj.addresses[0].id or None
        return vals

Settings.register()
