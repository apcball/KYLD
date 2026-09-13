from odoo import fields, models


class JobCostSheet(models.Model):
    _inherit = 'job.cost.sheet'

    project_image = fields.Image(
        string='Project Photo', max_width=1920, max_height=1080,
        help='Upload a project photo to display on this cost sheet.',
    )
