frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.doc.docstatus === 1) {
			// Grup tombol khusus Dokumen Pabean Keluar
			frm.add_custom_button(
				__("BC 3.0 (Ekspor)"),
				function () {
					create_outbound_bc_doc(frm, "BC 3.0");
				},
				__("Dokumen Bea Cukai Keluar")
			);

			frm.add_custom_button(
				__("BC 2.5 (Jual Lokal TLDDP)"),
				function () {
					create_outbound_bc_doc(frm, "BC 2.5");
				},
				__("Dokumen Bea Cukai Keluar")
			);

			frm.add_custom_button(
				__("BC 2.7 Keluar (Antar TPB)"),
				function () {
					create_outbound_bc_doc(frm, "BC 2.7 Keluar");
				},
				__("Dokumen Bea Cukai Keluar")
			);

			frm.add_custom_button(
				__("BC 2.6.1 (Keluar Perbaikan)"),
				function () {
					create_outbound_bc_doc(frm, "BC 2.6.1");
				},
				__("Dokumen Bea Cukai Keluar")
			);

			frm.add_custom_button(
				__("BC 4.1 (Hasil Olahan Lokal)"),
				function () {
					create_outbound_bc_doc(frm, "BC 4.1");
				},
				__("Dokumen Bea Cukai Keluar")
			);

			// Pilihan di menu Create standar
			frm.add_custom_button(
				__("Dokumen BC Pengeluaran"),
				function () {
					show_select_outbound_dialog(frm);
				},
				__("Create")
			);
		}
	},
});

function create_outbound_bc_doc(frm, doc_type) {
	frappe.model.open_mapped_doc({
		method: "bea_cukai_integration.api.bc_outbound.make_bc_outbound_from_sales_order",
		frm: frm,
		args: { doc_type: doc_type },
	});
}

function show_select_outbound_dialog(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Pilih Dokumen Pengeluaran Pabean"),
		fields: [
			{
				label: __("Jenis Dokumen Pengeluaran"),
				fieldname: "doc_type",
				fieldtype: "Select",
				options: [
					{ label: "BC 3.0 - Pemberitahuan Ekspor Barang (PEB)", value: "BC 3.0" },
					{ label: "BC 2.5 - Pengeluaran ke Lokal (TLDDP)", value: "BC 2.5" },
					{ label: "BC 2.7 Keluar - Pengeluaran Antar TPB / Kawasan Berikat", value: "BC 2.7 Keluar" },
					{ label: "BC 2.6.1 - Pengeluaran Sementara (Subkontrak / Perbaikan)", value: "BC 2.6.1" },
					{ label: "BC 4.1 - Pengeluaran Hasil Olahan Bahan Baku Lokal", value: "BC 4.1" },
				],
				default: "BC 3.0",
				reqd: 1,
			},
		],
		primary_action_label: __("Lanjutkan"),
		primary_action: function (values) {
			d.hide();
			create_outbound_bc_doc(frm, values.doc_type);
		},
	});
	d.show();
}
