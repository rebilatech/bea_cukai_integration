// Copyright (c) 2026, Nabila and contributors
// For license information, please see license.txt

frappe.ui.form.on("BC_23_Declaration", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Purchase Receipt"),
				function () {
					frappe.model.open_mapped_doc({
						method: "bea_cukai_integration.api.bc_23.make_purchase_receipt_from_bc",
						frm: frm,
					});
				},
				__("Create")
			);
			frm.page.set_inner_btn_group_as_primary(__("Create"));

			frm.add_custom_button(
				__("Generate CEISA JSON"),
				function () {
					frappe.call({
						method: "bea_cukai_integration.api.bc_23.generate_ceisa_payload",
						args: { bc_name: frm.doc.name },
						freeze: true,
						freeze_message: __("Mengenerate Payload CEISA..."),
						callback: function (r) {
							if (r.message) {
								frappe.show_alert({
									message: __("Payload CEISA 4.0 berhasil digenerate"),
									indicator: "green",
								});
								frm.reload_doc();
							}
						},
					});
				},
				__("Actions")
			);
		}
	},

	erp_bc_reference(frm) {
		if (frm.doc.erp_bc_reference && (!frm.doc.detail_item || frm.doc.detail_item.length === 0)) {
			frappe.call({
				method: "bea_cukai_integration.api.bc_23.make_bc_23_from_po",
				args: { source_name: frm.doc.erp_bc_reference },
				freeze: true,
				freeze_message: __("Menarik data item dari Purchase Order..."),
				callback: function (r) {
					if (r.message) {
						const data = r.message;
						if (!frm.doc.supplier_name) {
							frm.set_value("supplier_name", data.supplier_name);
						}
						if (!frm.doc.currency) {
							frm.set_value("currency", data.currency);
						}
						if (!frm.doc.cif_value) {
							frm.set_value("cif_value", data.cif_value);
						}

						frm.clear_table("detail_item");
						(data.detail_item || []).forEach((row) => {
							let child = frm.add_child("detail_item");
							Object.assign(child, row);
						});
						frm.refresh_field("detail_item");
					}
				},
			});
		}
	},
});
