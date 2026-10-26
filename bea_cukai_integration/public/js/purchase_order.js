frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("BC 2.3 Declaration"),
				function () {
					frappe.model.open_mapped_doc({
						method: "bea_cukai_integration.api.bc_23.make_bc_23_from_po",
						frm: frm,
					});
				},
				__("Create")
			);
		}
	},
});
