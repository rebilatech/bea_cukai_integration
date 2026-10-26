app_name = "bea_cukai_integration"
app_title = "Bea Cukai Integration"
app_publisher = "Nabila"
app_description = "Bea Cukai Integration for Frappe"
app_email = "admin@frappe.local"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bea_cukai_integration",
# 		"logo": "/assets/bea_cukai_integration/logo.png",
# 		"title": "Bea Cukai Integration",
# 		"route": "/bea_cukai_integration",
# 		"has_permission": "bea_cukai_integration.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bea_cukai_integration/css/bea_cukai_integration.css"
# app_include_js = "/assets/bea_cukai_integration/js/bea_cukai_integration.js"

# include js, css files in header of web template
# web_include_css = "/assets/bea_cukai_integration/css/bea_cukai_integration.css"
# web_include_js = "/assets/bea_cukai_integration/js/bea_cukai_integration.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bea_cukai_integration/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {"Purchase Order": "public/js/purchase_order.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bea_cukai_integration/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bea_cukai_integration.utils.jinja_methods",
# 	"filters": "bea_cukai_integration.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bea_cukai_integration.install.before_install"
# after_install = "bea_cukai_integration.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "bea_cukai_integration.uninstall.before_uninstall"
# after_uninstall = "bea_cukai_integration.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bea_cukai_integration.utils.before_app_install"
# after_app_install = "bea_cukai_integration.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bea_cukai_integration.utils.before_app_uninstall"
# after_app_uninstall = "bea_cukai_integration.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bea_cukai_integration.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["bea_cukai_integration.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"bea_cukai_integration.tasks.all"
# 	],
# 	"daily": [
# 		"bea_cukai_integration.tasks.daily"
# 	],
# 	"hourly": [
# 		"bea_cukai_integration.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bea_cukai_integration.tasks.weekly"
# 	],
# 	"monthly": [
# 		"bea_cukai_integration.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "bea_cukai_integration.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bea_cukai_integration.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bea_cukai_integration.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bea_cukai_integration.utils.before_request"]
# after_request = ["bea_cukai_integration.utils.after_request"]

# Job Events
# ----------
# before_job = ["bea_cukai_integration.utils.before_job"]
# after_job = ["bea_cukai_integration.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bea_cukai_integration.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Fixtures
# --------
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			["name", "in", [
				"Item-custom_hs_code",
				"Item-custom_is_bc",
				"Purchase Receipt-custom_bc_section",
				"Purchase Receipt-custom_bc_declaration",
				"Purchase Receipt-custom_bc_doc_type",
				"Purchase Receipt-custom_bc_no_aju",
				"Purchase Receipt-custom_bc_col_break",
				"Purchase Receipt-custom_bc_tgl_aju",
				"Purchase Receipt-custom_bc_no_daftar",
				"Purchase Receipt-custom_bc_tgl_daftar",
				"Purchase Receipt Item-custom_hs_code",
			]]
		]
	},
	{
		"doctype": "Property Setter",
		"filters": [
			["name", "in", [
				"Item-main-field_order",
			]]
		]
	}
]

after_migrate = "bea_cukai_integration.custom_fields.setup_custom_fields"
