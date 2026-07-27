"""
Dosimeter Management Views.

This module contains view functions for managing dosimeters and their documents.
All views require login, and create/edit/delete operations require staff permissions.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from .forms import DosimeterForm, DosimeterDocumentForm
from .models import Dosimeter, DosimeterDocument
import os

@login_required
def dosimeter_list(request):
    """Display list of all dosimeters"""
    dosimeters = Dosimeter.objects.all().order_by('name')
    return render(request, 'QAID_Manager/dosimeter_list.html', {
        'dosimeters': dosimeters
    })

@login_required
@staff_member_required
def dosimeter_create(request):
    """Create a new dosimeter (admin only)"""
    if request.method == 'POST':
        form = DosimeterForm(request.POST)
        if form.is_valid():
            dosimeter = form.save()
            messages.success(request, f'Dosimeter "{dosimeter.name}" created successfully.')
            return redirect('settings_dosimeters')
    else:
        form = DosimeterForm()
    
    return render(request, 'QAID_Manager/dosimeter_form.html', {
        'form': form,
        'title': 'Add New Dosimeter'
    })

@login_required
@staff_member_required
def dosimeter_edit(request, pk):
    """Edit an existing dosimeter (admin only)"""
    dosimeter = get_object_or_404(Dosimeter, pk=pk)
    
    if request.method == 'POST':
        form = DosimeterForm(request.POST, instance=dosimeter)
        if form.is_valid():
            dosimeter = form.save()
            messages.success(request, f'Dosimeter "{dosimeter.name}" updated successfully.')
            return redirect('settings_dosimeters')
    else:
        form = DosimeterForm(instance=dosimeter)
    
    return render(request, 'QAID_Manager/dosimeter_form.html', {
        'form': form,
        'dosimeter': dosimeter,
        'title': f'Edit Dosimeter: {dosimeter.name}'
    })

@login_required
def dosimeter_detail(request, pk):
    """View dosimeter details"""
    dosimeter = get_object_or_404(Dosimeter, pk=pk)
    documents = dosimeter.documents.all()
    is_admin = request.user.is_staff
    
    # Handle file upload
    if request.method == 'POST' and is_admin:
        form = DosimeterDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.dosimeter = dosimeter
            document.uploaded_by = request.user
            
            # Determine file type from extension
            filename = document.file.name
            ext = filename.split('.')[-1].lower() if '.' in filename else ''
            file_type_map = {
                'pdf': 'pdf',
                'doc': 'doc',
                'docx': 'docx',
                'png': 'png',
                'jpg': 'jpg',
                'jpeg': 'jpeg',
                'tiff': 'tiff',
                'tif': 'tif',
            }
            document.file_type = file_type_map.get(ext, 'other')
            
            # Set file_name if not provided
            if not document.file_name:
                document.file_name = os.path.basename(filename)
            
            document.save()
            messages.success(request, f'File "{document.file_name}" uploaded successfully.')
            return redirect('dosimeter_detail', pk=pk)
        else:
            messages.error(request, 'Error uploading file. Please check the form.')
    else:
        form = DosimeterDocumentForm()
    
    return render(request, 'QAID_Manager/dosimeter_detail.html', {
        'dosimeter': dosimeter,
        'documents': documents,
        'form': form,
        'is_admin': is_admin
    })

@login_required
@staff_member_required
@require_POST
def dosimeter_document_delete(request, pk, doc_pk):
    """Delete a dosimeter document"""
    document = get_object_or_404(DosimeterDocument, pk=doc_pk, dosimeter_id=pk)
    file_name = document.file_name
    document.delete()
    messages.success(request, f'File "{file_name}" deleted successfully.')
    return redirect('dosimeter_detail', pk=pk)

@login_required
@staff_member_required
def dosimeter_delete(request, pk):
    """Delete a dosimeter (admin only)"""
    dosimeter = get_object_or_404(Dosimeter, pk=pk)
    
    if request.method == 'POST':
        name = dosimeter.name
        dosimeter.delete()
        messages.success(request, f'Dosimeter "{name}" deleted successfully.')
        return redirect('settings_dosimeters')
    
    return render(request, 'QAID_Manager/dosimeter_confirm_delete.html', {
        'dosimeter': dosimeter
    }) 