from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from ..models import FastqUpload

class FastqAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.session = self.client.session
        self.session.save()
    
    def test_statistics_endpoint(self):
        """İstatistik endpoint testi"""
        response = self.client.get('/bio-tools/api/uploads/statistics/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_files', response.data)
        self.assertIn('completed', response.data)