import csv
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from QAID_Manager.models import PhysicsParameters


class Command(BaseCommand):
    help = 'Import physics parameters from CSV files into the PhysicsParameters model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-dir',
            type=str,
            default='physics_data',
            help='Directory containing CSV files (default: physics_data)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing physics parameters before importing'
        )

    def handle(self, *args, **options):
        csv_dir = options['csv_dir']
        clear_existing = options['clear_existing']
        
        # Get the full path to the CSV directory
        if os.path.isabs(csv_dir):
            csv_directory = csv_dir
        else:
            csv_directory = os.path.join(settings.BASE_DIR, csv_dir)
        
        self.stdout.write(f"📁 Looking for CSV files in: {csv_directory}")
        
        if not os.path.exists(csv_directory):
            self.stdout.write(
                self.style.ERROR(f"❌ Directory not found: {csv_directory}")
            )
            self.stdout.write("💡 Please create the directory and place your CSV files there.")
            return
        
        # Clear existing data if requested
        if clear_existing:
            count = PhysicsParameters.objects.count()
            PhysicsParameters.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"🗑️ Cleared {count} existing physics parameters")
            )
        
        # Process each CSV file
        csv_files = [f for f in os.listdir(csv_directory) if f.endswith('.csv')]
        
        if not csv_files:
            self.stdout.write(
                self.style.ERROR(f"❌ No CSV files found in {csv_directory}")
            )
            return
        
        self.stdout.write(f"📊 Found {len(csv_files)} CSV files: {', '.join(csv_files)}")
        
        total_imported = 0
        
        for csv_file in csv_files:
            file_path = os.path.join(csv_directory, csv_file)
            imported_count = self.import_csv_file(file_path, csv_file)
            total_imported += imported_count
        
        self.stdout.write(
            self.style.SUCCESS(f"✅ Successfully imported {total_imported} physics parameters")
        )

    def import_csv_file(self, file_path, filename):
        """Import data from a specific CSV file"""
        self.stdout.write(f"📄 Processing: {filename}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Log the column headers to understand the structure
                self.stdout.write(f"  📋 CSV Headers: {list(reader.fieldnames)}")
                
                # Read all rows into a list
                all_rows = []
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Log the first few rows to understand the data structure
                        if row_num <= 3:
                            self.stdout.write(f"  📊 Row {row_num}: {dict(row)}")
                        
                        all_rows.append(dict(row))
                        
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"  ❌ Error processing row {row_num}: {e}")
                        )
                        continue
                
                # Create one physics parameter for the entire CSV file
                parameter_type = self.determine_parameter_type(filename)
                param, created = self.create_physics_parameter_from_csv(all_rows, parameter_type, filename)
                
                if created:
                    self.stdout.write(f"  ✅ Created: {param.name}")
                else:
                    self.stdout.write(f"  🔄 Updated: {param.name}")
                
                self.stdout.write(f"  📊 Imported 1 table with {len(all_rows)} rows from {filename}")
                return 1
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error reading {filename}: {e}")
            )
            return 0

    def determine_parameter_type(self, filename):
        """Determine parameter type based on filename"""
        filename_lower = filename.lower()
        
        if 'ks' in filename_lower or 'coefficient' in filename_lower:
            return 'ks_coefficients'
        elif 'kq' in filename_lower or 'quality' in filename_lower:
            return 'kqqo'
        elif 'characteristics' in filename_lower and 'cylindrical' in filename_lower:
            return 'ndw'
        elif 'characteristics' in filename_lower and 'parallel' in filename_lower:
            return 'ndw'
        elif 'volume' in filename_lower and 'averaging' in filename_lower:
            return 'other'
        else:
            return 'other'

    def create_physics_parameter_from_csv(self, all_rows, parameter_type, filename):
        """Create or update a physics parameter from entire CSV file"""
        
        # Create a meaningful name from the filename
        name = self.get_table_name_from_filename(filename)
        
        # Add units to column headers based on filename
        processed_rows = self.add_units_to_headers(all_rows, filename)
        
        # Store all the CSV data in parameter_values
        parameter_values = {
            'table_data': processed_rows,
            'filename': filename,
            'import_date': str(datetime.now()),
        }
        
        # Reference information
        reference_standard = 'TRS398'
        reference_table = filename.replace('.csv', '')
        reference_page = ''
        
        # Description and notes
        description = f"Complete table data from {filename}"
        notes = f"Imported from {filename} with {len(all_rows)} rows"
        
        # Create or update the physics parameter
        param, created = PhysicsParameters.objects.update_or_create(
            name=name,
            parameter_type=parameter_type,
            defaults={
                'beam_type': 'photon',
                'chamber_type': '',
                'chamber_volume': None,
                'voltage_ratio': None,
                'a0_coefficient': None,
                'a1_coefficient': None,
                'a2_coefficient': None,
                'reference_energy': '',
                'kqqo_value': None,
                'reference_standard': reference_standard,
                'reference_table': reference_table,
                'reference_page': reference_page,
                'description': description,
                'notes': notes,
                'parameter_values': parameter_values,
                'is_active': True,
            }
        )
        
        return param, created

    def get_table_name_from_filename(self, filename):
        """Get a meaningful table name from filename"""
        # Remove .csv extension
        name = filename.replace('.csv', '')
        
        # Convert to title case and replace underscores with spaces
        name = name.replace('_', ' ').title()
        
        return name

    def add_units_to_headers(self, all_rows, filename):
        """Add units to column headers based on the type of data"""
        if not all_rows:
            return all_rows
        
        # Get the original headers from the first row
        original_headers = list(all_rows[0].keys())
        
        # Define unit mappings for different file types
        filename_lower = filename.lower()
        
        if 'cylindrical' in filename_lower:
            # Characteristics of Cylindrical Chamber types
            unit_mapping = {
                'Cavity volume (cm3)': 'Cavity volume (cm³)',
                'Cavity length (mm)': 'Cavity length (mm)',
                'Cavity radius (mm)': 'Cavity radius (mm)',
                'Wall thickness (g/cm2)': 'Wall thickness (g/cm²)',
            }
        elif 'parallel' in filename_lower:
            # Characteristics of Parallel Chamber types
            unit_mapping = {
                'Window thickness': 'Window thickness (mg/cm²)',
                'Electrode spacing': 'Electrode spacing (mm)',
                'Collecting electrode diameter': 'Collecting electrode diameter (mm)',
                'Guard ringwidth': 'Guard ring width (mm)',
            }
        elif 'kq' in filename_lower or 'quality' in filename_lower:
            # kQ Photon Beams - keep original headers
            unit_mapping = {}
        elif 'ks' in filename_lower or 'coefficient' in filename_lower:
            # Ks Coefficients - keep original headers
            unit_mapping = {}
        elif 'volume' in filename_lower and 'averaging' in filename_lower:
            # Volume Averaging Correction Factor for FFF - simplify headers to numbers
            unit_mapping = {
                'TPR20,10 = 0.6': '0.6',
                'TPR20,10 = 0.63': '0.63',
                'TPR20,10 = 0.66': '0.66',
                'TPR20,10 = 0.69': '0.69',
                'TPR20,10 = 0.72': '0.72',
                'TPR20,10 = 0.75': '0.75',
            }
        else:
            # Default: no units added
            unit_mapping = {}
        
        # Process each row
        processed_rows = []
        for row in all_rows:
            new_row = {}
            for header, value in row.items():
                # Use the unit mapping if available, otherwise keep original header
                new_header = unit_mapping.get(header, header)
                # Clean the value by removing units
                cleaned_value = self.clean_data_value(value, header)
                new_row[new_header] = cleaned_value
            processed_rows.append(new_row)
        
        return processed_rows

    def clean_data_value(self, value, header):
        """Remove units from data values since units are now in headers"""
        if not value or value == '':
            return value
        
        # Convert to string for processing
        value_str = str(value)
        
        # Remove common unit patterns
        import re
        
        # Remove units like "mm", "cm", "mg/cm²", "g/cm²", etc.
        value_str = re.sub(r'\s*(mm|cm|mg/cm²|g/cm²|cm³|cm3)\s*$', '', value_str, flags=re.IGNORECASE)
        
        # Remove complex patterns like "3.86 mg/cm20.05 mm" -> "0.05"
        value_str = re.sub(r'^\d+\.?\d*\s*mg/cm²\s*(\d+\.?\d*)\s*mm$', r'\1', value_str)
        
        # Remove patterns like "176 mg/cm²1 mm" -> "176"
        value_str = re.sub(r'^(\d+\.?\d*)\s*mg/cm²\s*\d+\s*mm$', r'\1', value_str)
        
        # Remove patterns like "1 mm polystyrene (P11)C-552 (A11)" -> "1"
        value_str = re.sub(r'^(\d+\.?\d*)\s*mm.*$', r'\1', value_str)
        
        # Remove simple mm patterns like "2 mm" -> "2"
        value_str = re.sub(r'^(\d+\.?\d*)\s*mm$', r'\1', value_str)
        
        return value_str.strip()

    def extract_name(self, row, filename):
        """Extract a meaningful name from the CSV row"""
        # Check for specific chamber type fields
        chamber_fields = ['Ionization chamber type', 'IC type', 'chamber_type', 'chamber', 'name', 'parameter_name']
        for field in chamber_fields:
            if field in row and row[field]:
                return row[field]
        
        # For Ks coefficients, use the voltage ratio
        if 'V1/V2' in row and row['V1/V2']:
            return f"Ks Coefficients (V1/V2 = {row['V1/V2']})"
        
        # For volume averaging, use cavity length
        if 'Cavity length (cm)' in row and row['Cavity length (cm)']:
            return f"Volume Averaging (L = {row['Cavity length (cm)']} cm)"
        
        # For kQ data, use the IC type if available
        if 'IC type' in row and row['IC type']:
            return f"kQ Values - {row['IC type']}"
        
        # Fallback to filename-based name
        return f"Parameter from {filename}"

    def safe_float(self, value):
        """Safely convert value to float, return None if invalid"""
        if value is None or value == '':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None 