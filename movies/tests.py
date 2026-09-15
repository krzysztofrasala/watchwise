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

    def test_movie_detail_view_and_htmx_partial(self):
        # Direct browser request (Deep linking)
        response_full = self.client.get(reverse('movie_modal_partial', args=[19995]))
        self.assertEqual(response_full.status_code, 200)
        self.assertContains(response_full, "Watch Wise")
        self.assertContains(response_full, "Avatar")

        # HTMX partial modal request
        response_htmx = self.client.get(reverse('movie_modal_partial', args=[19995]), HTTP_HX_REQUEST='true')
        self.assertEqual(response_htmx.status_code, 200)
        self.assertContains(response_htmx, 'id="movie-modal"')

    def test_profile_export_and_import(self):
        # Rate movie and export
        self.client.post(reverse('rate_movie', args=[19995]), {'stars': 5})
        response = self.client.get(reverse('export_profile'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json; charset=utf-8')
        self.assertIn('attachment; filename="watchwise_profiles_backup.json"', response['Content-Disposition'])

        # Import JSON backup
        import io
        backup_data = b'{"version": "2.0", "active_profile": "KinoFan", "profiles": {"KinoFan": {"watchlist": [19995], "ratings": {"19995": 5}}}}'
        file_obj = io.BytesIO(backup_data)
        file_obj.name = 'backup.json'
        import_resp = self.client.post(reverse('import_profile'), {'profile_file': file_obj})
        self.assertEqual(import_resp.status_code, 302)
        self.assertEqual(self.client.session.get('active_profile'), 'KinoFan')

    def test_discover_infinite_scroll_partial(self):
        response = self.client.get(reverse('discover') + '?page=2', HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "glass-card")


