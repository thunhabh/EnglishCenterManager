from odoo import models, fields, api
from odoo.exceptions import ValidationError

# model Assignment
class CenterAssignment(models.Model):
    _name = 'center.assignment'
    _description = 'Class Assignments & Materials'

    name = fields.Char(string="Title", required=True)
    class_id = fields.Many2one('center.class', string="Class", required=True)
    teacher_id = fields.Many2one('hr.employee', related='class_id.teacher_id', store=True, string="Teacher")

    description = fields.Char(string="Requirements")

    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")

    due_date = fields.Datetime(string="Deadline")
    submission_ids = fields.One2many('center.submission', 'assignment_id', string="Submissions")

    state_for_student = fields.Selection([
            ('submitted', 'Submitted'),
            ('pending', 'Pending'),
            ('overdue', 'Overdue'),
            ('graded', 'Graded')
    ], compute='_compute_states')

    state_for_teacher = fields.Selection([
            ('all_submitted', 'All Submitted'),
            ('partial', 'Partial'),
            ('overdue', 'Overdue'),
            ('finished', 'Finished')
    ], compute='_compute_states')

    def _compute_states(self):
        for record in self:
            user_id = self.env.user.id
            sub = record.submission_ids.filtered(lambda s: s.student_id.user_id.id == user_id)

            if sub:
                last_sub = sub[-1]

                if last_sub.score != -1:
                    record.state_for_student = 'graded'
                else:
                    record.state_for_student = 'submitted'

            elif record.due_date and record.due_date < fields.Datetime.now():
                record.state_for_student = 'overdue'
            else:
                record.state_for_student = 'pending'

            total_students = len(record.class_id.student_ids)
            submitted_count = len(record.submission_ids)
            graded_count = len(record.submission_ids.filtered(lambda s: s.score != -1))

            if graded_count == total_students and total_students > 0:
                record.state_for_teacher = 'finished'
            elif submitted_count == total_students and total_students > 0:
                record.state_for_teacher = 'all_submitted'
            elif record.due_date and record.due_date < fields.Datetime.now():
                record.state_for_teacher = 'overdue'
            else:
                record.state_for_teacher = 'partial'

    @api.constrains('due_date')
    def _check_due_date(self):
        for rec in self:
            if rec.due_date and rec.due_date.date() < fields.Date.today():
                raise ValidationError("Error: Due date can not be in the past!")


class CenterSubmission(models.Model):
    _name = 'center.submission'
    _description = 'Student Submissions'

    assignment_id = fields.Many2one('center.assignment', string="Assignment", required=True, ondelete='cascade')

    student_id = fields.Many2one('center.student', string="Student", required=True,
                                 default=lambda self: self._default_student())

    submission_file = fields.Binary(string='Submission File', required=True, attachment=False)
    file_name = fields.Char(string="File Name")

    submission_date = fields.Datetime(string="Submission date", default=fields.Datetime.now)

    download_url = fields.Char(string="Download Link", compute="_compute_download_url")

    score = fields.Float(string="Grade", default=-1)
    feedback = fields.Text(string="Teacher Feedback")

    def _default_student(self):
        if self.env.user.has_group('english_center.group_center_student'):
            student = self.env['center.student'].search([('user_id', '=', self.env.uid)], limit=1)
            return student.id
        return False

    def write(self, vals):
        if self.env.user.has_group('english_center.group_center_student'):
            if 'score' in vals or 'feedback' in vals:
                raise ValidationError("Security Alert: You cannot alter the teacher's grade or feedback!")

        if not self.env.user.has_group('english_center.group_center_student'):
            if 'submission_file' in vals or 'file_name' in vals:
                raise ValidationError(
                    "Security Alert: Teacher can't modify submission file or file name!")
        return super(CenterSubmission, self).write(vals)

    def _compute_download_url(self):
        for record in self:
            record_sudo = record.sudo()

            if record_sudo.submission_file:
                file_name_safe = record_sudo.file_name or 'student_submission.bin'
                record.download_url = f'/web/content/center.submission/{record.id}/submission_file/{file_name_safe}?download=true'
            else:
                record.download_url = "No file"

    @api.model
    def default_get(self, fields_list):
        # 1. Default
        res = super(CenterSubmission, self).default_get(fields_list)

        is_student = self.env.user.has_group('english_center.group_center_student')
        if is_student:
            assignments = self.env['center.assignment'].search([
                ('class_id.student_ids.user_id', '=', self.env.uid)
            ])

            if not assignments:
                raise ValidationError("Hiện tại bạn không có bài tập nào cần nộp!")

        return res