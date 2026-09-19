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

    def test_toggle_watched_endpoint_and_recommendation_exclusion(self):
        # 1. Add movie to watchlist
        self.client.post(reverse('toggle_watchlist', args=[19995]))
        self.assertEqual(len(self.client.session.get('profiles', {}).get('Główny', {}).get('watchlist', [])), 1)

        # 2. Toggle watched: marks as watched and removes from to-watch watchlist
        res = self.client.post(reverse('toggle_watched', args=[19995]))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['marked'])
        self.assertEqual(data['watched_count'], 1)
        self.assertEqual(data['watchlist_count'], 0)

        # Session verification
        p_data = self.client.session.get('profiles', {}).get('Główny', {})
        self.assertIn(19995, p_data.get('watched', []))
        self.assertNotIn(19995, p_data.get('watchlist', []))

        # Recommender test: Watched movie 19995 must be excluded from recommendations
        recs = recommender.recommend_for_user(
            user_ratings={11: 5},
            watchlist_ids=[],
            top_n=10,
            watched_ids=[19995]
        )
        rec_ids = [r['movie_id'] for r in recs]
        self.assertNotIn(19995, rec_ids)

    def test_vod_subscriptions_and_modal_partial(self):
        # Test VOD modal partial
        modal_res = self.client.get(reverse('vod_subscription_modal'))
        self.assertEqual(modal_res.status_code, 200)
        self.assertContains(modal_res, 'Netflix')
        self.assertContains(modal_res, 'Disney+')

        # Test setting subscriptions
        set_res = self.client.post(reverse('set_vod_subscriptions'), {'services': ['8', '337']})
        self.assertEqual(set_res.status_code, 302)
        active_subs = profiles.get_active_vod_subscriptions(self.client.session)
        self.assertEqual(active_subs, [8, 337])

    def test_watchlist_grid_partial_and_filtering(self):
        # Add a movie to watchlist and test grid partial
        self.client.post(reverse('toggle_watchlist', args=[19995]))
        grid_res = self.client.get(reverse('watchlist_grid_partial') + '?tab=watchlist&vod=all')
        self.assertEqual(grid_res.status_code, 200)
        self.assertContains(grid_res, 'Avatar')
        self.assertContains(grid_res, 'id="watchlist-grid-container"')

        # Test watched tab empty state
        watched_res = self.client.get(reverse('watchlist_grid_partial') + '?tab=watched&vod=all')
        self.assertEqual(watched_res.status_code, 200)
        self.assertContains(watched_res, 'Brak obejrzanych filmów')

    def test_profile_export_import_with_watched_and_vod(self):
        # Set up profile with watched and vod
        self.client.post(reverse('toggle_watched', args=[19995]))
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['8', '119']})

        # Export
        exp_res = self.client.get(reverse('export_profile'))
        self.assertEqual(exp_res.status_code, 200)
        exp_data = exp_res.json()
        self.assertIn('watched', exp_data['profiles']['Główny'])
        self.assertIn('vod_subscriptions', exp_data['profiles']['Główny'])
        self.assertEqual(exp_data['profiles']['Główny']['watched'], [19995])
        self.assertEqual(exp_data['profiles']['Główny']['vod_subscriptions'], [8, 119])

        # Import with new format
        import io
        import json
        new_backup = json.dumps({
            "version": "2.1",
            "active_profile": "Cinephile",
            "profiles": {
                "Cinephile": {
                    "watchlist": [278],
                    "watched": [19995],
                    "ratings": {"19995": 5},
                    "vod_subscriptions": [8, 337]
                }
            }
        }).encode('utf-8')
        file_obj = io.BytesIO(new_backup)
        file_obj.name = 'backup_v21.json'
        imp_res = self.client.post(reverse('import_profile'), {'profile_file': file_obj})
        self.assertEqual(imp_res.status_code, 302)

        session = self.client.session
        self.assertEqual(profiles.get_active_profile_name(session), "Cinephile")
        self.assertEqual(profiles.get_active_watched(session), [19995])
        self.assertEqual(profiles.get_active_vod_subscriptions(session), [8, 337])

    def test_roulette_spin_partial_and_filters(self):
        # 1. Base spin with default params
        res = self.client.get(reverse('roulette_spin_partial'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="roulette-result-container"')

        # 2. Spin with mood and runtime
        res_filtered = self.client.get(reverse('roulette_spin_partial') + '?mood=fun&runtime=120')
        self.assertEqual(res_filtered.status_code, 200)

        # 3. Spin with watchlist source
        self.client.post(reverse('toggle_watchlist', args=[19995]))
        res_wl = self.client.get(reverse('roulette_spin_partial') + '?source=watchlist')
        self.assertEqual(res_wl.status_code, 200)
        self.assertContains(res_wl, 'Avatar')

        # 4. Spin with excluded watched
        self.client.post(reverse('toggle_watched', args=[19995]))
        res_ex = self.client.get(reverse('roulette_spin_partial') + '?source=watchlist&exclude_watched=1')
        self.assertEqual(res_ex.status_code, 200)




