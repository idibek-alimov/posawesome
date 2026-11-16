import importlib.util
import pathlib
import sys
import types
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
HOOKS_PATH = REPO_ROOT / "posawesome" / "hooks.py"
INSTALL_PATH = REPO_ROOT / "posawesome" / "setup" / "install.py"
INSTALL_HOOK = "posawesome.setup.install"


class FakeDB:
    def __init__(self):
        self.indexes = []

    def add_index(self, doctype, fields, index_name=None):
        self.indexes.append((doctype, tuple(fields), index_name))

    def sql(self, *args, **kwargs):
        return True


def load_install_module(fake_frappe):
    original_frappe = sys.modules.get("frappe")
    sys.modules["frappe"] = fake_frappe
    try:
        spec = importlib.util.spec_from_file_location(
            "test_fast_pos_performance_indexes_install_target",
            INSTALL_PATH,
        )
        if spec is None or spec.loader is None:
            raise ImportError("Unable to load POS install module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if original_frappe is None:
            sys.modules.pop("frappe", None)
        else:
            sys.modules["frappe"] = original_frappe


class TestFastPosPerformanceIndexesPatch(unittest.TestCase):
    def test_hooks_register_install_and_migrate_setup(self):
        hooks = HOOKS_PATH.read_text()

        self.assertIn(INSTALL_HOOK, hooks)

    def test_install_adds_fast_counter_indexes(self):
        fake_frappe = types.SimpleNamespace(
            db=FakeDB(),
            log_error=lambda *args, **kwargs: None,
            custom=types.SimpleNamespace(
                doctype=types.SimpleNamespace(
                    custom_field=types.SimpleNamespace(
                        custom_field=types.SimpleNamespace(create_custom_field=lambda *a, **kw: None)
                    )
                )
            ),
        )
        sys.modules["frappe.custom"] = fake_frappe.custom
        sys.modules["frappe.custom.doctype"] = fake_frappe.custom.doctype
        sys.modules["frappe.custom.doctype.custom_field"] = fake_frappe.custom.doctype.custom_field
        sys.modules["frappe.custom.doctype.custom_field.custom_field"] = (
            fake_frappe.custom.doctype.custom_field.custom_field
        )
        module = load_install_module(fake_frappe)

        module.ensure_pos_indexes()

        for doctype, fields, index_name in module.FAST_POS_INDEXES:
            self.assertIn((doctype, tuple(fields), index_name), fake_frappe.db.indexes)
        self.assertIn(
            (
                "Sales Invoice",
                ("docstatus", "company", "posting_date", "name"),
                "posa_si_hot_catalog",
            ),
            fake_frappe.db.indexes,
        )
        self.assertIn(
            (
                "Item Barcode",
                ("barcode", "parent"),
                "posa_barcode_parent",
            ),
            fake_frappe.db.indexes,
        )


if __name__ == "__main__":
    unittest.main()
