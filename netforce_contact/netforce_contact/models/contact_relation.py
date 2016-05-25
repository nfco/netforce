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


class ContactRelation(Model):
    _name = "contact.relation"
    _string = "Contact Relation"
    _name_field="to_contact_id.name"
    _fields = {
        "from_contact_id": fields.Many2One("contact", "From Contact", required=True, on_delete="cascade"),
        "to_contact_id": fields.Many2One("contact", "To Contact", required=True, on_delete="cascade"),
        "rel_type_id": fields.Many2One("contact.relation.type", "Relation Type", required=True),
        "details": fields.Text("Details"),
    }

    def name_get(self, ids, context={}):
        res=self.browse(ids)
        return [(r.id, r.to_contact_id.name) for r in res]

    def name_search(self, name, condition=None, limit=None, context={}):
        f = self._name_field or "name"
        search_mode = context.get("search_mode")
        if search_mode == "suffix":
            cond = [[f, "=ilike", "%" + name]]
        elif search_mode == "prefix":
            cond = [[f, "=ilike", name + "%"]]
        else:
            cond = [[f, "ilike", name]]
        if condition:
            cond = [cond, condition]
        ids = self.search(cond, limit=limit, context=context)
        return self.name_get(ids, context=context)

ContactRelation.register()
