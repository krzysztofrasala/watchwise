from django.test import TestCase, Client
from django.urls import reverse
from movies import services

class MoviesViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_services_dataset_loading(self):
        all_movies = services.get_all_movies()
        self.assertGreater(len(all_movies), 0)

    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CineScope")

    def test_roulette_view(self):
        response = self.client.get(reverse('roulette'))
        self.assertEqual(response.status_code, 200)

    def test_watchlist_view(self):
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(response.status_code, 200)
