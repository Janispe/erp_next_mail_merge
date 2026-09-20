"""Optional application-owned HTML transformations; the core has no brand rules."""
import frappe


def apply_print_saving_brand_assets(html, enabled, **options):
    for handler in frappe.get_hooks("mail_merge_transform_html"):
        html = frappe.get_attr(handler)(html, enabled, **options)
    return html
