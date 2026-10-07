from odoo import models, fields
from datetime import date

import uuid

class HrCandidate(models.Model):
    _name = 'hr.candidate'
    _inherit = ['hr.candidate','image.mixin']

    nationality_no = fields.Char(string='National ID Number', help='The national identification number of the candidate.')
    birth_date = fields.Date(string='Birth Date', help='The birth date of the candidate.')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
    ], string='Gender', help='The gender of the candidate.')
    residence_country = fields.Char(
        string='Country of Residence',
        help='The country where the candidate resides.'
    )
    residence_city = fields.Char(string='City of Residence', help='The city where the candidate resides.')
    nationality = fields.Char(
        string='Nationality',
        help='The nationality of the candidate.'
    )
    language_ids = fields.One2many(
        'candidate.language', 'candidate_id'
    )
    education_ids = fields.One2many(
        'candidate.education', 'candidate_id'
    )
    experience_ids = fields.One2many(
        'candidate.work.experience', 'candidate_id'
    )

    total_experience_years = fields.Float(
    string='Total Experience (Years)',
    compute='_compute_total_experience_years',
)
    image_url = fields.Char(
        string='Image URL',
    )

    selection_decision_ids = fields.Many2many(
        'hr.selection.decision',
        string='Selection Decisions',
        compute='_compute_selection_decision_ids',
    )
    selection_decision_count = fields.Integer(
        string='Selection Decision Count',
        compute='_compute_selection_decision_ids',
    )

    def _compute_selection_decision_ids(self):
        for candidate in self:
            decisions = self.env['hr.selection.decision'].search([
                ('applicant_ids.candidate_id', '=', candidate.id)
            ])
            candidate.selection_decision_ids = decisions
            candidate.selection_decision_count = len(decisions)
    
    def _compute_total_experience_years(self):
        for candidate in self:
            total_days = 0
            for exp in candidate.experience_ids:
                if not exp.start_date:
                    continue

                end_date = exp.end_date or date.today()

                # Guard against inverted dates (bad data entry) —
                # never let a single entry contribute negative duration.
                if end_date < exp.start_date:
                    continue

                total_days += (end_date - exp.start_date).days

            candidate.total_experience_years = total_days / 365.0

    def candidate_data(self):
        self.ensure_one()
        photo = None
        if self.partner_id and self.partner_id.image_1920:
            photo = self.partner_id.image_1920.decode("utf-8")
        return {
            'id': self.id,
            'name': self.partner_name,
            'photo' : self.image_url if self.image_url else None,
            'nationality_no': self.nationality_no,
            'birth_date': self.birth_date.isoformat() if self.birth_date else None,
            'gender': self.gender,
            'email' : self.email_from,
            'phone' : self.partner_phone,
            'residence_country': self.residence_country,
            'residence_city': self.residence_city,
            'nationality': self.nationality,

            'languages': [
                {
                    'language_name': lang.language_name,
                    'proficiency': lang.proficiency,
                }
                for lang in self.language_ids
            ],

            'education': [
                {
                    'university': edu.university,
                    'graduation_year': edu.graduation_year,
                    'graduation_month': edu.graduation_month,
                    'specialization': {
                        'id': edu.specialization_id.id,
                        'name': edu.specialization_id.name,
                    } if edu.specialization_id else None,
                    'certification': edu.certification,
                    'university_location': edu.university_location,
                }
                for edu in self.education_ids
            ],

            'experience': [
                {
                    'company_name': exp.company_name,
                    'job_title': exp.job_title,
                    'start_date': exp.start_date.isoformat() if exp.start_date else None,
                    'end_date': exp.end_date.isoformat() if exp.end_date else None,
                    'country': exp.country,
                    'city': exp.city,
                }
                for exp in self.experience_ids
            ],
        }
    


class CandidateLanguage(models.Model):
    _name = 'candidate.language'
    _description = 'Candidate Language'

    candidate_id = fields.Many2one(
        'hr.candidate', ondelete='cascade', required=True
    )

    language_name = fields.Char(required=True)
    proficiency = fields.Selection([
        ('native', 'Native'),
        ('fluent', 'Fluent'),
        ('advanced', 'Advanced'),
        ('intermediate', 'Intermediate'),
        ('beginner', 'Beginner'),
    ],
    string='Proficiency',
    help='Language proficiency level',
)

class CandidateEducation(models.Model):
    _name = 'candidate.education'
    _description = 'Candidate Education'

    def _get_graduation_years(self):
        current_year = date.today().year
        return [(str(year), str(year)) for year in range(current_year, current_year - 51, -1)]

    candidate_id = fields.Many2one(
        'hr.candidate', ondelete='cascade', required=True
    )

    university = fields.Char(string='University', help='The university attended by the candidate.')
    graduation_year = fields.Selection(
        selection=_get_graduation_years,
        string='Graduation Year',
        help='The year the candidate graduated.'
    )
    graduation_month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Graduation Month', help='The month the candidate graduated.')


    specialization_id = fields.Many2one(
        'candidate.specialization',
        string='Specialization',
        ondelete='set null',
        help="The candidate's field of specialization.",
    )
    certification = fields.Selection([
        ('high_school', 'High School'),
        ('diploma', 'Diploma'),
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('phd', 'PhD'),
    ],
    string='Certification',
    help='Certification obtained by the candidate.',
)  
    university_location = fields.Char(string='University Location', help='Location of the university attended by the candidate.')
    

class CandidateWorkExperience(models.Model):
    _name = 'candidate.work.experience'
    _description = 'Candidate Work Experience'

    candidate_id = fields.Many2one('hr.candidate', string='Candidate', required=True, ondelete='cascade')
    company_name = fields.Char(string='Company Name', help='The name of the company where the candidate worked.')
    start_date = fields.Date(string='Start Date', help='The start date of the work experience.')
    end_date = fields.Date(string='End Date', help='The end date of the work experience.')
    country = fields.Char(string='Country', help='The country where the work experience took place.')
    city = fields.Char(string='City', help='The city where the work experience took place.')
    job_title = fields.Char(string='Job Title', help='The title of the job held during this work experience.')

class CandidateSpecialization(models.Model):
    """
    Master list of specializations managed by the admin.
    Candidates and filter wizards reference this model via Many2one.
    """
    _name = 'candidate.specialization'
    _description = 'Candidate Specialization'
    _order = 'name asc'
 
    name = fields.Char(string='Specialization', required=True, translate=True)
    active = fields.Boolean(default=True)
 
    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Specialization name must be unique.'),
    ]