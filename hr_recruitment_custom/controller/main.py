import logging
import requests
from odoo import http
from odoo.http import request
from odoo.http import Response
import json
import uuid
from odoo import http
from datetime import date
import base64
import hashlib
from odoo.osv.expression import AND
from odoo.tools import html2plaintext
_logger = logging.getLogger(__name__)

class JobRequestController(http.Controller):

    @staticmethod
    def _plain_text(value):
        """Convert HTML field values to text before serializing API responses."""
        return html2plaintext(value).strip() if value else None

    def _get_lang(self):
        lang = request.httprequest.headers.get('Accept-Language', 'ar_001')
        lang_record = request.env['res.lang'].sudo().search([('code', '=', lang)], limit=1)
        return lang_record.code if lang_record else 'ar_001'

    @http.route('/jobs-list', type='http', auth="bearer", crfs=False)
    def jobs_list(self, **values):
        headers = {'content-type':'application/json'}
        domain = [('is_published', '=', True)]
        try :
            lang = self._get_lang()
            Jobs = request.env['hr.job'].with_context(lang=lang)
            if values.get('company'):
                domain.append(('address_id.name', 'ilike', values.get('company')))
            '''if values.get('city'):
                domain.append(('address_id.city','=', values.get('city')))'''
            if values.get('job_name'):
                domain.append(('name','ilike', values.get('job_name')))
            '''if values.get('contract_type_id'):
                domain.append(('contract_type_id','=', int(values.get('contract_type_id'))))'''
            job_ids = Jobs.search(domain, order="is_published desc, sequence, no_of_recruitment desc")
            jobs_details = []
            for job in job_ids:
                job_ctx = job.with_context(lang=lang)
                if job.address_id.image_1920 :
                    logo = job.address_id.image_1920.decode("utf-8")
                else : 
                    logo = None
                res = {
                    'job_id': job.id,
                    'title': job_ctx.name,
                    'company' : job.address_id.name,
                    'company_logo' : logo,
                    'department' : {'id': job.department_id.id, 'name': job.department_id.name} if job.department_id else None,
                    'contract_type_id' : {'id': job.contract_type_id.id, 'name': job.contract_type_id.name} if job.contract_type_id else None,
                    'description': self._plain_text(job_ctx.description),
                }
                jobs_details.append(res)
            return Response(json.dumps(jobs_details),headers=headers)
            
        except Exception as e:
            _logger.error(e.__str__())
            response = Response(json.dumps({'message':{
                    'en': 'Internal server error ',
                    'ar': 'خطأ في السيرفر '
                    }}),headers=headers)
            response.status_code = 500
            return response
        
    @http.route('/jobs-details/<int:job_id>', type='http', auth="bearer", crfs=False)
    def job_details(self, job_id) :
        headers = {'content-type':'application/json'}
        
        try :
            lang = self._get_lang()
            job_id = request.env['hr.job'].with_context(lang=lang).search([('id', '=', job_id)])
            if job_id :
                if job_id.address_id.image_1920 :
                    logo = job_id.address_id.image_1920.decode("utf-8")
                else :
                    logo = None

                res = {
                        'job_id': job_id.id,
                        'title': job_id.name,
                        'company' : job_id.address_id.name or None,
                        'company_logo' : logo ,
                        'department': {'id': job_id.department_id.id, 'name': job_id.department_id.name} if job_id.department_id else None,
                        'contract_type_id' : {'id': job_id.contract_type_id.id, 'name': job_id.contract_type_id.name} if job_id.contract_type_id else None,
                        'description': self._plain_text(job_id.description),
                        'address': job_id.address_id.name or None,
                        'address_internal_note' : job_id.address_id.comment or None,
                        'responsibilities': job_id.responsibilities or None,
                        'requirements': job_id.requirements or None,
                        'degree_level':  dict(job_id._fields['degree_level']._description_selection(job_id.env)).get(job_id.degree_level) if job_id.degree_level else None,
                        'experience_years': job_id.experience_years or None,
                        'announcement_date': str(job_id.announcement_date) if job_id.announcement_date else None,
                        'closing_date' : str(job_id.closing_date) if job_id.closing_date else None,
                        'no_of_recruitment': job_id.no_of_recruitment or None,
                        'city': job_id.address_id.city or None,
                        'working_period': dict(job_id._fields['working_period']._description_selection(job_id.env)).get(job_id.working_period) if job_id.working_period else None,
                        'attendance_type': dict(job_id._fields['attendance_type']._description_selection(job_id.env)).get(job_id.attendance_type) if job_id.attendance_type else None,
                        'academic_degree': dict(job_id._fields['academic_degree']._description_selection(job_id.env)).get(job_id.academic_degree) if job_id.academic_degree else None,
                    }
                return Response(json.dumps(res),headers=headers)
            else :
                response = Response(json.dumps({"message": {
                            'error': 'Job not found',} }),
                            status=404,
                            headers=headers)
                return response
            
        except Exception as e:
            _logger.error(e.__str__())
            response = Response(json.dumps({'message':{
                    'en': 'Internal server error ',
                    'ar': 'خطأ في السيرفر '
                    }}),headers=headers)
            response.status_code = 500
            return response


    @http.route('/application_status', type='http', auth='bearer', methods=['GET'])
    def get_status(self, **values):
        headers = {'Content-Type': 'application/json'}
        applications = []

        try:
            lang = self._get_lang()
            nationality_no = request.httprequest.args.get('nationality_no')

            applicant_ids = request.env['hr.applicant'].sudo().search([
                ('candidate_id.nationality_no', '=', nationality_no),
                ('active', 'in', [True, False])
            ])

            if not applicant_ids:
                return Response(
                    json.dumps({
                        "message": {
                            "error": "لا يوجد طلبات تقديم"
                        }
                    }),
                    status=404,
                    headers=headers
                )

            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

            for applicant in applicant_ids:
                try:
                    # -------------------------------
                    # Base application data
                    # -------------------------------
                    logo = (
                        applicant.job_id.address_id.image_1920.decode("utf-8")
                        if applicant.job_id.address_id.image_1920
                        else None
                    )

                    job_ctx = applicant.job_id.with_context(lang=lang)
                    stage_ctx = applicant.stage_id.with_context(lang=lang) if applicant.stage_id else None

                    job_status = {
                        'application_id': applicant.id,
                        'job_position': job_ctx.name,
                        'company': applicant.job_id.address_id.name,
                        # 'company_logo': logo,
                        'create_date': str(applicant.create_date),
                        'status': stage_ctx.name if stage_ctx else None,
                        'refused': not applicant.active,
                    }

                    # -------------------------------
                    # Exam date stage
                    # -------------------------------
                    if applicant.stage_id and applicant.stage_id.exam_date_stage:
                        job_status.update({
                            'exam_date': str(applicant.exam_date) if applicant.exam_date else None,
                            'exam_center': {
                                'id': applicant.exam_center_id.id if applicant.exam_center_id else None,
                                'name': applicant.exam_center_id.name if applicant.exam_center_id else None,
                            },
                            'notes': applicant.notes or None,
                        })

                    # -------------------------------
                    # Exam stage (survey)
                    # -------------------------------
                    elif applicant.exam_stage and applicant.active:
                        exam_date = str(applicant.exam_date) if applicant.exam_date else None

                        try:
                            # Create survey answer only if none exists
                            if not applicant.response_ids:
                                applicant.sudo().write({
                                    'response_ids': (
                                        applicant.response_ids |
                                        applicant.job_id.exam_id.sudo()._create_answer(
                                            partner=applicant.partner_id,
                                            job_id=applicant.job_id.id,
                                        )
                                    ).ids
                                })

                            answer = applicant.response_ids.filtered(lambda r: r.state == 'new')
                            completed_answer = applicant.response_ids.filtered(lambda r: r.state == 'done')

                            if answer:
                                job_status.update({
                                    'exam_date': exam_date,
                                    'notes': applicant.notes or None,
                                    'survey': {
                                        'survey_id': applicant.job_id.exam_id.id,
                                        'survey_title': applicant.job_id.exam_id.title,
                                        'survey_url': '%s/survey/%s/%s' % (
                                            base_url,
                                            applicant.job_id.exam_id.access_token,
                                            answer[0].access_token
                                        )
                                    }
                                })

                            if completed_answer:
                                job_status.update({
                                    'exam_completed': True
                                })

                        except Exception as survey_error:
                            _logger.warning(
                                "Survey error for applicant %s: %s",
                                applicant.id,
                                survey_error
                            )
                            job_status.update({
                                'exam_available': False,
                                'exam_error': 'no_attempts_left'
                            })

                    # -------------------------------
                    # Interview stage
                    # -------------------------------
                    elif applicant.interview_stage:
                        job_status.update({
                            'interview_date': str(applicant.interview_date) if applicant.interview_date else None,
                            'notes': applicant.interview_notes or None,
                        })

                    applications.append(job_status)

                except Exception as applicant_error:
                    _logger.error(
                        "Applicant processing error (ID %s): %s",
                        applicant.id,
                        applicant_error
                    )
                    continue

            return Response(
                json.dumps(applications),
                status=200,
                headers=headers
            )

        except Exception as e:
            _logger.exception("Application status API failed")
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                status=500,
                headers=headers
            )
           
    # ── Specializations ────────────────────────────────────────────────────

    @http.route('/specializations', type='http', auth='bearer', methods=['GET'], csrf=False)
    def get_specializations(self, **values):
        """
        Return all active specializations for selection on the platform.
        Optional query param: ?name=comp  (case-insensitive name filter)
        """
        headers = {'Content-Type': 'application/json'}
        try:
            lang = self._get_lang()
            domain = [('active', '=', True)]
            if values.get('name'):
                domain.append(('name', 'ilike', values.get('name')))

            specs = request.env['candidate.specialization'].sudo().search(domain)
            data = [{'id': s.id, 'name': s.with_context(lang=lang).name} for s in specs]
            return Response(json.dumps(data), headers=headers, status=200)

        except Exception as e:
            _logger.error(str(e))
            return Response(
                json.dumps({'message': {'en': 'Internal server error', 'ar': 'خطأ في السيرفر'}}),
                headers=headers,
                status=500,
            )
    
    # Candidate Profile Creation and Update
    @http.route('/candidate-profile', type='http', auth="bearer", methods=['POST'], csrf=False)
    def create_candidate_profile(self, **values):
        """
        Create a new candidate profile.
        Accepts: nationality_no, name, birth_date, gender, email, phone,
                 nationality, certification, specialization_id, photo
        """
        headers = {'content-type':'application/json'}
        try :
            if values.get('birth_date'):
                birth_date = str(values.get('birth_date'))
            else :
                birth_date = None
            candidate = {
                    'nationality_no': values.get('nationality_no'),
                    'partner_name' : values.get('name'),
                    'birth_date': birth_date,
                    'gender': values.get('gender') or None,
                    'email_from': values.get('email') or None,
                    'partner_phone': values.get('phone') or None,
                    'nationality' : values.get('nationality') or None,
                }
            candidate_id = request.env['hr.candidate'].sudo().search([('nationality_no','=', values.get('nationality_no'))])
            if candidate_id :
                response = Response(json.dumps({'message':{
                        'error': 'Candidate with this National ID already exists.',
                        'candidate_id' : candidate_id.id
                        }}),headers=headers)
                response.status_code = 400
                return response
            candidate_id = request.env['hr.candidate'].sudo().create(candidate)
            picture_path = values.get('photo')
            if picture_path:
                candidate_id.sudo().write({'image_url': picture_path})
                # if picture is hosted remotely
                if picture_path.startswith("https"):
                    response = requests.get(picture_path)
                    if response.status_code == 200:
                        file_content = response.content
                    else:
                        file_content = None
                else:
                    # if local path on server
                    try:
                        with open("/var/www/html" + picture_path, "rb") as f:
                            file_content = f.read()
                    except Exception:
                        file_content = None

                if file_content:
                    photo_data = base64.b64encode(file_content)
                    candidate_id.sudo().write({'image_1920': photo_data})
                    candidate_id.partner_id.sudo().write({'image_1920': photo_data})
                    
            response = Response(json.dumps({"message": {
                        'success': 'Candidate profile created successfully.',
                        'candidate_id': candidate_id.id
                        } }),headers=headers)
            response.status_code = 201
            return response

        except Exception as e:
            _logger.error(e.__str__())
            response = Response(json.dumps({'message':{
                    'en': 'Internal server error ',
                    'ar': 'خطأ في السيرفر '
                    }}),headers=headers)
            response.status_code = 500
            return response

    @http.route('/candidate-profile', type='http', auth="bearer", methods=['PUT'], csrf=False)
    def update_candidate_profile(self, **values):
        """
        Update candidate profile — main info, education, experience, languages.
        Accepts top-level: certification, specialization_id
        Each education entry accepts: specialization_id, certification, university,
                                      graduation_year, graduation_month, university_location
        """
        headers = {'content-type':'application/json'}
        try:
            candidate_id = request.env['hr.candidate'].sudo().search([('id','=', values.get('candidate_id'))])
            if not candidate_id:
                response = Response(
                    json.dumps({"message": {'error': 'Candidate not found'}}),
                    status=404,
                    headers=headers
                )
                return response

            # Update main candidate fields
            candidate_vals = {
                'residence_country': values.get('residence_country') or None,
                'residence_city': values.get('residence_city') or None,
                'nationality': values.get('nationality') or None,
                'partner_phone': values.get('phone') or None,
            }
            candidate_id.write(candidate_vals)

            # Update Education (multiple)
            request.env['candidate.education'].sudo().search([
                ('candidate_id', '=', candidate_id.id)
            ]).unlink()
            educations = json.loads(values.get('education')) if isinstance(values.get('education'), str) else []
            for edu in educations:
                request.env['candidate.education'].sudo().create({
                    'candidate_id': candidate_id.id,
                    'university': edu.get('university'),
                    'graduation_year': edu.get('graduation_year'),
                    'graduation_month': edu.get('graduation_month'),
                    'specialization_id': int(edu.get('specialization_id')) if edu.get('specialization_id') else None,
                    'certification': edu.get('certification'),
                    'university_location': edu.get('university_location'),
                })

            # Update Work Experience (multiple)
            request.env['candidate.work.experience'].sudo().search([
                ('candidate_id', '=', candidate_id.id)
            ]).unlink()
            experiences = json.loads(values.get('experience')) if isinstance(values.get('experience'), str) else []
            for exp in experiences:
                request.env['candidate.work.experience'].sudo().create({
                    'candidate_id': candidate_id.id,
                    'company_name': exp.get('company_name'),
                    'job_title': exp.get('job_title'),
                    'start_date': str(exp.get('start_date')),
                    'end_date': str(exp.get('end_date')),
                    'country': exp.get('country'),
                    'city': exp.get('city'),
                })

            # Update Languages (multiple)
            request.env['candidate.language'].sudo().search([
                ('candidate_id', '=', candidate_id.id)
            ]).unlink()
            languages = json.loads(values.get('languages')) if isinstance(values.get('languages'), str) else []
            for lang in languages:
                request.env['candidate.language'].sudo().create({
                    'candidate_id': candidate_id.id,
                    'language_name': lang.get('language_name'),
                    'proficiency': lang.get('proficiency'),
                })

            # Response
            response = Response(
                json.dumps({
                    "message": {
                        'success': 'Candidate profile updated successfully.',
                        'candidate_id': candidate_id.id
                    }
                }),
                headers=headers
            )
            response.status_code = 200
            return response

        except Exception as e:
            _logger.error(str(e))
            response = Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=headers
            )
            response.status_code = 500
            return response
        
    @http.route('/candidate/<int:candidate_id>',type='http',auth='bearer',methods=['GET'],csrf=False)
    def get_candidate_profile(self, candidate_id, **values):
        headers = [('Content-Type', 'application/json')]
        try :
            candidate = request.env['hr.candidate'].sudo().browse(candidate_id)

            if not candidate:
                return request.make_response(
                    json.dumps({'error': 'Candidate not found'}),
                    headers=headers,
                    status=404
                )

            data = candidate.candidate_data()

            return request.make_response(
                json.dumps(data),
                headers=headers,
                status=200
            )
        except Exception as e:
            _logger.error(str(e))
            response = Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=headers
            )
            response.status_code = 500
            return response
        
    @http.route('/candidate-attachments', type='http', auth='bearer', methods=['POST'], csrf=False)
    def upload_candidate_attachments(self, candidate_id, **values):
        """
        Upload CV and certificates as attachments to candidate record
        """
        try:
            candidate = request.env['hr.candidate'].sudo().browse(int(candidate_id))
            if not candidate.exists():
                return Response(
                    json.dumps({'error': 'Candidate not found'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            files = request.httprequest.files
            if not files:
                return Response(
                    json.dumps({'error': 'No files uploaded'}),
                    headers=[('Content-Type', 'application/json')],
                    status=400
                )

            attachment_ids = []
            for uploaded_file in files.getlist('files'):
                attachment = request.env['ir.attachment'].sudo().create({
                                        'name': uploaded_file.filename,
                                        'res_model': 'hr.candidate',
                                        'res_id': candidate.id,
                                        'type': 'binary',
                                        'datas': base64.b64encode(uploaded_file.read()),
                                        'mimetype': uploaded_file.mimetype,
                                    })
                attachment_ids.append(attachment.id)

            return Response(
                json.dumps({
                    'message': 'Attachments uploaded successfully',
                    'attachment_ids': attachment_ids
                }),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.exception(e)
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
        
    @http.route('/candidate-attachments', type='http', auth='bearer', methods=['GET'], csrf=False)
    def get_candidate_attachments(self, candidate_id, **values):
        try:
            candidate = request.env['hr.candidate'].sudo().browse(int(candidate_id))
            if not candidate.exists():
                return Response(
                    json.dumps({'error': 'Candidate not found'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            attachments = request.env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.candidate'),
                ('res_id', '=', candidate.id)
            ])

            data = []
            for att in attachments:
                data.append({
                    'id': att.id,
                    'name': att.name,
                    'mimetype': att.mimetype,
                    'create_date': str(att.create_date),
                    'url': f"/web/content/{att.id}?download=true"
                })

            return Response(
                json.dumps({
                    'candidate_id': candidate.id,
                    'attachments': data
                }),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.exception(e)
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
        
    @http.route('/candidate-attachment', type='http',
                auth='bearer', methods=['DELETE'], csrf=False)
    def delete_candidate_attachment(self, attachment_id, candidate_id, **kwargs):
        try:
            attachment = request.env['ir.attachment'].sudo().browse(int(attachment_id))
            if not attachment :
                return Response(
                    json.dumps({'error': 'Attachment not found'}),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )

            # Security check: ensure attachment belongs to candidate
            if attachment.res_model != 'hr.candidate' or attachment.res_id != int(candidate_id):
                return Response(
                    json.dumps({'error': 'Attachment does not belong to candidate'}),
                    headers=[('Content-Type', 'application/json')],
                    status=403
                )

            attachment.unlink()

            return Response(
                json.dumps({
                    'message': 'Attachment deleted successfully',
                    'attachment_id': attachment_id
                }),
                headers=[('Content-Type', 'application/json')],
                status=200
            )

        except Exception as e:
            _logger.exception(e)
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

        
    @http.route('/job-apply', type='http', auth="bearer", methods=['POST'], csrf=False)
    def job_apply(self, **values):
        """
        Apply to a job on behalf of a candidate
        """
        import time
        headers = {'content-type': 'application/json'}
        t_start = time.perf_counter()

        def elapsed(label, t_ref=None):
            now = time.perf_counter()
            since_ref = f" (+{(now - t_ref)*1000:.1f}ms since last)" if t_ref else ""
            _logger.info(f"[job_apply] ⏱ {label}: {(now - t_start)*1000:.1f}ms total{since_ref}")
            return now

        try:
            t0 = elapsed("start")

            job_id = int(values.get('job_id'))
            candidate_id = int(values.get('candidate_id'))
            t0 = elapsed(f"parsed params — job_id={job_id}, candidate_id={candidate_id}", t0)

            Applicant = request.env['hr.applicant'].sudo()
            t0 = elapsed("sudo() env resolved", t0)

            job = request.env['hr.job'].sudo().browse(job_id).exists()
            if not job:
                return Response(
                    json.dumps({
                        'message': {
                            'ar': 'الوظيفة المطلوبة غير موجودة',
                            'en': 'The requested job does not exist.'
                        }
                    }),
                    headers=headers,
                    status=404
                )

            # A candidate may have one active application for an entity, even
            # when that entity has several advertised job positions.
            application_domain = [
                ('candidate_id', '=', candidate_id),
                ('active', '!=', False),
            ]
            if job.address_id:
                application_domain.append(('job_id.address_id', '=', job.address_id.id))
            else:
                # Keep the existing duplicate protection for jobs that have no
                # entity/address configured.
                application_domain.append(('job_id', '=', job.id))

            previous_applicant = Applicant.search(application_domain, limit=1)
            t0 = elapsed(f"search() done — found={bool(previous_applicant)}", t0)

            if previous_applicant:
                elapsed("returning 400 — duplicate entity application")
                return Response(
                    json.dumps({
                        'message': {
                            'ar': 'لا يمكن التقديم على أكثر من وظيفة واحدة لدى الجهة نفسها إلا في حالة الرفض.',
                            'en': 'You have already applied for a job at this entity.'
                        }
                    }),
                    headers=headers,
                    status=400
                )

            applicant = Applicant.create({
                'job_id': job_id,
                'candidate_id': candidate_id,
            })
            t0 = elapsed(f"create() done — applicant_id={applicant.id}", t0)

            elapsed("returning 200 — success")
            return Response(
                json.dumps({
                    "message": {
                        'success': 'Application submitted successfully.',
                        'applicant_id': applicant.id
                    }
                }),
                headers=headers,
                status=200
            )

        except Exception as e:
            elapsed("exception raised")
            _logger.exception(e)
            return Response(
                json.dumps({
                    'message': {
                        'en': 'Internal server error',
                        'ar': 'خطأ في السيرفر'
                    }
                }),
                headers=headers,
                status=500
            )

    ## News API
    @http.route('/news-list', type='http', auth="bearer", csrf=False, methods=['GET'])
    def news_list(self, **values):
        headers = {'content-type': 'application/json'}
        try:
            lang = self._get_lang()
            News = request.env['news.news'].sudo()
            domain = [('is_published', '=', True)]
            news_ids = News.search(domain, order='create_date desc')
            news_details = []
            for news in news_ids:
                news_ctx = news.with_context(lang=lang)
                if news.image:
                    image = news.image.decode("utf-8")
                else:
                    image = None
                res = {
                    'news_id': news.id,
                    'title': news_ctx.title,
                    'content': news_ctx.content or None,
                    'image': image,
                }
                news_details.append(res)
            return Response(json.dumps(news_details), headers=headers)
 
        except Exception as e:
            _logger.error(e.__str__())
            response = Response(json.dumps({'message':{
                    'en': 'Internal server error ',
                    'ar': 'خطأ في السيرفر '
                    }}),headers=headers)
            response.status_code = 500
            return response
