frappe.ui.form.on("Purchase Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			// Grup tombol khusus Dokumen Pabean Masuk
			frm.add_custom_button(
				__("BC 2.3 (Impor)"),
				function () {
					create_inbound_bc_doc(frm, "BC 2.3");
				},
				__("Dokumen Bea Cukai")
			);

			frm.add_custom_button(
				__("BC 4.0 (Lokal TLDDP)"),
				function () {
					create_inbound_bc_doc(frm, "BC 4.0");
				},
				__("Dokumen Bea Cukai")
			);

			frm.add_custom_button(
				__("BC 2.7 (Antar TPB/KB)"),
				function () {
					create_inbound_bc_doc(frm, "BC 2.7");
				},
				__("Dokumen Bea Cukai")
			);

			frm.add_custom_button(
				__("BC 2.6.2 (Kembali Perbaikan)"),
				function () {
					create_inbound_bc_doc(frm, "BC 2.6.2");
				},
				__("Dokumen Bea Cukai")
			);

			// Pilihan cepat di menu Create standar
			frm.add_custom_button(
				__("Dokumen Pabean (BC)"),
				function () {
					show_select_inbound_dialog(frm);
				},
				__("Create")
			);
		}
	},
});

function create_inbound_bc_doc(frm, doc_type) {
	frappe.model.open_mapped_doc({
		method: "bea_cukai_integration.api.bc_23.make_bc_inbound_from_po",
		frm: frm,
		args: { doc_type: doc_type },
	});
}

function show_select_inbound_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Pilih Dokumen Pemasukan Pabean"),
		fields: [
			{
				label: __("Jenis Dokumen"),
				fieldname: "doc_type",
				fieldtype: "Select",
				options: [
					{ label: "BC 2.3 - Pemasukan Impor Luar Negeri", value: "BC 2.3" },
					{ label: "BC 4.0 - Pemasukan Lokal (TLDDP ke TPB)", value: "BC 4.0" },
					{ label: "BC 2.7 - Pemasukan Antar TPB / Kawasan Berikat", value: "BC 2.7" },
					{ label: "BC 2.6.2 - Pemasukan Kembali setelah Perbaikan / Subkontrak", value: "BC 2.6.2" },
				],
				default: "BC 2.3",
				reqd: 1,
			},
		],
		primary_action_label: __("Lanjutkan"),
		primary_action: function (values) {
			d.hide();
			create_inbound_bc_doc(frm, values.doc_type);
		},
	});
	d.show();
}
