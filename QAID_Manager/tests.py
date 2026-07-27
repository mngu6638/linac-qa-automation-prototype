import json
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .film_constants import (
    FIELD_SIZE_ANALYSIS_KEY,
    GANTRY_ANALYSIS_KEY,
    SESSION_LATEST_PATHS_KEY,
)
from .models import Linac, QARecord, QASchedule, QATest, QAStatus
from .statistics_service import (
    StatisticsFilters,
    StatisticsService,
    CLASSIFICATION_FAILED,
    CLASSIFICATION_NORMAL,
    CLASSIFICATION_WARNING,
)
from .qa_test_mapping import get_storage_field
from .session_hooks import RUNTIME_SESSION_KEY
from .views.film_views import _clear_session_keys, _drop_latest_analysis_path, _set_latest_analysis_path
from .services import QAScheduleService
from .film_parameters_service import (
    DEFAULT_FIELD_SIZE_BAND_WIDTH_MM,
    DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD,
    band_width_mm_to_pixels,
    compute_station_line_count,
    deduplicate_film_analysis_parameters,
    get_field_size_band_width_mm,
    get_field_size_detection_threshold,
)
from .models import PhysicsParameters
from .forms import PhysicsParametersForm

RUNTIME_MIDDLEWARE = list(settings.MIDDLEWARE)
if 'QAID_Manager.middleware.RuntimeBoundSessionMiddleware' not in RUNTIME_MIDDLEWARE:
    auth_index = RUNTIME_MIDDLEWARE.index('django.contrib.auth.middleware.AuthenticationMiddleware')
    RUNTIME_MIDDLEWARE.insert(auth_index + 1, 'QAID_Manager.middleware.RuntimeBoundSessionMiddleware')


class PortConfigTests(TestCase):
    def test_resolve_listen_port_finds_localhost_port(self):
        from QAID_Manager.port_config import resolve_listen_port

        port = resolve_listen_port('127.0.0.1')
        self.assertGreaterEqual(port, 1024)
        self.assertLessEqual(port, 65535)

    def test_default_candidates_avoid_8000(self):
        from QAID_Manager.port_config import DEFAULT_PORT_CANDIDATES

        self.assertNotIn(8000, DEFAULT_PORT_CANDIDATES)
        self.assertEqual(DEFAULT_PORT_CANDIDATES[0], 17890)


class SecurityAccessTests(TestCase):
    def test_shutdown_endpoint_works_in_desktop_mode_without_login(self):
        response = self.client.post(reverse('shutdown_app'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_shutdown_endpoint_ignored_in_server_mode(self):
        import os
        previous = os.environ.get('QAID_SERVER_MODE')
        os.environ['QAID_SERVER_MODE'] = '1'
        try:
            response = self.client.post(reverse('shutdown_app'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'ignored')
        finally:
            if previous is None:
                os.environ.pop('QAID_SERVER_MODE', None)
            else:
                os.environ['QAID_SERVER_MODE'] = previous

    def test_assign_performers_requires_authentication(self):
        response = self.client.post(
            reverse('assign_performers'),
            data=json.dumps({'schedule_id': 1}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

class QAScheduleServiceTests(TestCase):
    def test_create_schedule_builds_expected_record(self):
        linac = Linac.objects.create(name='Linac A')
        schedule = QAScheduleService.create_schedule(
            date_str='2026-05-01',
            linac_id=linac.id,
            performer1_id=None,
            performer2_id=None,
        )

        self.assertEqual(schedule.linac_id, linac.id)
        self.assertEqual(schedule.month_year, date(2026, 5, 1))
        self.assertIn('Linac A', schedule.qa_reason)

    def test_update_schedule_notes_appends_history(self):
        linac = Linac.objects.create(name='Linac B')
        user = User.objects.create_user(username='note_user', password='pass1234')
        schedule = QASchedule.objects.create(linac=linac, month_year=date(2026, 5, 1), notes='old')

        updated = QAScheduleService.update_schedule_notes(
            schedule_id=schedule.id,
            new_notes='new notes',
            user=user,
            ip_address='127.0.0.1',
        )

        self.assertEqual(updated.notes, 'new notes')
        self.assertEqual(len(updated.notes_edit_history), 1)
        self.assertEqual(updated.notes_edit_history[0]['old_notes'], 'old')
        self.assertEqual(updated.notes_edit_history[0]['new_notes'], 'new notes')


class FilmSessionHelperTests(TestCase):
    class _Request:
        def __init__(self, session):
            self.session = session

    def test_set_latest_analysis_path_initializes_session_dict(self):
        request = self._Request(session={SESSION_LATEST_PATHS_KEY: 'invalid'})
        _set_latest_analysis_path(request, FIELD_SIZE_ANALYSIS_KEY, '/tmp/result.png')
        self.assertEqual(
            request.session[SESSION_LATEST_PATHS_KEY][FIELD_SIZE_ANALYSIS_KEY],
            '/tmp/result.png',
        )

    def test_drop_latest_analysis_path_removes_only_target_key(self):
        request = self._Request(
            session={
                SESSION_LATEST_PATHS_KEY: {
                    FIELD_SIZE_ANALYSIS_KEY: '/tmp/field.png',
                    GANTRY_ANALYSIS_KEY: '/tmp/gantry.png',
                }
            }
        )
        _drop_latest_analysis_path(request, FIELD_SIZE_ANALYSIS_KEY)
        self.assertNotIn(FIELD_SIZE_ANALYSIS_KEY, request.session[SESSION_LATEST_PATHS_KEY])
        self.assertIn(GANTRY_ANALYSIS_KEY, request.session[SESSION_LATEST_PATHS_KEY])

    def test_clear_session_keys_is_idempotent(self):
        request = self._Request(session={'film_cropped': True})
        _clear_session_keys(request, 'film_cropped', 'missing_key')
        self.assertNotIn('film_cropped', request.session)


class StatisticsAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='stats_user', password='pass1234')
        self.linac = Linac.objects.create(name='Stats Linac', energy=['6MV'])

    def test_anonymous_redirects_from_statistics(self):
        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_authenticated_user_can_access_statistics(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Statistics')


class StatisticsServiceTests(TestCase):
    def setUp(self):
        self.linac = Linac.objects.create(name='L1', energy=['6MV', '10MV'])
        self.test_symmetry = QATest.objects.create(
            name='Symmetry',
            test_type='beam',
            tolerance_value=3.0,
            tolerance_unit='%',
            order_index=17,
            is_active=True,
        )
        self.test_mechanical = QATest.objects.create(
            name='Field light',
            test_type='mechanical',
            tolerance_value=1.0,
            tolerance_unit='mm',
            order_index=1,
            is_active=True,
        )
        self.status = QAStatus.objects.create(name='passed', color='#00ff00')
        self.user = User.objects.create_user(username='physicist', password='pass')

    def _make_record(self, **kwargs):
        date_performed = kwargs.pop('date_performed', date(2026, 5, 10))
        defaults = dict(
            linac=self.linac,
            performed_by=self.user,
            status=self.status,
            is_draft=False,
            test_01=0.5,
            beam_test_results={
                '6MV': {'test_17': 1.2},
                '10MV': {'test_17': 2.8},
            },
        )
        defaults.update(kwargs)
        record = QARecord.objects.create(**defaults)
        QARecord.objects.filter(pk=record.pk).update(date_performed=date_performed)
        record.refresh_from_db()
        return record

    def test_draft_excluded_by_default(self):
        self._make_record(is_draft=True, test_01=5.0)
        final = self._make_record(test_01=0.5)
        filters = StatisticsFilters(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        qs = StatisticsService.build_queryset(filters)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().id, final.id)

    def test_date_filtering(self):
        self._make_record(date_performed=date(2025, 1, 1))
        self._make_record(date_performed=date(2026, 5, 10))
        filters = StatisticsFilters(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        self.assertEqual(StatisticsService.build_queryset(filters).count(), 1)

    def test_scalar_extraction(self):
        record = self._make_record(test_01=0.8)
        pt = StatisticsService.extract_point(record, self.test_mechanical)
        self.assertIsNotNone(pt)
        self.assertEqual(pt['value'], 0.8)
        self.assertEqual(get_storage_field(1), 'test_01')

    def test_beam_extraction(self):
        record = self._make_record()
        pt = StatisticsService.extract_point(
            record, self.test_symmetry, energy='6MV'
        )
        self.assertIsNotNone(pt)
        self.assertEqual(pt['value'], 1.2)
        self.assertEqual(pt['source_type'], 'beam_json')

    def test_classification_boundaries(self):
        self.assertEqual(
            StatisticsService.classify_value(1.0, 3.0, 17),
            CLASSIFICATION_NORMAL,
        )
        self.assertEqual(
            StatisticsService.classify_value(3.1, 3.0, 17),
            CLASSIFICATION_WARNING,
        )
        self.assertEqual(
            StatisticsService.classify_value(3.6, 3.0, 17),
            CLASSIFICATION_FAILED,
        )
        self.assertEqual(
            StatisticsService.classify_value(0.98, 1.0, 19),
            CLASSIFICATION_FAILED,
        )
        self.assertEqual(
            StatisticsService.classify_value(0.995, 1.0, 19),
            CLASSIFICATION_NORMAL,
        )

    def test_overview_api_shape(self):
        self._make_record(
            beam_test_results={'6MV': {'test_17': 2.6}},
            date_performed=date(2026, 5, 12),
        )
        filters = StatisticsFilters(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        data = StatisticsService.build_overview(filters)
        self.assertIn('cards', data)
        self.assertIn('matrix', data)
        self.assertIn('sections', data['matrix'])
        self.assertIn('charts', data)
        self.assertIn('management', data['charts'])
        mgmt = data['charts']['management']
        self.assertIn('linac_completion', mgmt)
        self.assertIn('missing_qa_heatmap', mgmt)
        self.assertIn('summary', mgmt)
        self.assertIn('top_issues', mgmt)
        self.assertIn('review_list', data)
        self.assertGreaterEqual(data['cards']['records_included'], 1)

    def test_csv_export_headers(self):
        self._make_record()
        filters = StatisticsFilters(
            view_mode='single_test',
            qa_test_id=self.test_symmetry.id,
            energy='6MV',
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        csv_text = StatisticsService.build_csv(filters)
        self.assertIn('qa_record_id', csv_text.splitlines()[0])
        self.assertIn('Symmetry', csv_text)

    def test_single_test_trend_uses_warning_and_action_thresholds(self):
        self._make_record(
            beam_test_results={'6MV': {'test_17': 3.2}},
            date_performed=date(2026, 5, 12),
        )
        filters = StatisticsFilters(
            view_mode='single_test',
            qa_test_id=self.test_symmetry.id,
            energy='6MV',
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        data = StatisticsService.build_single_test_trend(filters)
        self.assertEqual(data['reference_lines']['upper_warning'], 3.0)
        self.assertEqual(data['reference_lines']['upper_action'], 3.5)
        self.assertEqual(data['table_rows'][0]['classification'], CLASSIFICATION_WARNING)


@override_settings(
    QAID_RUNTIME_SESSION_ID='runtime-b',
    MIDDLEWARE=RUNTIME_MIDDLEWARE,
)
class RuntimeSessionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='runtime_user', password='pass1234')

    def test_login_binds_session_to_current_runtime(self):
        logged_in = self.client.login(username='runtime_user', password='pass1234')
        self.assertTrue(logged_in)
        self.assertEqual(self.client.session.get(RUNTIME_SESSION_KEY), 'runtime-b')

    def test_runtime_mismatch_forces_relogin(self):
        self.client.force_login(self.user)
        session = self.client.session
        session[RUNTIME_SESSION_KEY] = 'runtime-a'
        session.save()

        response = self.client.get(reverse('statistics'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)


class StatisticsViewModeTests(TestCase):
    def setUp(self):
        self.linac = Linac.objects.create(name='L2', energy=['6MV'])
        self.test = QATest.objects.create(
            name='Output',
            test_type='beam',
            tolerance_value=2.0,
            tolerance_unit='%',
            order_index=15,
            is_active=True,
        )
        self.user = User.objects.create_user(username='vm_user', password='pass')
        self.client.force_login(self.user)

    def test_overview_api_returns_success(self):
        response = self.client.get(
            reverse('statistics_overview_api'),
            {'view_mode': 'overview', 'linac_ids': self.linac.id},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('cards', data['data'])

    def test_single_test_requires_test_id(self):
        response = self.client.get(
            reverse('statistics_trend_api'),
            {'view_mode': 'single_test'},
        )
        self.assertEqual(response.status_code, 400)

    def test_linac_all_requires_one_linac(self):
        response = self.client.get(
            reverse('statistics_linac_all_api'),
            {'view_mode': 'linac_all_tests'},
        )
        self.assertEqual(response.status_code, 400)


class StatisticsModeServiceTests(TestCase):
    def setUp(self):
        self.linac = Linac.objects.create(name='L3', energy=['6MV'])
        self.beam_test = QATest.objects.create(
            name='Symmetry',
            test_type='beam',
            tolerance_value=3.0,
            tolerance_unit='%',
            order_index=17,
            is_active=True,
        )
        self.mechanical = QATest.objects.create(
            name='Laser',
            test_type='mechanical',
            tolerance_value=1.0,
            tolerance_unit='mm',
            order_index=6,
            is_active=True,
        )
        self.status = QAStatus.objects.create(name='passed', color='#00ff00')
        self.user = User.objects.create_user(username='mode_user', password='pass')
        record = QARecord.objects.create(
            linac=self.linac,
            performed_by=self.user,
            status=self.status,
            is_draft=False,
            test_06=0.5,
            beam_test_results={'6MV': {'test_17': 3.2}},
        )
        QARecord.objects.filter(pk=record.pk).update(date_performed=date(2026, 5, 10))

    def test_linac_all_tests_summary(self):
        filters = StatisticsFilters(
            view_mode='linac_all_tests',
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        data = StatisticsService.build_linac_all_tests_summary(filters)
        self.assertIn('groups', data)
        self.assertIn('summary_table', data)
        self.assertTrue(len(data['summary_table']) > 0)

    def test_category_trends_summary(self):
        filters = StatisticsFilters(
            view_mode='category_trends',
            test_category='mechanical',
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        data = StatisticsService.build_category_trends_summary(filters)
        self.assertIn('summary_table', data)
        names = [r['test_name'] for r in data['summary_table']]
        self.assertTrue(any('Laser' in n for n in names))

    def test_beam_energy_summary(self):
        filters = StatisticsFilters(
            view_mode='beam_energy',
            energy='6MV',
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        data = StatisticsService.build_beam_energy_summary(filters)
        self.assertIn('summary_table', data)
        self.assertTrue(any(r.get('has_data') for r in data['summary_table']))

    def test_trend_summary_mini_series_capped(self):
        for i in range(30):
            record = QARecord.objects.create(
                linac=self.linac,
                performed_by=self.user,
                status=self.status,
                beam_test_results={'6MV': {'test_17': 1.0 + i * 0.01}},
            )
            QARecord.objects.filter(pk=record.pk).update(
                date_performed=date(2026, 1, 1) + __import__('datetime').timedelta(days=i)
            )
        filters = StatisticsFilters(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        qs = StatisticsService.build_queryset(filters)
        pts = StatisticsService.collect_points(qs, [self.beam_test], energy='6MV')
        summary = StatisticsService.build_trend_summary(pts, self.beam_test, energy='6MV')
        self.assertLessEqual(len(summary['mini_series']), 24)

    def test_review_list_includes_warnings(self):
        filters = StatisticsFilters(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        overview = StatisticsService.build_overview(filters)
        self.assertTrue(len(overview['review_list']) >= 1)

    def test_csv_export_all_modes(self):
        base = dict(
            linac_ids=[self.linac.id],
            date_from=date(2026, 1, 1),
            date_to=date(2026, 12, 31),
        )
        for mode in ('overview', 'single_test', 'linac_all_tests', 'category_trends', 'beam_energy'):
            filters = StatisticsFilters(view_mode=mode, **base)
            if mode == 'single_test':
                filters.qa_test_id = self.beam_test.id
                filters.energy = '6MV'
            if mode == 'category_trends':
                filters.test_category = 'beam'
                filters.energy = '6MV'
            if mode == 'beam_energy':
                filters.energy = '6MV'
            if mode == 'linac_all_tests':
                pass
            csv_text = StatisticsService.build_csv(filters)
            self.assertIn('qa_record_id', csv_text.splitlines()[0])


class FilmAnalysisParametersTests(TestCase):
    def test_default_threshold_when_no_record(self):
        self.assertEqual(
            get_field_size_detection_threshold(),
            DEFAULT_FIELD_SIZE_DETECTION_THRESHOLD,
        )

    def test_default_band_width_when_key_missing(self):
        self.assertEqual(DEFAULT_FIELD_SIZE_BAND_WIDTH_MM, 8.0)
        param = PhysicsParameters.objects.filter(parameter_type='film_analysis').first()
        values = dict(param.parameter_values) if isinstance(param.parameter_values, dict) else {}
        values.pop('field_size_band_width_mm', None)
        param.parameter_values = values
        param.save(update_fields=['parameter_values'])
        self.assertAlmostEqual(get_field_size_band_width_mm(), 8.0)

    def test_reads_threshold_from_physics_parameter_row(self):
        param = PhysicsParameters.objects.filter(parameter_type='film_analysis').first()
        param.parameter_values = {
            'field_size_detection_threshold': 0.45,
            'field_size_band_width_mm': 2.0,
        }
        param.save(update_fields=['parameter_values'])
        self.assertAlmostEqual(get_field_size_detection_threshold(), 0.45)

    def test_reads_band_width_mm_from_physics_parameter_row(self):
        param = PhysicsParameters.objects.filter(parameter_type='film_analysis').first()
        param.parameter_values = {
            'field_size_detection_threshold': 0.3,
            'field_size_band_width_mm': 3.5,
        }
        param.save(update_fields=['parameter_values'])
        self.assertAlmostEqual(get_field_size_band_width_mm(), 3.5)

    def test_band_width_mm_converts_to_pixels(self):
        px = band_width_mm_to_pixels(2.0, 300)
        self.assertAlmostEqual(px, 2.0 * (300 / 25.4), places=2)
        self.assertEqual(compute_station_line_count(px), int(round(px)))

    def test_robust_band_profile_offsets_within_half_band(self):
        import numpy as np
        from QAID_Manager.views.film_views import robust_band_profile

        band_width_px = band_width_mm_to_pixels(2.0, 300)
        half = band_width_px / 2.0
        p1 = np.array([100.0, 100.0])
        p2 = np.array([200.0, 100.0])
        normal = np.array([0.0, 1.0])
        image = np.full((300, 300), 128, dtype=np.uint8)

        offsets_used = []
        original_linspace = np.linspace

        def tracking_linspace(start, stop, num, *args, **kwargs):
            arr = original_linspace(start, stop, num, *args, **kwargs)
            if num >= 3 and abs(float(start) + half) < 0.01 and abs(float(stop) - half) < 0.01:
                offsets_used.extend(arr.tolist())
            return arr

        import unittest.mock as mock
        with mock.patch('QAID_Manager.views.film_views.np.linspace', side_effect=tracking_linspace):
            robust_band_profile(
                image_array=image,
                p1=p1,
                p2=p2,
                normal=normal,
                band_width_px=band_width_px,
                band_lines=10,
            )

        self.assertTrue(offsets_used)
        self.assertLessEqual(max(abs(v) for v in offsets_used), half + 0.01)

    def test_deduplicate_leaves_single_seeded_row(self):
        self.assertEqual(PhysicsParameters.objects.filter(parameter_type='film_analysis').count(), 1)
        result = deduplicate_film_analysis_parameters()
        self.assertIsNotNone(result)
        self.assertEqual(PhysicsParameters.objects.filter(parameter_type='film_analysis').count(), 1)

    def test_form_accepts_film_analysis_threshold(self):
        param = PhysicsParameters.objects.filter(parameter_type='film_analysis').first()
        form = PhysicsParametersForm(
            data={
                'name': 'Film Analysis Parameters',
                'parameter_type': 'film_analysis',
                'energy': '',
                'beam_type': 'photon',
                'parameter_values': '',
                'field_size_detection_threshold_percent': '42.5',
                'field_size_band_width_mm': '2.5',
                'description': '',
                'notes': '',
                'is_active': 'on',
            },
            instance=param,
        )
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_staff_can_update_threshold_via_standard_edit_form(self):
        user = User.objects.create_user(username='film_editor', password='pass1234', is_staff=True)
        param = PhysicsParameters.objects.filter(parameter_type='film_analysis').first()
        self.assertIsNotNone(param)
        self.client.force_login(user)
        response = self.client.post(
            reverse('physics_parameter_edit', kwargs={'pk': param.pk}),
            data={
                'name': 'Film Analysis Parameters',
                'parameter_type': 'film_analysis',
                'energy': '',
                'beam_type': 'photon',
                'parameter_values': '',
                'field_size_detection_threshold_percent': '42.5',
                'field_size_band_width_mm': '2.5',
                'description': '',
                'notes': '',
                'is_active': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        param.refresh_from_db()
        self.assertAlmostEqual(
            param.parameter_values['field_size_detection_threshold'],
            0.425,
        )
        self.assertAlmostEqual(param.parameter_values['field_size_band_width_mm'], 2.5)
        self.assertAlmostEqual(get_field_size_detection_threshold(), 0.425)
        self.assertAlmostEqual(get_field_size_band_width_mm(), 2.5)
