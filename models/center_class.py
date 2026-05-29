from datetime import timedelta, datetime, time

import pytz

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class CenterClass(models.Model):
    _name = 'center.class'
    _description = 'Manage Classes'

    #Name will be generated when create = The Course Template's Name + mm/yy
    name = fields.Char(string="Class Code", readonly=True, copy=False, default='New')
    course_id = fields.Many2one('center.course', string="Course", required=True)

    state = fields.Selection([
        ('recruiting', 'Recruiting'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], string="Status", default='recruiting')

    start_date = fields.Date(string="Start Date", required=True)
    end_date = fields.Date(string="End Date", readonly=True)

    schedule_ids = fields.One2many('center.class.schedule', 'class_id', string="Weekly Schedule")

    available_student_ids = fields.Many2many(
        'center.student',
        relation='class_available_student_rel',  # naming relation avoiding duplication
        compute='_compute_available_students'
    )

    student_ids = fields.Many2many(
        'center.student',
        string="Students",
        domain="[('id', 'in', available_student_ids)]"
    )
    session_ids = fields.One2many('class.session', 'class_id', string="Sessions Timeline")

    available_classroom_ids = fields.Many2many(
        'center.classroom',
        compute='_compute_available_classrooms'
    )
    classroom_id = fields.Many2one('center.classroom',
                                   string="Classroom",
                                   domain="[('id', 'in', available_classroom_ids)]")

    assignment_ids = fields.One2many('center.assignment', 'class_id', string="Assignments")

    available_teacher_ids = fields.Many2many('hr.employee', compute='_compute_available_teachers')
    teacher_id = fields.Many2one(
        'hr.employee',
        string="Teacher",
        domain="[('id', 'in', available_teacher_ids)]"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('course_id') and vals.get('start_date'):
                course = self.env['center.course'].browse(vals['course_id'])
                start_date = fields.Date.from_string(vals['start_date'])
                vals['name'] = f"{course.name} - {start_date.strftime('%m/%Y')}"
        return super(CenterClass, self).create(vals_list)

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_teachers(self):
        is_student = self.env.user.has_group('english_center.group_center_student')

        for record in self:
            if is_student:
                record.available_teacher_ids = False
                continue

        for record in self:
            all_teachers = self.env['hr.employee'].search([])

            if not record.schedule_ids:
                record.available_teacher_ids = all_teachers.ids
                continue

            qualified = []
            for teacher in all_teachers:
                is_overlap = False

                busy_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', '=', 'active'),
                    ('teacher_id', '=', teacher.id)
                ])

                for busy_class in busy_classes:
                    for busy_sched in busy_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(teacher.id)

            record.available_teacher_ids = qualified

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_classrooms(self):
        for record in self:
            all_classrooms = self.env['center.classroom'].search([])

            if not record.schedule_ids:
                record.available_classroom_ids = all_classrooms.ids
                continue

            qualified = []
            for aclass in all_classrooms:
                is_overlap = False

                here_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', '=', 'active'),
                    ('classroom_id', '=', aclass.id)
                ])

                for here_class in here_classes:
                    for busy_sched in here_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(aclass.id)

            record.available_classroom_ids = qualified

    @api.constrains('start_date')
    def _check_start_date(self):
        for record in self:
            if record.start_date and record.start_date < fields.Date.today():
                raise ValidationError("Error: Start date cannot be in the past.")

    def action_active_class(self):
        """ Generate physical sessions based on schedule lines and timezone """
        user_tz = pytz.timezone(self.env.user.tz or 'UTC')

        def float_to_time(f):
            h = int(f)
            m = int(round((f - h) * 60))
            if m == 60:
                h, m = h + 1, 0
            return time(hour=h, minute=m)

        for rec in self:
            if not rec.teacher_id:
                raise ValidationError("Please select a Teacher.")
            if not rec.schedule_ids:
                raise ValidationError("Please configure at least one schedule slot.")

            rec.state = 'active'
            rec.session_ids.unlink()

            current_date = rec.start_date
            session_count = 0

            while session_count < rec.course_id.total_sessions:
                weekday_str = str(current_date.weekday())
                # Find if current date matches any configured schedule day
                schedules = rec.schedule_ids.filtered(lambda s: s.day_of_week == weekday_str)

                for sched in schedules:
                    if session_count >= rec.course_id.total_sessions:
                        break
                    session_count += 1

                    # Convert to local timezone datetime
                    start_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.start_time)))
                    end_local = user_tz.localize(datetime.combine(current_date, float_to_time(sched.end_time)))

                    # Convert to UTC to store properly in Database
                    start_utc = start_local.astimezone(pytz.UTC).replace(tzinfo=None)
                    end_utc = end_local.astimezone(pytz.UTC).replace(tzinfo=None)

                    self.env['class.session'].create({
                        'class_id': rec.id,
                        'sequence': session_count,
                        'start_datetime': start_utc,
                        'end_datetime': end_utc,
                    })
                current_date += timedelta(days=1)

            rec.end_date = current_date - timedelta(days=1)

    @api.depends('schedule_ids.day_of_week', 'schedule_ids.start_time', 'schedule_ids.end_time')
    def _compute_available_students(self):
        for record in self:
            all_students = self.env['center.student'].search([])

            if not record.schedule_ids:
                record.available_student_ids = all_students.ids
                continue

            qualified = []
            for student in all_students:
                is_overlap = False

                # Find other classes that this student attending
                # 'Active' + 'Recuriting' classes
                busy_classes = self.env['center.class'].search([
                    ('id', '!=', record._origin.id if record._origin else record.id),
                    ('state', 'in', ['active', 'recruiting']),
                    ('student_ids', 'in', student.id)
                ])

                for busy_class in busy_classes:
                    for busy_sched in busy_class.schedule_ids:
                        for current_sched in record.schedule_ids:
                            if str(busy_sched.day_of_week) == str(current_sched.day_of_week):
                                if current_sched.start_time < busy_sched.end_time and current_sched.end_time > busy_sched.start_time:
                                    is_overlap = True
                                    break
                        if is_overlap: break
                    if is_overlap: break

                if not is_overlap:
                    qualified.append(student.id)

            record.available_student_ids = qualified

    def action_view_class_schedule(self):
        return {
            'name': f'Schedule: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'class.session',
            'view_mode': 'calendar,list',
            'domain': [('class_id', '=', self.id)],
            'context': {'default_class_id': self.id},
        }