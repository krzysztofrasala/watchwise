from django.test import TestCase, Client
from django.urls import reverse
from movies import services, recommender, taste, nl_query, profiles, i18n

class MoviesViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_services_dataset_loading(self):
        all_movies = services.get_all_movies()
        self.assertGreater(len(all_movies), 0)

    def test_index_view(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Watch Wise")

    def test_discover_view(self):
        response = self.client.get(reverse('discover'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Discover Pro")

    def test_taste_dna_view(self):
        response = self.client.get(reverse('taste_dna'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Taste DNA")

    def test_compare_view(self):
        response = self.client.get(reverse('compare'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Matchmaker")

    def test_assistant_view(self):
        response = self.client.get(reverse('assistant'))
        self.assertEqual(response.status_code, 200)

    def test_roulette_view(self):
        response = self.client.get(reverse('roulette'))
        self.assertEqual(response.status_code, 200)

    def test_watchlist_view(self):
        response = self.client.get(reverse('watchlist'))
        self.assertEqual(response.status_code, 200)

    def test_nl_query_parsing(self):
        result = nl_query.parse_natural_query("mroczny thriller z lat 90")
        self.assertEqual(result["genre"], "Thriller")
        self.assertEqual(result["year_min"], 1990)
        self.assertEqual(result["year_max"], 1999)

    def test_profiles_management(self):
        session = {}
        active = profiles.get_active_profile_name(session)
        self.assertEqual(active, "Główny")

        added = profiles.add_profile(session, "Anna")
        self.assertTrue(added)
        self.assertEqual(profiles.get_active_profile_name(session), "Anna")

    def test_taste_profile_calculation(self):
        ratings = {11: 5, 278: 5}
        watchlist_ids = [680]
        taste_data = taste.compute_taste_profile(ratings, watchlist_ids)
        self.assertIn("persona_title", taste_data)
        self.assertGreaterEqual(taste_data["total_rated"], 2)

    def test_i18n_translations(self):
        self.assertEqual(i18n.t("nav_home", "PL"), "Odkrywaj")
        self.assertEqual(i18n.t("nav_home", "EN"), "Home")

    def test_language_switch_view_and_rendering(self):
        # Switch language to EN
        response = self.client.post(reverse('switch_language'), {'lang': 'EN'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get('lang'), 'EN')

        # Discover view should now render in English
        response = self.client.get(reverse('discover'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Precise Movie Filtering")

    def test_trending_services_and_partial_view(self):
        # Service function test
        items = services.get_trending_content(category="movies", lang="PL")
        self.assertIsInstance(items, list)

        # Partial view test
        response = self.client.get(reverse('trending_partial'), {'category': 'tv'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Popularne Seriale")

