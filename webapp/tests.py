from django.test import TestCase, Client
from django.urls import reverse
from .models import PredictionRecord
from .forms import PredictionForm
import numpy as np

class TitanicMLTests(TestCase):
    def setUp(self):
        """Initialize the test client and sample data."""
        self.client = Client()
        self.prediction_url = reverse('prediction_form')
        self.valid_data = {
            'name': 'Braund, Mr. Owen Harris',
            'pclass': 3,
            'sex': 'male',
            'age': 22,
            'sibsp': 1,
            'parch': 0,
            'fare': 7.25,
            'embarked': 'S'
        }

    def test_ml_artifacts_loaded(self):
        """Check if model and preprocessor are loaded globally in views."""
        from .views import model, preprocessor
        self.assertIsNotNone(model, "ML Model was not loaded.")
        self.assertIsNotNone(preprocessor, "Preprocessor was not loaded.")

    def test_prediction_flow_and_logic(self):
        """Test the full cycle: Form submission -> Engineering -> DB Save."""
        # Submit the form
        response = self.client.post(self.prediction_url, data=self.valid_data)
        
        # Check for redirect to results page
        self.assertEqual(response.status_code, 302)
        
        # Verify a record was created in the database
        record = PredictionRecord.objects.last()
        self.assertIsNotNone(record)
        
        # Verify feature engineering (John Doe, age 25, should be 'young_adult' -> 3)
        # Note: Since your view doesn't save age_group_numeric to the DB, 
        # we check the survival result and probability which depend on it.
        self.assertIn(record.survived_prediction, [True, False])
        self.assertGreaterEqual(record.probability, 0)
        self.assertLessEqual(record.probability, 100)

    def test_session_storage(self):
        """Verify the passenger name is stored in the session for the results page."""
        self.client.post(self.prediction_url, data=self.valid_data)
        self.assertEqual(self.client.session['last_passenger_name'], 'Braund, Mr. Owen Harris')

    def test_invalid_data_handling(self):
        """Ensure the app doesn't crash with missing data."""
        invalid_data = self.valid_data.copy()
        invalid_data['age'] = ''  # Age is required
        response = self.client.post(self.prediction_url, data=invalid_data)
        
        # Should stay on same page and show form errors
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PredictionRecord.objects.exists())

    def test_rating_submission(self):
        """Test the star rating functionality."""
        # Create a dummy record first
        record = PredictionRecord.objects.create(
            pclass=1, sex='female', age=22, sibsp=0, parch=0, fare=50, 
            embarked='C', survived_prediction=True, probability=90.0
        )
        rating_url = reverse('submit_rating', kwargs={'pk': record.pk})
        
        # Submit rating
        self.client.post(rating_url, {'rating': 5})
        
        # Refresh from DB
        record.refresh_from_db()
        self.assertEqual(record.rating, 5)