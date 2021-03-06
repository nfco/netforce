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
from netforce.database import get_connection  # XXX: move this
from .cms_base import BaseController
import json


class GetProvinces(BaseController):
    _path = "/get_provinces"

    def get(self):
        db = get_connection()
        try:
            country_id = self.get_argument("country_id")
            print(country_id)
            country = get_model("country").browse(int(country_id))
            if not country:
                raise Exception("Country not found")
            provinces = []
            for province in country.provinces:
                vals = {
                    'name': province.name,
                    'id': province.id,
                    'code': province.code,
                }
                provinces.append(vals)
            provinces = sorted(provinces, key=lambda k: k['name'])
            print(provinces)
            data = json.dumps(provinces)
            self.write(data)
            db.commit()
        except:
            import traceback
            traceback.print_exc()
            db.rollback()

GetProvinces.register()
