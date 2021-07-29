# Copyright 2018 Eficent Business and IT Consulting Services, S.L.
# Copyright 2018-2020 Brainbean Apps (https://brainbeanapps.com)
# Copyright 2018-2019 Onestein (<https://www.onestein.eu>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import babel.dates
import logging
import re
from collections import namedtuple
from datetime import datetime, time
from dateutil.relativedelta import relativedelta, SU
from dateutil.rrule import MONTHLY, WEEKLY

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

empty_name = '/'


class MagnusPlanning(models.Model):
    _name = 'magnus.planning'
    _description = 'Magnus Planning'
    # _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    # _table = 'hr_timesheet_sheet'
    _order = 'id desc'
    # _rec_name = 'complete_name'

    def _default_date_start(self):
        return (datetime.today() + relativedelta(weekday=0, days=-6)).strftime('%Y-%m-%d')
        # return self._get_period_start(
        #     self.env.user.company_id,
        #     fields.Date.context_today(self)
        # )

    def _default_date_end(self):
        return (datetime.today() + relativedelta(weekday=6)).strftime('%Y-%m-%d')
        # return self._get_period_end(
        #     self.env.user.company_id,
        #     fields.Date.context_today(self)
        # )

    # def _selection_review_policy(self):
    #     ResCompany = self.env['res.company']
    #     return ResCompany._fields['timesheet_sheet_review_policy'].selection

    # def _default_review_policy(self):
    #     company = self.env['res.company']._company_default_get()
    #     return company.timesheet_sheet_review_policy

    def _default_employee(self):
        company = self.env['res.company']._company_default_get()
        return self.env['hr.employee'].search([
            ('user_id', '=', self.env.uid),
            ('company_id', 'in', [company.id, False]),
        ], limit=1, order="company_id ASC")

    def _default_department_id(self):
        return self._default_employee().department_id


    def fetch_weeks_from_planning_quarter(self, planning_quarter):
        start_date = planning_quarter.date_start
        end_date = planning_quarter.date_end
        # date_range_type_cw = self.env.ref('magnus_date_range_week.date_range_calender_week')
        date_range = self.env['date.range']
        # domain = [('type_id', '=', date_range_type_cw.id)]
        domain = [('type_id', '=', 1)]
        week_from = date_range.search(domain + [('date_start', '<=', start_date), ('date_end', '>=', start_date)],
                                           limit=1).id
        week_to = date_range.search(domain + [('date_start', '<=', end_date), ('date_end', '>=', end_date)],
                                         limit=1).id
        return week_from, week_to

    @api.onchange('planning_quarter')
    def onchange_planning_quarter(self):
        self.employee_id = self._default_employee()
        if not self.week_to or not self.week_from:
            self.week_from, self.week_to = self.fetch_weeks_from_planning_quarter(self.planning_quarter)


    week_to = fields.Many2one('date.range', string="Week Start")
    week_from = fields.Many2one('date.range', string="Week End")
    planning_quarter = fields.Many2one('date.range', string='Select Quarter',
                                       required=True, index=True)

    name = fields.Char(
        compute='_compute_name',
        context_dependent=True,
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
        default=lambda self: self._default_employee(),
        required=True,
        readonly=True,
        states={'new': [('readonly', False)]},
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        related='employee_id.user_id',
        string='User',
        store=True,
        readonly=True,
    )
    date_start = fields.Date(
        string='Date From',
        # default=lambda self: self._default_date_start(),
        required=False,
        index=True,
        readonly=True,
        states={'new': [('readonly', False)]},
    )
    date_end = fields.Date(
        string='Date To',
        # default=lambda self: self._default_date_end(),
        required=False,
        index=True,
        readonly=True,
        states={'new': [('readonly', False)]},
    )
    planning_ids = fields.One2many(
        comodel_name='account.analytic.line',
        inverse_name='planning_id',
        string='Planning',
        readonly=True,
        states={
            'new': [('readonly', False)],
            'draft': [('readonly', False)],
        },
    )
    line_ids = fields.One2many(
        comodel_name='magnus.planning.line',
        compute='_compute_line_ids',
        string='Planning Lines',
        readonly=True,
        states={
            'new': [('readonly', False)],
            'draft': [('readonly', False)],
        },
    )
    new_line_ids = fields.One2many(
        comodel_name='magnus.planning.new.analytic.line',
        inverse_name='planning_id',
        string='Temporary Timesheets',
        readonly=True,
        states={
            'new': [('readonly', False)],
            'draft': [('readonly', False)],
        },
    )
    state = fields.Selection([
        ('new', 'New'),
        ('draft', 'Open'),
        ('confirm', 'Waiting Review'),
        ('done', 'Approved')],
        default='new', track_visibility='onchange',
        string='Status', required=True, readonly=True, index=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env['res.company']._company_default_get(),
        required=True,
        readonly=True,
    )
    # review_policy = fields.Selection(
    #     selection=lambda self: self._selection_review_policy(),
    #     default=lambda self: self._default_review_policy(),
    #     required=True,
    #     readonly=True,
    # )
    department_id = fields.Many2one(
        comodel_name='hr.department',
        string='Department',
        default=lambda self: self._default_department_id(),
        readonly=True,
        states={'new': [('readonly', False)]},
    )
    reviewer_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Reviewer',
        readonly=True,
        track_visibility='onchange',
    )
    add_line_project_id = fields.Many2one(
        comodel_name='project.project',
        string='Select Project',
        help='If selected, the associated project is added '
             'to the timesheet sheet when clicked the button.',
    )
    add_line_task_id = fields.Many2one(
        comodel_name='project.task',
        string='Select Task',
        help='If selected, the associated task is added '
             'to the timesheet sheet when clicked the button.',
    )
    add_line_emp_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Select Employee',
    )
    total_time = fields.Float(
        compute='_compute_total_time',
        store=True,
    )
    # can_review = fields.Boolean(
    #     string='Can Review',
    #     compute='_compute_can_review',
    #     search='_search_can_review',
    # )
    # complete_name = fields.Char(
    #     string='Complete Name',
    #     compute='_compute_complete_name',
    # )

    @api.multi
    # @api.depends('date_start', 'date_end')
    # @api.depends('planning_quarter')
    @api.depends('week_from', 'week_to')
    def _compute_name(self):
        locale = self.env.context.get('lang') or self.env.user.lang or 'en_US'
        for sheet in self:
            if sheet.planning_quarter.date_start == sheet.planning_quarter.date_end:
                sheet.name = babel.dates.format_skeleton(
                    skeleton='MMMEd',
                    datetime=datetime.combine(sheet.planning_quarter.date_start, time.min),
                    locale=locale,
                )
                continue

            period_start = sheet.planning_quarter.date_start.strftime(
                '%V, %Y'
            )
            period_end = sheet.planning_quarter.date_end.strftime(
                '%V, %Y'
            )

            if sheet.planning_quarter.date_end <= sheet.planning_quarter.date_start + relativedelta(weekday=SU):
                sheet.name = _('Week %s') % (
                    period_end,
                )
            else:
                sheet.name = _('Weeks %s - %s') % (
                    period_start,
                    period_end,
                )

    @api.depends('planning_ids.unit_amount')
    def _compute_total_time(self):
        for sheet in self:
            sheet.total_time = sum(sheet.mapped('planning_ids.unit_amount'))

    # @api.multi
    # @api.depends('review_policy')
    # def _compute_can_review(self):
    #     for sheet in self:
    #         sheet.can_review = self.env.user in sheet._get_possible_reviewers()

    # @api.model
    # def _search_can_review(self, operator, value):
    #
    #     def check_in(users):
    #         return self.env.user in users
    #
    #     def check_not_in(users):
    #         return self.env.user not in users
    #
    #     if (operator == '=' and value) \
    #             or (operator in ['<>', '!='] and not value):
    #         check = check_in
    #     else:
    #         check = check_not_in
    #
    #     sheets = self.search([]).filtered(
    #         lambda sheet: check(sheet._get_possible_reviewers())
    #     )
    #     return [('id', 'in', sheets.ids)]

    # @api.depends('name', 'employee_id')
    # def _compute_complete_name(self):
    #     for sheet in self:
    #         complete_name = sheet.name
    #         complete_name_components = sheet._get_complete_name_components()
    #         if complete_name_components:
    #             complete_name = '%s (%s)' % (
    #                 complete_name,
    #                 ', '.join(complete_name_components)
    #             )
    #         sheet.complete_name = complete_name

    # @api.constrains('date_start', 'date_end')
    # def _check_start_end_dates(self):
    #     for sheet in self:
    #         if sheet.date_start > sheet.date_end:
    #             raise ValidationError(
    #                 _('The start date cannot be later than the end date.'))

    # @api.multi
    # def _get_complete_name_components(self):
    #     """ Hook for extensions """
    #     self.ensure_one()
    #     return [self.employee_id.name_get()[0][1]]

    @api.multi
    def _get_overlapping_sheet_domain(self):
        """ Hook for extensions """
        self.ensure_one()
        return [
            ('id', '!=', self.id),
            ('date_start', '<=', self.week_to.date_end),
            ('date_end', '>=', self.week_from.date_start),
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self._get_timesheet_sheet_company().id),
        ]

    # @api.constrains(
    #     'date_start',
    #     'date_end',
    #     'company_id',
    #     'employee_id',
    # )
    @api.constrains(
        'week_from',
        'week_to',
        'company_id',
        'employee_id',
    )
    def _check_overlapping_sheets(self):
        for sheet in self:
            overlapping_sheets = self.search(
                sheet._get_overlapping_sheet_domain()
            )
            if overlapping_sheets:
                raise ValidationError(_(
                    'You cannot have 2 or more sheets that overlap!\n'
                    'Please use the menu "Timesheet Sheet" '
                    'to avoid this problem.\nConflicting sheets:\n - %s' % (
                        '\n - '.join(overlapping_sheets.mapped('name')),
                    )
                ))

    @api.multi
    @api.constrains('company_id', 'employee_id')
    def _check_company_id_employee_id(self):
        for rec in self.sudo():
            if rec.company_id and rec.employee_id.company_id and \
                    rec.company_id != rec.employee_id.company_id:
                raise ValidationError(
                    _('The Company in the Timesheet Sheet and in '
                      'the Employee must be the same.'))

    @api.multi
    @api.constrains('company_id', 'department_id')
    def _check_company_id_department_id(self):
        for rec in self.sudo():
            if rec.company_id and rec.department_id.company_id and \
                    rec.company_id != rec.department_id.company_id:
                raise ValidationError(
                    _('The Company in the Timesheet Sheet and in '
                      'the Department must be the same.'))

    @api.multi
    @api.constrains('company_id', 'add_line_project_id')
    def _check_company_id_add_line_project_id(self):
        for rec in self.sudo():
            if rec.company_id and rec.add_line_project_id.company_id and \
                    rec.company_id != rec.add_line_project_id.company_id:
                raise ValidationError(
                    _('The Company in the Timesheet Sheet and in '
                      'the Project must be the same.'))

    # @api.multi
    # @api.constrains('company_id', 'add_line_task_id')
    # def _check_company_id_add_line_task_id(self):
    #     for rec in self.sudo():
    #         if rec.company_id and rec.add_line_task_id.company_id and \
    #                 rec.company_id != rec.add_line_task_id.company_id:
    #             raise ValidationError(
    #                 _('The Company in the Timesheet Sheet and in '
    #                   'the Task must be the same.'))
    @api.multi
    @api.constrains('company_id', 'add_line_emp_id')
    def _check_company_id_add_line_emp_id(self):
        for rec in self.sudo():
            if rec.company_id and rec.add_line_emp_id.company_id and \
                    rec.company_id != rec.add_line_emp_id.company_id:
                raise ValidationError(
                    _('The Company in the Timesheet Sheet and in '
                      'the Task must be the same.'))

    # @api.multi
    # def _get_possible_reviewers(self):
    #     self.ensure_one()
    #     res = self.env['res.users'].browse(SUPERUSER_ID)
    #     if self.review_policy == 'hr':
    #         res |= self.env.ref('hr.group_hr_user').users
    #     elif self.review_policy == 'hr_manager':
    #         res |= self.env.ref('hr.group_hr_manager').users
    #     elif self.review_policy == 'timesheet_manager':
    #         res |= self.env.ref('hr_timesheet.group_timesheet_manager').users
    #     return res

    @api.multi
    def _get_timesheet_sheet_company(self):
        self.ensure_one()
        employee = self.employee_id
        company = employee.company_id or employee.department_id.company_id
        if not company:
            company = employee.user_id.company_id
        return company

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            company = self._get_timesheet_sheet_company()
            self.company_id = company
            # self.review_policy = company.timesheet_sheet_review_policy
            self.department_id = self.employee_id.department_id

    @api.multi
    def _get_timesheet_sheet_lines_domain(self):
        self.ensure_one()
        return [
            ('date', '<=', self.week_to.date_end),
            ('date', '>=', self.week_from.date_start),
            ('employee_id', '=', self.employee_id.id),
            ('company_id', '=', self._get_timesheet_sheet_company().id),
            ('project_id', '!=', False),
        ]

    @api.multi
    # @api.depends('date_start', 'date_end')
    @api.depends('week_from', 'week_to')
    def _compute_line_ids(self):
        SheetLine = self.env['magnus.planning.line']
        for sheet in self:
            if not all([sheet.week_from.date_start, sheet.week_to.date_end]):
                continue
            matrix = sheet._get_data_matrix()
            vals_list = []
            for key in sorted(matrix,
                              key=lambda key: self._get_matrix_sortby(key)):
                vals_list.append(sheet._get_default_sheet_line(matrix, key))
                if sheet.state in ['new', 'draft']:
                    sheet.clean_timesheets(matrix[key])
            sheet.line_ids = SheetLine.create(vals_list)

    @api.model
    def _matrix_key_attributes(self):
        """ Hook for extensions """
        return ['date', 'project_id', 'task_id']

    @api.model
    def _matrix_key(self):
        return namedtuple('MatrixKey', self._matrix_key_attributes())

    @api.model
    def _get_matrix_key_values_for_line(self, aal):
        """ Hook for extensions """
        return {
            'date': aal.date,
            'project_id': aal.project_id,
            'task_id': aal.task_id,
        }

    @api.model
    def _get_matrix_sortby(self, key):
        res = []
        for attribute in key:
            value = None
            if hasattr(attribute, 'name_get'):
                name = attribute.name_get()
                value = name[0][1] if name else ''
            else:
                value = attribute
            res.append(value)
        return res

    @api.multi
    def _get_data_matrix(self):
        self.ensure_one()
        MatrixKey = self._matrix_key()
        matrix = {}
        empty_line = self.env['account.analytic.line']
        for line in self.planning_ids:
            key = MatrixKey(**self._get_matrix_key_values_for_line(line))
            if key not in matrix:
                matrix[key] = empty_line
            matrix[key] += line
        for date in self._get_dates():
            for key in matrix.copy():
                key = MatrixKey(**{
                    **key._asdict(),
                    'date': date,
                })
                if key not in matrix:
                    matrix[key] = empty_line
        return matrix

    def _compute_planning_ids(self):
        AccountAnalyticLines = self.env['account.analytic.line']
        for sheet in self:
            domain = sheet._get_timesheet_sheet_lines_domain()
            timesheets = AccountAnalyticLines.search(domain)
            sheet.link_timesheets_to_sheet(timesheets)
            sheet.planning_ids = timesheets

    # @api.onchange('date_start', 'date_end', 'employee_id')
    @api.onchange('week_from', 'week_to', 'employee_id')
    def _onchange_scope(self):
        self._compute_planning_ids()


    @api.onchange('planning_ids')
    def _onchange_timesheets(self):
        self._compute_line_ids()

    # @api.onchange('add_line_project_id')
    # def onchange_add_project_id(self):
    #     """Load the project to the timesheet sheet"""
    #     if self.add_line_project_id:
    #         return {
    #             'domain': {
    #                 'add_line_task_id': [
    #                     ('project_id', '=', self.add_line_project_id.id),
    #                     ('company_id', '=', self.company_id.id),
    #                     ('id', 'not in',
    #                      self.planning_ids.mapped('task_id').ids)],
    #             },
    #         }
    #     else:
    #         return {
    #             'domain': {
    #                 'add_line_task_id': [('id', '=', False)],
    #             },
    #         }
    # since the project is selected after employee selection, task related condition is not required

    @api.model
    def _check_employee_user_link(self, vals):
        if 'employee_id' in vals:
            employee = self.env['hr.employee'].browse(vals['employee_id'])
            if not employee.user_id:
                raise UserError(_(
                    'In order to create a sheet for this employee, you must'
                    ' link him/her to an user: %s'
                ) % (
                    employee.name,
                ))
            return employee.user_id.id
        return False

    @api.multi
    def copy(self, default=None):
        if not self.env.context.get('allow_copy_timesheet'):
            raise UserError(_('You cannot duplicate a sheet.'))
        return super().copy(default=default)

    @api.model
    def create(self, vals):
        self._check_employee_user_link(vals)
        res = super().create(vals)
        res.write({'state': 'draft'})
        return res

    def _sheet_write(self, field, recs):
        self.with_context(sheet_write=True).write({field: [(6, 0, recs.ids)]})

    @api.multi
    def write(self, vals):
        self._check_employee_user_link(vals)
        res = super().write(vals)
        for rec in self:
            if rec.state == 'draft' and \
                    not self.env.context.get('sheet_write'):
                rec._update_analytic_lines_from_new_lines(vals)
                if 'add_line_project_id' not in vals:
                    rec.delete_empty_lines(True)
        return res

    @api.multi
    def unlink(self):
        for sheet in self:
            if sheet.state in ('confirm', 'done'):
                raise UserError(_(
                    'You cannot delete a timesheet sheet which is already'
                    ' submitted or confirmed: %s') % (
                        sheet.name,
                    ))
        return super().unlink()

    def _get_informables(self):
        """ Hook for extensions """
        self.ensure_one()
        return self.employee_id.parent_id.user_id.partner_id

    # def _get_subscribers(self):
    #     """ Hook for extensions """
    #     self.ensure_one()
    #     subscribers = self._get_possible_reviewers().mapped('partner_id')
    #     subscribers |= self._get_informables()
    #     return subscribers

    # def _timesheet_subscribe_users(self):
    #     for sheet in self.sudo():
    #         subscribers = sheet._get_subscribers()
    #         if subscribers:
    #             self.message_subscribe(partner_ids=subscribers.ids)

    @api.multi
    def action_timesheet_draft(self):
        if self.filtered(lambda sheet: sheet.state != 'done'):
            raise UserError(_('Cannot revert to draft a non-approved sheet.'))
        # self._check_can_review()
        self.write({
            'state': 'draft',
            'reviewer_id': False,
        })

    @api.multi
    def action_timesheet_confirm(self):
        # self._timesheet_subscribe_users()
        self.reset_add_line()
        self.write({'state': 'confirm'})

    @api.multi
    def action_timesheet_done(self):
        if self.filtered(lambda sheet: sheet.state != 'confirm'):
            raise UserError(_('Cannot approve a non-submitted sheet.'))
        # self._check_can_review()
        self.write({
            'state': 'done',
            'reviewer_id': self._get_current_reviewer().id,
        })

    @api.multi
    def action_timesheet_refuse(self):
        if self.filtered(lambda sheet: sheet.state != 'confirm'):
            raise UserError(_('Cannot reject a non-submitted sheet.'))
        # self._check_can_review()
        self.write({
            'state': 'draft',
            'reviewer_id': False,
        })

    @api.model
    def _get_current_reviewer(self):
        reviewer = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)],
            limit=1
        )
        if not reviewer:
            raise UserError(_(
                'In order to review a timesheet sheet, your user needs to be'
                ' linked to an employee.'
            ))
        return reviewer

    # @api.multi
    # def _check_can_review(self):
    #     if self.filtered(
    #             lambda x: not x.can_review and x.review_policy == 'hr'):
    #         raise UserError(_(
    #             'Only a HR Officer or Manager can review the sheet.'
    #         ))

    @api.multi
    def button_add_line(self):
        for rec in self:
            if rec.state in ['new', 'draft']:
                rec.add_line()
                rec.reset_add_line()

    def reset_add_line(self):
        self.write({
            'add_line_project_id': False,
            # 'add_line_task_id': False,
            'add_line_emp_id': False,
        })

    def _get_date_name(self, date):
        name = babel.dates.format_skeleton(
            skeleton='MMMEd',
            datetime=datetime.combine(date, time.min),
            locale=(
                self.env.context.get('lang') or self.env.user.lang or 'en_US'
            ),
        )
        name = re.sub(r'(\s*[^\w\d\s])\s+', r'\1\n', name)
        name = re.sub(r'([\w\d])\s([\w\d])', u'\\1\u00A0\\2', name)
        return name

    def _get_dates(self):
        start = self.week_from.date_start
        end = self.week_to.date_start
        if end < start:
            return []
        dates = [start]
        while start != end:
            start += relativedelta(days=7)
            dates.append(start)
        print ('\n\n\ndates----------\n', dates)
        return dates

    @api.multi
    def _get_line_name(self, project_id, task_id=None, **kwargs):
        self.ensure_one()
        if task_id:
            return '%s - %s' % (
                project_id.name_get()[0][1],
                task_id.name_get()[0][1]
            )

        return project_id.name_get()[0][1]

    @api.multi
    def _get_new_line_unique_id(self):
        """ Hook for extensions """
        self.ensure_one()
        return {
            'project_id': self.add_line_project_id,
            # 'task_id': self.add_line_task_id,
            'employee_id': self.add_line_emp_id,
        }

    @api.multi
    def _get_default_sheet_line(self, matrix, key):
        self.ensure_one()
        values = {
            'value_x': self._get_date_name(key.date),
            'value_y': self._get_line_name(**key._asdict()),
            'date': key.date,
            'project_id': key.project_id.id,
            'task_id': key.task_id.id,
            'unit_amount': sum(t.unit_amount for t in matrix[key]),
            'employee_id': self.employee_id.id,
            'company_id': self.company_id.id,
        }
        if self.id:
            values.update({'planning_id': self.id})
        return values

    @api.model
    def _prepare_empty_analytic_line(self):
        return {
            'name': empty_name,
            # 'employee_id': self.employee_id.id,
            'date': self.week_from.date_start,
            'project_id': self.add_line_project_id.id,
            # 'task_id': self.add_line_task_id.id,
            'employee_id': self.add_line_emp_id.id,
            'planning_id': self.id,
            'unit_amount': 0.0,
            'company_id': self.company_id.id,
        }

    def add_line(self):
        if not self.add_line_project_id:
            return
        values = self._prepare_empty_analytic_line()
        new_line_unique_id = self._get_new_line_unique_id()
        existing_unique_ids = list(set(
            [frozenset(line.get_unique_id().items()) for line in self.line_ids]
        ))
        if existing_unique_ids:
            self.delete_empty_lines(False)
        if frozenset(new_line_unique_id.items()) not in existing_unique_ids:
            self.planning_ids |= \
                self.env['account.analytic.line']._planning_create(values)

    def link_timesheets_to_sheet(self, timesheets):
        self.ensure_one()
        if self.id and self.state in ['new', 'draft']:
            for aal in timesheets.filtered(lambda a: not a.planning_id):
                aal.write({'planning_id': self.id})

    def clean_timesheets(self, timesheets):
        repeated = timesheets.filtered(lambda t: t.name == empty_name)
        if len(repeated) > 1 and self.id:
            return repeated.merge_timesheets()
        return timesheets

    @api.multi
    def _is_add_line(self, row):
        """ Hook for extensions """
        self.ensure_one()
        # return self.add_line_project_id == row.project_id \
        #     and self.add_line_task_id == row.task_id
        return self.add_line_project_id == row.project_id \
            and self.add_line_emp_id == row.employee_id

    @api.model
    def _is_line_of_row(self, aal, row):
        """ Hook for extensions """
        # return aal.project_id.id == row.project_id.id \
        #     and aal.task_id.id == row.task_id.id
        return aal.project_id.id == row.project_id.id \
            and aal.employee_id.id == row.employee_id.id

    def delete_empty_lines(self, delete_empty_rows=False):
        self.ensure_one()
        for name in list(set(self.line_ids.mapped('value_y'))):
            rows = self.line_ids.filtered(lambda l: l.value_y == name)
            if not rows:
                continue
            row = fields.first(rows)
            if delete_empty_rows and self._is_add_line(row):
                check = any([l.unit_amount for l in rows])
            else:
                check = not all([l.unit_amount for l in rows])
            if not check:
                continue
            row_lines = self.planning_ids.filtered(
                lambda aal: self._is_line_of_row(aal, row)
            )
            row_lines.filtered(
                lambda t: t.name == empty_name and not t.unit_amount
            ).unlink()
            if self.planning_ids != self.planning_ids.exists():
                self._sheet_write(
                    'planning_ids', self.planning_ids.exists())

    @api.multi
    def _update_analytic_lines_from_new_lines(self, vals):
        self.ensure_one()
        new_line_ids_list = []
        for line in vals.get('line_ids', []):
            # Every time we change a value in the grid a new line in line_ids
            # is created with the proposed changes, even though the line_ids
            # is a computed field. We capture the value of 'new_line_ids'
            # in the proposed dict before it disappears.
            # This field holds the ids of the transient records
            # of model 'magnus.planning.new.analytic.line'.
            if line[0] == 1 and line[2] and line[2].get('new_line_id'):
                new_line_ids_list += [line[2].get('new_line_id')]
        for new_line in self.new_line_ids.exists():
            if new_line.id in new_line_ids_list:
                new_line._update_analytic_lines()
        self.new_line_ids.exists().unlink()
        self._sheet_write('new_line_ids', self.new_line_ids.exists())

    @api.model
    def _prepare_new_line(self, line):
        """ Hook for extensions """
        return {
            'planning_id': line.planning_id.id,
            'date': line.date,
            'project_id': line.project_id.id,
            'task_id': line.task_id.id,
            'unit_amount': line.unit_amount,
            'company_id': line.company_id.id,
            'employee_id': line.employee_id.id,
        }

    @api.multi
    def _is_compatible_new_line(self, line_a, line_b):
        """ Hook for extensions """
        self.ensure_one()
        return line_a.project_id.id == line_b.project_id.id \
            and line_a.task_id.id == line_b.task_id.id \
            and line_a.date == line_b.date

    @api.multi
    def add_new_line(self, line):
        self.ensure_one()
        new_line_model = self.env['magnus.planning.new.analytic.line']
        new_line = self.new_line_ids.filtered(
            lambda l: self._is_compatible_new_line(l, line)
        )
        if new_line:
            new_line.write({'unit_amount': line.unit_amount})
        else:
            vals = self._prepare_new_line(line)
            new_line = new_line_model.create(vals)
        self._sheet_write('new_line_ids', self.new_line_ids | new_line)
        line.new_line_id = new_line.id

    # @api.model
    # def _get_period_start(self, company, date):
    #     r = company and company.sheet_range or WEEKLY
    #     if r == WEEKLY:
    #         if company.timesheet_week_start:
    #             delta = relativedelta(
    #                 weekday=int(company.timesheet_week_start),
    #                 days=6)
    #         else:
    #             delta = relativedelta(days=date.weekday())
    #         return date - delta
    #     elif r == MONTHLY:
    #         return date + relativedelta(day=1)
    #     return date

    # @api.model
    # def _get_period_end(self, company, date):
    #     r = company and company.sheet_range or WEEKLY
    #     if r == WEEKLY:
    #         if company.timesheet_week_start:
    #             delta = relativedelta(weekday=(int(
    #                 company.timesheet_week_start) + 6) % 7)
    #         else:
    #             delta = relativedelta(days=6-date.weekday())
    #         return date + delta
    #     elif r == MONTHLY:
    #         return date + relativedelta(months=1, day=1, days=-1)
    #     return date

    # ------------------------------------------------
    # OpenChatter methods and notifications
    # ------------------------------------------------

    @api.multi
    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'state' in init_values and self.state == 'confirm':
            return 'hr_timesheet_sheet.mt_timesheet_confirmed'
        elif 'state' in init_values and self.state == 'done':
            return 'hr_timesheet_sheet.mt_timesheet_approved'
        return super()._track_subtype(init_values)


class MagnusAbstractSheetLine(models.AbstractModel):
    _name = 'magnus.planning.line.abstract'
    _description = 'Abstract Timesheet Sheet Line'

    planning_id = fields.Many2one(
        comodel_name='magnus.planning',
        ondelete='cascade',
    )
    date = fields.Date()
    project_id = fields.Many2one(
        comodel_name='project.project',
        string='Project',
    )
    task_id = fields.Many2one(
        comodel_name='project.task',
        string='Task',
    )
    unit_amount = fields.Float(
        string="Quantity",
        default=0.0,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Employee',
    )

    @api.multi
    def get_unique_id(self):
        """ Hook for extensions """
        self.ensure_one()
        return {
            'project_id': self.project_id,
            'task_id': self.task_id,
        }


class PlanningLine(models.TransientModel):
    _name = 'magnus.planning.line'
    _inherit = 'magnus.planning.line.abstract'
    _description = 'Planning Line'

    value_x = fields.Char(
        string='Date Name',
    )
    value_y = fields.Char(
        string='Project Name',
    )
    new_line_id = fields.Integer(
        default=0,
    )

    @api.onchange('unit_amount')
    def onchange_unit_amount(self):
        """ This method is called when filling a cell of the matrix. """
        self.ensure_one()
        sheet = self._get_sheet()
        if not sheet:
            return {'warning': {
                'title': _("Warning"),
                'message': _("Save the Timesheet Sheet first."),
            }}
        sheet.add_new_line(self)

    @api.model
    def _get_sheet(self):
        sheet = self.planning_id
        if not sheet:
            model = self.env.context.get('params', {}).get('model', '')
            obj_id = self.env.context.get('params', {}).get('id')
            if model == 'magnus.planning' and isinstance(obj_id, int):
                sheet = self.env['magnus.planning'].browse(obj_id)
        return sheet


class SheetNewAnalyticLine(models.TransientModel):
    _name = 'magnus.planning.new.analytic.line'
    _inherit = 'magnus.planning.line.abstract'
    _description = 'Magnus planning New Analytic Line'

    @api.model
    def _is_similar_analytic_line(self, aal):
        """ Hook for extensions """
        return aal.date == self.date \
            and aal.project_id.id == self.project_id.id \
            and aal.task_id.id == self.task_id.id

    @api.model
    def _update_analytic_lines(self):
        sheet = self.planning_id
        timesheets = sheet.planning_ids.filtered(
            lambda aal: self._is_similar_analytic_line(aal)
        )
        new_ts = timesheets.filtered(lambda t: t.name == empty_name)
        amount = sum(t.unit_amount for t in timesheets)
        diff_amount = self.unit_amount - amount
        if len(new_ts) > 1:
            new_ts = new_ts.merge_timesheets()
            sheet._sheet_write('planning_ids', sheet.planning_ids.exists())
        if not diff_amount:
            return
        if new_ts:
            unit_amount = new_ts.unit_amount + diff_amount
            if unit_amount:
                new_ts.write({'unit_amount': unit_amount})
            else:
                new_ts.unlink()
                sheet._sheet_write(
                    'planning_ids', sheet.planning_ids.exists())
        else:
            new_ts_values = sheet._prepare_new_line(self)
            new_ts_values.update({
                'name': empty_name,
                'unit_amount': diff_amount,
            })
            self.env['account.analytic.line']._planning_create(new_ts_values)
