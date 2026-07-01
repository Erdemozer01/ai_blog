# bio_tools/urls.py

from django.urls import path, include
from . import views
from dash_apps.fastq_app import app as dash_app

app_name = 'bio_tools'

urlpatterns = [
    path('sequence-analyzer/', views.sequence_analyzer_view, name='sequence_analyzer'),

    path('phylogenetic-tree/', views.phylogenetic_tree_view, name='phylogenetic_tree'),

    path('sequence-alignment/', views.sequence_alignment_view, name='sequence_alignment'),

    path('molecule-viewer/', views.molecule_viewer_view, name='molecule_viewer'),

    path('mutation-predictor/', views.mutation_predictor_view, name='mutation_predictor'),

    path('bacterial-designer/', views.bacterial_designer_view, name='bacterial_designer'),

    path('pipeline-designer/', views.pipline_designer_view, name='pipline_designer_view'),
    path('primer-design/', views.primer_design_view, name='primer_design'),
    path('restriction-analysis/', views.restriction_view, name='restriction_analysis'),
    path('plasmid-map/', views.plasmid_map_view, name='plasmid_map'),

    path('crispr-designer/', views.crispr_designer_view, name='crispr_designer'),

    path('api/start-analysis/', views.start_analysis_view, name='start_analysis'),

    path('api/job-status/<str:job_id>/', views.get_job_status_view, name='get_job_status'),

    path('fastq-analyzer/', views.fastq_analyzer_view, name='fastq_analyzer'),

    path('api/', include('bio_tools.api.urls')),

    # Yeni araçlar — Makale entegrasyonu

    path('federated-learning/', views.federated_view, name='federated_learning'),
    path('pharmacogenomics/', views.pharmacogenomics_view, name='pharmacogenomics'),
    path('variant-prioritization/', views.variant_view, name='variant_prioritization'),
]