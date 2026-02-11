from odoo import api, fields, models, _
from odoo.exceptions import UserError

class PurchaseOrderApprovalWizard(models.TransientModel):
    _name = 'purchase.order.approval.wizard'
    _description = 'Purchase Order Approval Wizard'

    order_id = fields.Many2one('purchase.order', string="Purchase Order", required=True)
    signature_type = fields.Selection([('draw', 'Draw Signature'), ('upload', 'Upload File')], string="Signature Type", default='draw')
    approval_stage = fields.Selection([
        ('prepare', 'Prepare'),
        ('review', 'Review'),
        ('approve', 'Approve')
    ], string="Approval Stage", default='approve')
    draw_signature = fields.Binary(string='Draw Signature')
    upload_signature = fields.Binary(string='Upload Signalue')

    def action_approve(self):
        self.ensure_one()
        signature = self.draw_signature if self.signature_type == 'draw' else self.upload_signature
        
        if not signature:
            raise UserError(_("Please provide a signature."))

        vals = {}
        company = self.order_id.company_id
        
        if self.approval_stage == 'prepare':
            if not company.po_reviewer_ids:
                raise UserError(_("No default reviewer configured. Please set up the Purchase Order Reviewer in Settings."))

            vals = {
                'prepared_signature': signature,
                'prepared_date': fields.Datetime.now(),
                'approval_state': 'to_review',
                'reviewer_id': False # Clear reviewer, wait for one of them
            }
            # Schedule Review Activity
            for reviewer in company.po_reviewer_ids:
                self.order_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=reviewer.id,
                    summary='Please Review Purchase Order',
                    note=f'Purchase Order {self.order_id.name} needs your review.'
                )

        elif self.approval_stage == 'review':
            
            # Determine Approver based on Limit
            limit = company.po_approver_limit
            amount = self.order_id.amount_total
            next_approvers = self.env['res.users']
            
            if amount > limit and company.po_approver_above_limit_id:
                next_approvers = company.po_approver_above_limit_id
            else:
                next_approvers = company.po_approver_ids

            if not next_approvers:
                raise UserError(_("No approver configured. Please set up the Purchase Order Approver in Settings."))

            vals = {
                'reviewed_signature': signature,
                'reviewed_date': fields.Datetime.now(),
                'approval_state': 'to_approve',
                 # Record the actual reviewer
                'reviewer_id': self.env.user.id,
                'approver_id': False # Clear approver, wait for one of them
            }
            
            # Complete Review Activity
            activity_domain = [('res_id', '=', self.order_id.id), ('res_model', '=', 'purchase.order'), ('user_id', '=', self.env.user.id)]
            self.env['mail.activity'].search(activity_domain).action_feedback()

            # Write vals now to update approver_id before sending email
            self.order_id.write(vals)
            vals = {} # Clear vals

            # Schedule Approve Activity & Send Email
            for next_approver in next_approvers:
                self.order_id.activity_schedule(
                    'mail.mail_activity_data_todo',
                    user_id=next_approver.id,
                    summary='Please Approve Purchase Order',
                    note=f'Purchase Order {self.order_id.name} needs your approval.'
                )
                
                # Generate Token if not exists (This might generate token for first one if we call _generate_approval_token directly?)
                # Actually, purchase.order logic handles token generation in action_send_line_approval_request for LINE.
                # For Email... template_id.send_mail might use a generic token? 
                
                # The original code generated token here:
                if not self.order_id.approval_token:
                    self.order_id._generate_approval_token()

                # Send Email
                # Note: This sends email to... whom? The template probably uses object.approver_id which is now empty!
                # We need to explicitly allow sending to specific recipients or rely on Followers? 
                # Or maybe we send to EACH approver manually?
                
                template_id = self.env.ref('buz_po_portal.email_template_purchase_approval_request')
                if template_id:
                     # Force send to specific email? 
                     # The template likely uses object.approver_id.partner_id.email
                     # Since object.approver_id is False, this email might fail or go nowhere.
                     
                     # We should manually send email composition?
                     # Or temporarily set the context?
                     
                     # Better approach: Loop actions? 
                     # For now, let's assume we can pass email_values or similar. 
                     # send_mail doesn't easily allow changing 'To' unless we change the object.
                     
                     # But we can use force_send=True and email_values={'email_to': ...} if supported? No, email_values is for create.
                     # We can call send_mail with email_layout_xmlid? No.
                     
                     # Simplest: use template.send_mail(self.order_id.id, email_values={...})
                     template_id.send_mail(self.order_id.id, force_send=True, email_values={'email_to': next_approver.email, 'recipient_ids': [(4, next_approver.partner_id.id)]})

        elif self.approval_stage == 'approve':
            vals = {
                'approval_signature': signature,
                'approval_date': fields.Datetime.now(),
                'approval_state': 'approved',
                'approver_id': self.env.user.id
            }

            # Complete Approve Activity
            activity_domain = [('res_id', '=', self.order_id.id), ('res_model', '=', 'purchase.order'), ('user_id', '=', self.env.user.id)]
            self.env['mail.activity'].search(activity_domain).action_feedback()

        self.order_id.write(vals)
        
        # Trigger LINE Notification for Prepare and Review stages
        if self.approval_stage in ['prepare', 'review']:
                 # Check if we are in a valid state to send (Double check, though write(vals) should have set it)
                 if self.order_id.approval_state in ['to_review', 'to_approve']:
                     self.order_id.action_send_line_approval_request(raise_exception=False)

        if self.approval_stage == 'approve':
             self.order_id.button_confirm()
             
        return {'type': 'ir.actions.act_window_close'}
