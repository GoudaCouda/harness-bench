#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import zipfile
from decimal import Decimal
from xml.etree import ElementTree as ET

package = io.BytesIO()
with zipfile.ZipFile(package, "w") as archive:
    archive.writestr("[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'/>")
    archive.writestr("word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>Northstar</w:t></w:r></w:p></w:body></w:document>")
package.seek(0)
with zipfile.ZipFile(package) as archive:
    names = set(archive.namelist())
    root = ET.fromstring(archive.read("word/document.xml"))
rows = list(csv.DictReader(io.StringIO("region,net\nNorth,10.25\n")))
amount = Decimal(rows[0]["net"])

if "word/document.xml" not in names or root.tag.rsplit("}", 1)[-1] != "document" or amount != Decimal("10.25"):
    raise SystemExit("grader OOXML/CSV/decimal parsing probe failed")
print(json.dumps({"ooxml": "parsed", "csv_rows": len(rows), "decimal": str(amount)}, sort_keys=True))
