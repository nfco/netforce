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
from netforce.model import get_model, fields
from netforce import database
try:
    import xlsxwriter
    from xlsxwriter.utility import xl_rowcol_to_cell
except:
    xlsxwriter = None
import io
import time
import json


class ReportXLS(Controller):
    _path = "/report_xls"

    def get(self):
        db = database.get_connection()
        try:
            if not xlsxwriter:
                raise Exception("XLSXWriter module not installed")
            model = self.get_argument("model")
            condition = self.get_argument("condition", None)
            if condition:
                condition = json.loads(condition)
            else:
                condition = []
            group_field = self.get_argument("group_field", None)
            subgroup_field = self.get_argument("subgroup_field", None)
            agg_field = self.get_argument("agg_field", None)
            m = get_model(model)
            group_fields = []
            if group_field:
                group_fields.append(group_field)
            if subgroup_field:
                group_fields.append(subgroup_field)
            agg_fields = []
            if agg_field:
                agg_fields.append(agg_field)
            order = ",".join(group_fields)
            lines = m.read_group(group_fields, agg_fields, condition, order=order)

            out = io.BytesIO()
            book = xlsxwriter.Workbook(out)
            fmt_header = book.add_format({'bold': True, "bg_color": "#cccccc"})
            bold = book.add_format({'bold': True})
            sheet = book.add_worksheet()
            col = 0
            for n in group_fields:
                f = self._get_field(model=m, field_name=n)
                sheet.write(0, col, f.string, fmt_header)
                sheet.set_column(col, col, 20)
                col += 1
            sheet.write(0, col, "Count", fmt_header)
            sheet.set_column(col, col, 20)
            col += 1
            for n in agg_fields:
                f = m._fields[n]
                sheet.write(0, col, f.string, fmt_header)
                sheet.set_column(col, col, 20)
                col += 1

            row = 1
            for line in lines:
                col = 0
                for n in group_fields:
                    v = line[n]
                    f = self._get_field(model=m, field_name=n)
                    if isinstance(f, fields.Many2One):
                        v = v[1] if v else None
                    sheet.write(row, col, v)
                    col += 1
                sheet.write(row, col, line["_count"])
                col += 1
                for n in agg_fields:
                    v = line[n]
                    sheet.write(row, col, v)
                    col += 1
                row += 1
            book.close()

            fname = "report-" + time.strftime("%Y-%m-%dT%H:%M:%S") + ".xlsx"
            self.set_header("Content-Disposition", "attachment; filename=%s" % fname)
            self.set_header("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.write(out.getvalue())
        finally:
            db.commit()

    def _get_field(self, model, field_name):
        if not field_name or not model:
            return None
        if isinstance(model, str):
            model = get_model(model)
        path = field_name.split(".", 1)
        if len(path) == 1:
            return model._fields[field_name]
        else:
            sub_model = model._fields[path[0]].relation
            return self._get_field(sub_model, path[1])

ReportXLS.register()
