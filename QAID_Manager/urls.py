"""
URL Configuration for QAID Manager.

This module defines all URL patterns for the application, including:
- Authentication (login, logout, password change)
- QA Entry and Management
- Film Upload and Analysis
- Settings Management
- Equipment Management
- QA Schedule Management
- API Endpoints
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import qa_views, film_views
from .views.qa_schedule_views import (
    qa_schedule_monthly, create_qa_schedule, edit_qa_schedule, 
    assign_performers, confirm_schedule, create_schedule, accept_failed_qa,
    view_qa_records, create_bulk_schedule, create_adhoc_qa_schedule,
    update_schedule_notes
)
from .dosimeter_views import dosimeter_list, dosimeter_create, dosimeter_detail, dosimeter_edit, dosimeter_delete, dosimeter_document_delete
from .views.settings_views import (
    settings_home, settings_dosimeters, settings_linacs,
    settings_physics_parameters, settings_qa_tests, settings_vietnamese_holidays,
    settings_organization, settings_users, settings_devices,
    linac_detail, linac_create, linac_edit, linac_delete, linac_document_delete,
    physics_parameter_detail, physics_parameter_create, physics_parameter_edit, physics_parameter_delete,
    qa_test_detail, qa_test_create, qa_test_edit, qa_test_delete,
    vietnamese_holiday_detail, vietnamese_holiday_create, vietnamese_holiday_edit, vietnamese_holiday_delete,
    user_detail, user_create, user_edit, user_delete,
    device_detail, device_create, device_edit, device_delete, device_document_delete,
    download_report_template,
    settings_custom_test_types, custom_test_type_create, custom_test_type_edit, custom_test_type_delete,
    custom_test_create, custom_test_edit, custom_test_delete
)
from .views.linac_management_views import (
    linac_management, service_report_detail, service_report_create,
    service_report_edit, service_report_delete,
    service_report_print_selected, service_report_print_periodic
)
from .views import statistics_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', qa_views.home, name='home'),
    path('about/', qa_views.about, name='about'),
    path('help/', qa_views.help, name='help'),

    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='QAID_Manager/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('password_change/', auth_views.PasswordChangeView.as_view(
        template_name='QAID_Manager/password_change.html',
        success_url='/'
    ), name='password_change'),

    # QA Entry
    path('qa-entry/', qa_views.qa_entry, name='qa_entry'),
    path('qa-list/', qa_views.qa_list, name='qa_list'),
    path('qa-detail/<int:qa_id>/', qa_views.qa_detail, name='qa_detail'),

    # Film upload and analysis
    path('film-upload/', film_views.upload_film, name='upload_film'),
    path('check-dpi/', film_views.check_dpi, name='check_dpi'),
    path('crop-fieldsize/', film_views.crop_fieldsize_film, name='crop_fieldsize_film'),
    path('get-latest-film-filename/', film_views.get_latest_film_filename, name='get_latest_film_filename'),
    path('get-latest-colli-film-filename/', film_views.get_latest_colli_film_filename, name='get_latest_colli_film_filename'),
    path('get-latest-gantry-film-filename/', film_views.get_latest_gantry_film_filename, name='get_latest_gantry_film_filename'),
    path('save-temp-lines/', film_views.save_temp_lines, name='save_temp_lines'),
    path('clear-temp-lines/', film_views.clear_temp_lines, name='clear_temp_lines'),
    path('analyze-fieldsize/', film_views.analyze_fieldsize, name='analyze_fieldsize'),
    path('upload-collimator-film/', film_views.upload_collimator_film, name='upload_collimator_film'),
    path('crop-collimator-film/', film_views.crop_collimator_film, name='crop_collimator_film'),
    path('set-collimator-center/', film_views.set_collimator_center, name='set_collimator_center'),
    path('analyze-collimator/', film_views.analyze_collimator, name='analyze_collimator'),
    path('debug-collimator-files/', film_views.debug_collimator_files, name='debug_collimator_files'),
    
    # Gantry film upload and analysis
    path('upload-gantry-film/', film_views.upload_gantry_film, name='upload_gantry_film'),
    path('crop-gantry-film/', film_views.crop_gantry_film, name='crop_gantry_film'),
    path('set-gantry-center/', film_views.set_gantry_center, name='set_gantry_center'),
    path('analyze-gantry/', film_views.analyze_gantry, name='analyze_gantry'),
    path('debug-gantry-files/', film_views.debug_gantry_files, name='debug_gantry_files'),
    
    # Settings
    path('settings/', settings_home, name='settings'),
    path('settings/dosimeters/', settings_dosimeters, name='settings_dosimeters'),
    path('settings/linacs/', settings_linacs, name='settings_linacs'),
    path('settings/linacs/<int:pk>/', linac_detail, name='linac_detail'),
    path('settings/linacs/create/', linac_create, name='linac_create'),
    path('settings/linacs/<int:pk>/edit/', linac_edit, name='linac_edit'),
    path('settings/linacs/<int:pk>/delete/', linac_delete, name='linac_delete'),
    path('settings/linacs/<int:pk>/documents/<int:doc_pk>/delete/', linac_document_delete, name='linac_document_delete'),
    path('settings/physics-parameters/', settings_physics_parameters, name='settings_physics_parameters'),
    path('settings/physics-parameters/<int:pk>/', physics_parameter_detail, name='physics_parameter_detail'),
    path('settings/physics-parameters/create/', physics_parameter_create, name='physics_parameter_create'),
    path('settings/physics-parameters/<int:pk>/edit/', physics_parameter_edit, name='physics_parameter_edit'),
    path('settings/physics-parameters/<int:pk>/delete/', physics_parameter_delete, name='physics_parameter_delete'),
    path('settings/qa-tests/', settings_qa_tests, name='settings_qa_tests'),
    path('settings/qa-tests/<int:pk>/', qa_test_detail, name='qa_test_detail'),
    path('settings/qa-tests/create/', qa_test_create, name='qa_test_create'),
    path('settings/qa-tests/<int:pk>/edit/', qa_test_edit, name='qa_test_edit'),
    path('settings/qa-tests/<int:pk>/delete/', qa_test_delete, name='qa_test_delete'),
    path('settings/vietnamese-holidays/', settings_vietnamese_holidays, name='settings_vietnamese_holidays'),
    path('settings/vietnamese-holidays/<int:pk>/', vietnamese_holiday_detail, name='vietnamese_holiday_detail'),
    path('settings/vietnamese-holidays/create/', vietnamese_holiday_create, name='vietnamese_holiday_create'),
    path('settings/vietnamese-holidays/<int:pk>/edit/', vietnamese_holiday_edit, name='vietnamese_holiday_edit'),
    path('settings/vietnamese-holidays/<int:pk>/delete/', vietnamese_holiday_delete, name='vietnamese_holiday_delete'),
    path('settings/organization/', settings_organization, name='settings_organization'),
    path('settings/organization/templates/<str:template_type>/download/', download_report_template, name='download_report_template'),
    path('settings/users/', settings_users, name='settings_users'),
    path('settings/users/<int:pk>/', user_detail, name='user_detail'),
    path('settings/users/create/', user_create, name='user_create'),
    path('settings/users/<int:pk>/edit/', user_edit, name='user_edit'),
    path('settings/users/<int:pk>/delete/', user_delete, name='user_delete'),
    path('settings/devices/', settings_devices, name='settings_devices'),
    path('settings/devices/<int:pk>/', device_detail, name='device_detail'),
    path('settings/devices/create/', device_create, name='device_create'),
    path('settings/devices/<int:pk>/edit/', device_edit, name='device_edit'),
    path('settings/devices/<int:pk>/delete/', device_delete, name='device_delete'),
    path('settings/devices/<int:pk>/documents/<int:doc_pk>/delete/', device_document_delete, name='device_document_delete'),
    path('settings/custom-test-types/', settings_custom_test_types, name='settings_custom_test_types'),
    path('settings/custom-test-types/create/', custom_test_type_create, name='custom_test_type_create'),
    path('settings/custom-test-types/<int:pk>/edit/', custom_test_type_edit, name='custom_test_type_edit'),
    path('settings/custom-test-types/<int:pk>/delete/', custom_test_type_delete, name='custom_test_type_delete'),
    path('settings/custom-test-types/<int:type_pk>/tests/create/', custom_test_create, name='custom_test_create'),
    path('settings/custom-tests/<int:pk>/edit/', custom_test_edit, name='custom_test_edit'),
    path('settings/custom-tests/<int:pk>/delete/', custom_test_delete, name='custom_test_delete'),
    
    # Dosimeter Management (kept for compatibility, but accessed through settings)
    path('dosimeters/', dosimeter_list, name='dosimeter_list'),
    path('dosimeters/create/', dosimeter_create, name='dosimeter_create'),
    path('dosimeters/<int:pk>/', dosimeter_detail, name='dosimeter_detail'),
    path('dosimeters/<int:pk>/edit/', dosimeter_edit, name='dosimeter_edit'),
    path('dosimeters/<int:pk>/delete/', dosimeter_delete, name='dosimeter_delete'),
    path('dosimeters/<int:pk>/documents/<int:doc_pk>/delete/', dosimeter_document_delete, name='dosimeter_document_delete'),
    
    # QA Schedule Management
    path('qa-schedule/', qa_schedule_monthly, name='qa_schedule_monthly'),
    
    # Equipment Management (Equipment Service Reports)
    path('linacs-management/', linac_management, name='linac_management'),
    path('linacs-management/reports/create/', service_report_create, name='service_report_create'),
    path('linacs-management/reports/<int:pk>/', service_report_detail, name='service_report_detail'),
    path('linacs-management/reports/<int:pk>/edit/', service_report_edit, name='service_report_edit'),
    path('linacs-management/reports/<int:pk>/delete/', service_report_delete, name='service_report_delete'),
    path('linacs-management/reports/print-selected/', service_report_print_selected, name='service_report_print_selected'),
    path('linacs-management/reports/print-periodic/', service_report_print_periodic, name='service_report_print_periodic'),
    path('qa-schedule/create/', create_qa_schedule, name='create_qa_schedule'),
    path('qa-schedule/create-bulk/', create_bulk_schedule, name='create_bulk_schedule'),
    path('qa-schedule/create-adhoc/', create_adhoc_qa_schedule, name='create_adhoc_qa_schedule'),
    path('qa-schedule/<int:schedule_id>/edit/', edit_qa_schedule, name='edit_qa_schedule'),
    path('qa-schedule/assign-performers/', assign_performers, name='assign_performers'),
    path('qa-schedule/confirm-schedule/', confirm_schedule, name='confirm_schedule'),
    path('qa-schedule/create-schedule/', create_schedule, name='create_schedule'),
    path('qa-schedule/<int:schedule_id>/accept-failed/', accept_failed_qa, name='accept_failed_qa'),
    path('qa-schedule/<int:schedule_id>/view-records/', view_qa_records, name='view_qa_records'),
    path('qa-schedule/<int:schedule_id>/update-notes/', update_schedule_notes, name='update_schedule_notes'),

    # Statistics (v1.3)
    path('statistics/', statistics_views.statistics_home, name='statistics'),
    path('api/statistics/overview/', statistics_views.statistics_overview_api, name='statistics_overview_api'),
    path('api/statistics/trend/', statistics_views.statistics_trend_api, name='statistics_trend_api'),
    path('api/statistics/linac-all/', statistics_views.statistics_linac_all_api, name='statistics_linac_all_api'),
    path('api/statistics/category/', statistics_views.statistics_category_api, name='statistics_category_api'),
    path('api/statistics/beam-energy/', statistics_views.statistics_beam_energy_api, name='statistics_beam_energy_api'),
    path('api/statistics/point/<int:qa_record_id>/', statistics_views.statistics_point_api, name='statistics_point_api'),
    path('statistics/export/csv/', statistics_views.statistics_export_csv, name='statistics_export_csv'),

    
    # API endpoints
    path('api/linac/<int:linac_id>/energies/', qa_views.get_linac_energies, name='get_linac_energies'),
    path('api/ks-coefficients/<str:voltage_ratio>/', qa_views.get_ks_coefficients, name='get_ks_coefficients'),
    path('api/beam-quality/<int:linac_id>/<str:energy>/', qa_views.get_beam_quality, name='get_beam_quality'),
    path('api/kq-factor/<str:detector>/<str:tpr>/', qa_views.get_kq_factor, name='get_kq_factor'),
    path('api/dosimeter/<int:dosimeter_id>/', qa_views.get_dosimeter_calibration, name='get_dosimeter_calibration'),
    path('api/linac/<int:linac_id>/cat-values/<str:energy>/', qa_views.get_linac_cat_values, name='get_linac_cat_values'),
    path('api/dose-calculation/save/', qa_views.save_dose_calculation, name='save_dose_calculation'),
    path('api/linac/<int:linac_id>/previous-dose-values/', qa_views.get_previous_dose_values, name='get_previous_dose_values'),
    path('reports/qa/<int:qa_record_id>/', qa_views.generate_qa_report, name='generate_qa_report'),
    
    # App shutdown endpoint
    path('api/shutdown/', qa_views.shutdown_app, name='shutdown_app'),
]

# ✅ Add this for media support in development:
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)