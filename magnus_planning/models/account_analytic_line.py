# Copyright 2018 Eficent Business and IT Consulting Services, S.L.
# Copyright 2018-2019 Brainbean Apps (https://brainbeanapps.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountAnalyticLine(models.Model):
    _inherit = 'account.analytic.line'

    
    planning_id = fields.Many2one(
        comodel_name='magnus.planning',
        string='Planning_id',
    )
    week_id = fields.Many2one('date.range',string="Week")

   
    @api.model
    def _planning_create(self, values):
        return self.with_context(planning_create=True).create(values)
