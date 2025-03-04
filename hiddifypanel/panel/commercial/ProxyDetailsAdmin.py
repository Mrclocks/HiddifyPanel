from hiddifypanel.models import *
from hiddifypanel.panel.admin.adminlte import AdminLTEModelView
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
from hiddifypanel.panel import hiddify
from flask import g, redirect, Markup
from hiddifypanel.hutils.flask import hurl_for, flash
from hiddifypanel.auth import login_required
from flask_admin.model.template import EndpointLinkRowAction
from flask_admin.actions import action
from flask_admin.contrib.sqla import form, filters as sqla_filters, tools
# Define a custom field type for the related domains

from flask import current_app


class ProxyDetailsAdmin(AdminLTEModelView):

    column_hide_backrefs = True
    can_create = False
    form_excluded_columns = ['child', 'proto', 'transport', 'l3', 'cdn']
    column_exclude_list = ['child']
    column_searchable_list = ['name', 'proto', 'transport', 'l3', 'cdn']
    column_editable_list = ['name']

    @action('disable', 'Disable', 'Are you sure you want to disable selected proxies?')
    def action_disable(self, ids):
        query = tools.get_query_for_ids(self.get_query(), self.model, ids)
        count = query.update({'enable': False})

        self.session.commit()
        flash(_('%(count)s records were successfully disabled.', count=count), 'success')
        hiddify.get_available_proxies.invalidate_all()

    @action('enable', 'Enable', 'Are you sure you want to enable selected proxies?')
    def action_enable(self, ids):
        query = tools.get_query_for_ids(self.get_query(), self.model, ids)
        count = query.update({'enable': True})

        self.session.commit()
        flash(_('%(count)s records were successfully enabled.', count=count), 'success')
        hiddify.get_available_proxies.invalidate_all()

    # list_template = 'model/domain_list.html'

    # form_overrides = {'work_with': Select2Field}

    def after_model_change(self, form, model, is_created):
        # if hconfig(ConfigEnum.parent_panel):
        #     hiddify_api.sync_child_to_parent()
        hiddify.get_available_proxies.invalidate_all()
        pass

    def after_model_delete(self, model):
        # if hconfig(ConfigEnum.parent_panel):
        #     hiddify_api.sync_child_to_parent()
        hiddify.get_available_proxies.invalidate_all()
        pass

    def is_accessible(self):
        if login_required(roles={Role.super_admin, Role.admin})(lambda: True)() != True:
            return False
        return True

    def _enable_formatter(view, context, model, name):
        if model.enable:
            link = '<i class="fa-solid fa-circle-check text-success"></i> '
        else:
            link = '<i class="fa-solid fa-circle-xmark text-danger"></i> '
        return Markup(link)
    column_formatters = {

        "enable": _enable_formatter
    }
