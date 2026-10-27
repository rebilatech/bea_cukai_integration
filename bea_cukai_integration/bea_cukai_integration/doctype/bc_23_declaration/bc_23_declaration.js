// Copyright (c) 2026, Nabila and contributors
// For license information, please see license.txt

frappe.ui.form.on("BC_23_Declaration", {
	refresh(frm) {
		frm.trigger("render_no_aju_status");

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

		// Tombol pemeriksaan nomor aju (selalu tersedia)
		frm.add_custom_button(
			__("Cek Rincian No Aju"),
			function () {
				show_no_aju_dialog(frm);
			},
			__("Actions")
		);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				__("Generate Ulang No Aju"),
				function () {
					frappe.call({
						method: "bea_cukai_integration.api.bc_23.generate_nomor_aju",
						args: {
							doc_type: frm.doc.doc_type || "BC 2.3",
							tgl_aju: frm.doc.tgl_aju,
						},
						callback: function (r) {
							if (r.message) {
								frm.set_value("no_aju", r.message);
								frappe.show_alert({
									message: __("Nomor Aju 26 digit berhasil digenerate"),
									indicator: "blue",
								});
								frm.trigger("render_no_aju_status");
							}
						},
					});
				},
				__("Actions")
			);
		}
	},

	no_aju(frm) {
		frm.trigger("render_no_aju_status");
	},

	render_no_aju_status(frm) {
		if (!frm.doc.no_aju) {
			frm.set_df_property(
				"no_aju",
				"description",
				__("Nomor Aju 26 digit standar DJBC (otomatis terisi saat simpan atau tarik PO)")
			);
			return;
		}

		frappe.call({
			method: "bea_cukai_integration.api.bc_23.parse_and_validate_no_aju",
			args: { no_aju: frm.doc.no_aju },
			callback: function (r) {
				if (r.message) {
					const d = r.message;
					if (d.is_valid) {
						frm.set_df_property(
							"no_aju",
							"description",
							`<span style="color: #28a745; font-weight: bold;">✔ Valid 26 Digit</span>: Kantor <b>${d.kode_kantor}</b> | Dok <b>${d.kode_dokumen}</b> | Perusahaan <b>${d.kode_perusahaan}</b> | Tgl <b>${d.tanggal_aju}</b> | Urut <b>${d.nomor_urut}</b>`
						);
					} else {
						frm.set_df_property(
							"no_aju",
							"description",
							`<span style="color: #dc3545; font-weight: bold;">✖ Format Tidak Valid</span>: ${d.message}`
						);
					}
				}
			},
		});
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
						if (!frm.doc.no_aju && data.no_aju) {
							frm.set_value("no_aju", data.no_aju);
						}
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
						frm.trigger("render_no_aju_status");
					}
				},
			});
		}
	},
});

function show_no_aju_dialog(frm) {
	if (!frm.doc.no_aju) {
		frappe.msgprint(__("Nomor Aju masih kosong. Silakan generate atau isi terlebih dahulu."));
		return;
	}

	frappe.call({
		method: "bea_cukai_integration.api.bc_23.parse_and_validate_no_aju",
		args: { no_aju: frm.doc.no_aju },
		callback: function (r) {
			if (!r.message) return;
			const data = r.message;

			let htmlContent = "";
			if (data.is_valid) {
				htmlContent = `
					<div style="padding: 10px; border-left: 4px solid #28a745; background-color: #f8fdf9; margin-bottom: 15px;">
						<h5 style="color: #28a745; margin: 0 0 5px 0;">✔ Format Sesuai Standar DJBC 26 Digit</h5>
						<span style="font-family: monospace; font-size: 14px; font-weight: bold;">${data.formatted}</span>
					</div>
					<table class="table table-bordered table-sm" style="font-size: 13px;">
						<tbody>
							<tr><th style="width: 40%;">Kode Kantor Pabean</th><td><b>${data.kode_kantor}</b> (${data.nama_kantor})</td></tr>
							<tr><th>Jenis Dokumen Pabean</th><td><b>${data.kode_dokumen}</b> (${data.doc_type_name})</td></tr>
							<tr><th>Kode Unik Perusahaan</th><td><b>${data.kode_perusahaan}</b></td></tr>
							<tr><th>Tanggal Pengajuan</th><td><b>${data.tanggal_aju}</b> (format YYYYMMDD: ${data.tanggal_raw})</td></tr>
							<tr><th>Nomor Urut Dokumen</th><td><b>${data.nomor_urut}</b></td></tr>
							<tr><th>26 Digit Murni</th><td><code>${data.clean_no}</code></td></tr>
						</tbody>
					</table>
				`;
			} else {
				htmlContent = `
					<div style="padding: 10px; border-left: 4px solid #dc3545; background-color: #fdf8f8; margin-bottom: 15px;">
						<h5 style="color: #dc3545; margin: 0 0 5px 0;">✖ Format Nomor Aju Tidak Valid</h5>
						<p style="margin: 0; color: #555;">${data.message}</p>
					</div>
					<p>Standar nomor pengajuan Bea Cukai harus terdiri dari tepat <b>26 digit alfanumerik</b>:</p>
					<code>[4 digit kantor][2 digit jenis dok][6 digit perusahaan][8 digit tanggal YYYYMMDD][6 digit urut]</code>
				`;
			}

			const d = new frappe.ui.Dialog({
				title: __("Pemeriksaan Nomor Aju Bea Cukai"),
				fields: [
					{
						fieldname: "html_detail",
						fieldtype: "HTML",
						options: htmlContent,
					},
				],
				primary_action_label: __("Tutup"),
				primary_action: function () {
					d.hide();
				},
			});

			if (data.is_valid) {
				d.add_custom_action(__("Buka Cek Aju Bea Cukai"), function () {
					window.open("https://beacukai.go.id/", "_blank");
				});
			}

			d.show();
		},
	});
}
