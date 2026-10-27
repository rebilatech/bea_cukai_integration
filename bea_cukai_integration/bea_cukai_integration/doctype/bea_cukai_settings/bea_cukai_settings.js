// Copyright (c) 2026, Nabila and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bea Cukai Settings", {
	refresh(frm) {
		frm.trigger("update_preview");

		frm.add_custom_button(
			__("Test Login / Koneksi CEISA 4.0"),
			function () {
				frappe.call({
					method: "bea_cukai_integration.api.ceisa_client.login_ceisa",
					args: { force: 1 },
					freeze: true,
					freeze_message: __("Menghubungkan ke API Gateway CEISA 4.0..."),
					callback: function (r) {
						if (r.message && r.message.status === "success") {
							frappe.show_alert({
								message: __("Koneksi & Autentikasi CEISA 4.0 Berhasil!"),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			}
		);
	},
	kode_kantor(frm) {
		frm.trigger("update_preview");
	},
	kode_perusahaan(frm) {
		frm.trigger("update_preview");
	},
	no_aju_with_hyphen(frm) {
		frm.trigger("update_preview");
	},
	update_preview(frm) {
		const kantor = (frm.doc.kode_kantor || "0403").substring(0, 4).padStart(4, "0");
		const doc_code = "23"; // BC 2.3
		const pers = (frm.doc.kode_perusahaan || "000001").substring(0, 6).padStart(6, "0");
		const date_str = frappe.datetime.nowdate().replace(/-/g, "");
		const seq = "000001";

		let preview = "";
		if (frm.doc.no_aju_with_hyphen) {
			preview = `${kantor}${doc_code}-${pers}-${date_str}-${seq}`;
		} else {
			preview = `${kantor}${doc_code}${pers}${date_str}${seq}`;
		}

		frm.set_df_property(
			"format_preview",
			"description",
			__("Contoh hasil No Aju hari ini: <b>{0}</b> (Total: {1} karakter)", [
				preview,
				preview.replace(/-/g, "").length,
			])
		);
	},
});
