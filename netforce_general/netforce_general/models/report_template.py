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
import uuid


class ReportTemplate(Model):
    _name = "report.template"
    _string = "Report Template"
    _multi_company = True
    _fields = {
        "name": fields.Char("Template Name", required=True, search=True),
        "type": fields.Selection([
            ["cust_invoice", "Customer Invoice"],
            ["cust_credit_note", "Customer Credit Note"],
            ["supp_invoice", "Supplier Invoice"],
            ["payment", "Payment"],
            ["account_move", "Journal Entry"],
            ["sale_quot", "Quotation"],
            ["sale_order", "Sales Order"],
            ["purch_order", "Purchase Order"],
            ["purchase_request", "Purchase Request"],
            ["prod_order", "Production Order"],
            ["goods_receipt", "Goods Receipt"],
            ["goods_transfer", "Goods Transfer"],
            ["goods_issue", "Goods Issue"],
            ["pay_slip", "Pay Slip"],
            ["tax_detail", "Tax Detail"],
            ["hr_expense", "HR Expense"],
            ["landed_cost","Landed Cost"],
            ["other", "Other"]], "Template Type", required=True, search=True),
        "format": fields.Selection([["odt", "ODT (old)"], ["odt2", "ODT"], ["ods", "ODS"], ["docx", "DOCX (old)"], ["xlsx", "XLSX"], ["jrxml", "JRXML (old)"], ["jrxml2", "JRXML"]], "Template Format", required=True, search=True),
        "file": fields.File("Template File"),
        "company_id": fields.Many2One("company", "Company"),
        "model_id": fields.Many2One("model", "Model"),
        "method": fields.Char("Method"),
    }
    _defaults = {
        "file_type": "odt",
    }

ReportTemplate.register()
