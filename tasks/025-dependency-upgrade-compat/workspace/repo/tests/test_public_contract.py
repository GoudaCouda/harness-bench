from catalog_slug.feed_import import prepare_feed_rows
from catalog_slug.slugger import make_slug


def test_ascii_default_and_custom_separator():
    assert make_slug("Quarterly Catalog") == "quarterly-catalog"
    assert make_slug("Quarterly Catalog", separator="_") == "quarterly_catalog"


def test_unicode_feed_key():
    rows = [{"sku": "SKU-1001", "title": "Café Décor"}]
    assert prepare_feed_rows(rows, preserve_unicode=True) == [
        {"sku": "SKU-1001", "title": "Café Décor", "url_key": "café-décor"}
    ]


def test_source_row_is_not_mutated():
    source = {"sku": "SKU-1002", "title": "Summer Offers"}
    prepare_feed_rows([source])
    assert source == {"sku": "SKU-1002", "title": "Summer Offers"}
