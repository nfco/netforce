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
from netforce.database import get_connection, get_active_db
import os
import csv
from netforce import static
from netforce.locale import get_active_locale
from netforce import ipc

_cache = {}


def _clear_cache():
    pid = os.getpid()
    print("translation _clear_cache pid=%s" % pid)
    _cache.clear()

ipc.set_signal_handler("clear_translation_cache", _clear_cache)


class Translation(Model):
    _name = "translation"
    _string = "Translation"
    _key = ["lang_id", "original"]
    _fields = {
        "lang_id": fields.Many2One("language", "Language", required=True, search=True),
        "original": fields.Char("Original String", required=True, search=True),
        "translation": fields.Char("Translation", search=True),
        "comments": fields.One2Many("message", "related_id", "Comments"),
    }
    _order = "lang_id,original"

    def change_lang(self, context={}):
        locale = context["set_locale"]
        return {
            "cookies": {
                "locale": locale,
            },
            "next": {
                "type": "reload",
            }
        }

    def create(self, *a, **kw):
        new_id = super().create(*a, **kw)
        static.clear_translations()
        #ipc.send_signal("clear_translation_cache")
        return new_id

    def write(self, *a, **kw):
        res = super().write(*a, **kw)
        static.clear_translations()
        #ipc.send_signal("clear_translation_cache")

    def delete(self, *a, **kw):
        res = super().delete(*a, **kw)
        static.clear_translations()
        #ipc.send_signal("clear_translation_cache")

    def get_translation(self, original, lang):
        cache = self._get_cache()
        return cache.get((original, lang))

    def translate(self, original):
        lang = get_active_locale()
        cache = self._get_cache()
        return cache.get((original, lang))

    def _get_cache(self):
        global _cache
        dbname = get_active_db()
        cache = _cache.get(dbname)
        if cache is None:
            cache = self._load_cache()
        return cache

    def _load_cache(self):
        global _cache
        dbname = get_active_db()
        print("Loading translations (%s)" % dbname)
        db = get_connection()
        res = db.query(
            "SELECT t.original,l.code AS lang,t.translation FROM translation t, language l WHERE t.lang_id=l.id")
        cache = {}
        for r in res:
            cache[(r.original, r.lang)] = r.translation
        _cache[dbname] = cache
        return cache

Translation.register()
