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


class PaymentMethod(Model):
    _name = "payment.method"
    _string = "Payment Method"
    _fields = {
        "name": fields.Char("Name", required=True, search=True),
        "code": fields.Char("Code", search=True),
        "sequence": fields.Integer("Sequence"),
        "type": fields.Selection([["bank", "Bank Transfer"], ["credit_card", "Credit Card"], ["paypal", "Paypal"],["scb_gateway","SCB Gateway"], ["paysbuy","Paysbuy"]], "Type", search=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
        "account_id": fields.Many2One("account.account","Account"),
        "paypal_url": fields.Selection([["test", "Test URL"], ["production", "Production URL"]], "Server URL"),
        "paypal_user": fields.Char("Username", size=256),
        "paypal_password": fields.Char("Password", size=256),
        "paypal_signature": fields.Char("Signature", size=256),
        "paysbuy_id": fields.Char("Paysbuy ID"),
        "paysbuy_username": fields.Char("Username"),
        "paysbuy_securecode": fields.Char("Secure Code"),
        "paysbuy_resp_back_url": fields.Char("Response back URL"),
        "paysbuy_url": fields.Selection([["test", "Test URL"], ["production", "Production URL"]], "Server URL"),
        "scb_mid": fields.Char("Merchant ID"),
        "scb_terminal": fields.Char("Terminal ID"),
        "scb_url": fields.Selection([["test", "Test URL"], ["production", "Production URL"]], "Server URL"),
    }
    _order = "sequence,name"

PaymentMethod.register()
