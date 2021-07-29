# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.


{
    'name': 'Magnus Planning',
    'version': '1.0',
    'category': 'Human Resources',
    'sequence': 23,
    'summary': 'Track employee time on tasks',
    'description': """
This module implements a planning system.
==========================================

Each employee can encode and track their time spent on the different projects.

Lots of reporting on time and employee tracking are provided.

It is completely integrated with the cost accounting module. It allows you to set
up a management by affair.
    """,
    'website': 'https://www.odoo.com/page/planning-mobile-app',
    'depends': ['hr_timesheet', 'analytic', 'project', 'uom'],
    'data': [
        # 'security/magnus_planning_security.xml',
        'security/ir.model.access.csv',
        # 'views/assets.xml',
        # 'views/magnus_planning_views.xml',
        # 'views/res_config_settings_views.xml',
        # 'views/project_views.xml',
        # 'views/project_portal_templates.xml',
        # 'report/magnus_planning_report_view.xml',
        # 'report/report_planning_templates.xml',
        'views/hr_planning_views.xml',
        # 'data/magnus_planning_data.xml',
    ],

    'installable': True,
    'application': False,
    'auto_install': False,
}
