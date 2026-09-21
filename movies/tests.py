import json
from django.test import TestCase, Client
from django.urls import reverse
from movies import services, recommender, taste, nl_query, profiles, i18n, tmdb

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

    def test_multilingual_overview_and_title_fallback(self):
        # 1. Services level test
        m_en = services.get_movie_by_id(278, lang="EN")
        m_pl = services.get_movie_by_id(278, lang="PL")
        self.assertIsNotNone(m_en)
        self.assertIsNotNone(m_pl)
        self.assertEqual(m_en["title"], "The Shawshank Redemption")
        self.assertTrue(m_en["overview"].startswith("Imprisoned in the 1940s"))
        self.assertTrue(m_pl["overview"].startswith("Adaptacja powieści"))

        # 2. Filter level test
        filtered_en = services.filter_movies(genre="All", sort_by="vote_desc", per_page=5, lang="EN")
        for item in filtered_en["items"]:
            if item.get("overview_en"):
                self.assertEqual(item["overview"], item["overview_en"])

        # 3. View level test with session lang
        self.client.post(reverse('switch_language'), {'lang': 'EN'})
        res_detail_en = self.client.get(reverse('movie_modal_partial', args=[278]))
        self.assertEqual(res_detail_en.status_code, 200)
        self.assertContains(res_detail_en, "The Shawshank Redemption")
        self.assertContains(res_detail_en, "Imprisoned in the 1940s")

    def test_vod_categorization_and_region_mapping(self):
        # 1. VOD details for EN (US region)
        vod_en = tmdb.fetch_movie_details(278, lang="EN")
        self.assertIsNotNone(vod_en)
        self.assertTrue("themoviedb.org" in vod_en["justwatch_url"] or "us/search" in vod_en["justwatch_url"])
        self.assertGreater(len(vod_en["vod_flatrate"]), 0)
        self.assertTrue(any(p["name"] in ["fuboTV", "MGM+ Amazon Channel", "Max"] for p in vod_en["vod_flatrate"]))

        # 2. VOD details for PL (PL region)
        vod_pl = tmdb.fetch_movie_details(278, lang="PL")
        self.assertIsNotNone(vod_pl)
        self.assertTrue("themoviedb.org" in vod_pl["justwatch_url"] or "pl/search" in vod_pl["justwatch_url"])

        # 3. Modal rendering contains VOD stream badge
        self.client.post(reverse('switch_language'), {'lang': 'EN'})
        res_modal = self.client.get(reverse('movie_modal_partial', args=[278]), HTTP_HX_REQUEST='true')
        self.assertEqual(res_modal.status_code, 200)
        self.assertContains(res_modal, "Stream / Subscription:")
        self.assertTrue("fuboTV" in res_modal.content.decode("utf-8") or "Max" in res_modal.content.decode("utf-8"))


    def test_localization_zero_polish_leaks(self):
        # Test English modal
        self.client.post(reverse('switch_language'), {'lang': 'EN'})
        res_en = self.client.get(reverse('movie_modal_partial', args=[278]), HTTP_HX_REQUEST='true')
        self.assertEqual(res_en.status_code, 200)
        self.assertNotContains(res_en, "Szukaj zwiastuna")
        self.assertNotContains(res_en, "Udostępnij")
        self.assertNotContains(res_en, "Zamknij (Esc)")
        self.assertNotContains(res_en, "Adaptacja powieści")
        self.assertContains(res_en, "Share")
        self.assertContains(res_en, "Close (Esc)")

        # Test German modal & trending
        self.client.post(reverse('switch_language'), {'lang': 'DE'})
        res_de = self.client.get(reverse('movie_modal_partial', args=[278]), HTTP_HX_REQUEST='true')
        self.assertEqual(res_de.status_code, 200)
        self.assertNotContains(res_de, "Szukaj zwiastuna")
        self.assertNotContains(res_de, "Udostępnij")
        self.assertNotContains(res_de, "Zamknij (Esc)")
        self.assertNotContains(res_de, "Adaptacja powieści")
        self.assertContains(res_de, "Teilen")
        self.assertContains(res_de, "Schließen (Esc)")

        res_trending_de = self.client.get(reverse('trending_partial'))
        self.assertEqual(res_trending_de.status_code, 200)
        self.assertNotContains(res_trending_de, "Filmowe Hity")
        self.assertNotContains(res_trending_de, "Popularne Seriale")
        self.assertContains(res_trending_de, "Film-Highlights")
        self.assertContains(res_trending_de, "Beliebte Serien")

        # Test Spanish modal
        self.client.post(reverse('switch_language'), {'lang': 'ES'})
        res_es = self.client.get(reverse('movie_modal_partial', args=[278]), HTTP_HX_REQUEST='true')
        self.assertEqual(res_es.status_code, 200)
        self.assertNotContains(res_es, "Szukaj zwiastuna")
        self.assertNotContains(res_es, "Udostępnij")
        self.assertNotContains(res_es, "Zamknij (Esc)")
        self.assertContains(res_es, "Compartir")
        self.assertContains(res_es, "Cerrar (Esc)")

    def test_i18n_fallback_to_en_for_non_pl(self):
        from movies.i18n import t
        # Existing key in DE
        self.assertEqual(t("share", "DE"), "Teilen")
        # Non-existing key in DE should fall back to EN, NOT to PL
        self.assertEqual(t("non_existent_key_xyz", "DE"), "non_existent_key_xyz")
        # PL key should return PL
        self.assertEqual(t("share", "PL"), "Udostępnij")

    def test_localized_toasts(self):
        self.client.post(reverse('switch_language'), {'lang': 'EN'})
        res = self.client.post(reverse('toggle_watchlist', args=[278]))
        self.assertEqual(res.status_code, 200)
        self.assertIn("Added to your library", res["HX-Trigger"])

        res_rate = self.client.post(reverse('rate_movie', args=[278]), data=json.dumps({'stars': 5}), content_type='application/json')
        self.assertEqual(res_rate.status_code, 200)
        self.assertIn("Rating saved", res_rate["HX-Trigger"])

    def test_foreign_language_overview_translation(self):
        # Switch to ES and verify modal for Attack on Titan (1333100)
        self.client.post(reverse('switch_language'), {'lang': 'ES'})
        res = self.client.get(reverse('movie_modal_partial', args=[1333100]), HTTP_HX_REQUEST='true')
        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("Compartir", content)
        self.assertIn("Cerrar (Esc)", content)
        # Should have translated or localized Spanish overview instead of English raw overview
        self.assertTrue("película" in content.lower() or "titanes" in content.lower())

    def test_watchlist_smart_vod_filtering_and_groups(self):
        # Ensure session is in Polish
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # 1. Add Shawshank (278) to watchlist
        self.client.post(reverse('toggle_watchlist', args=[278]))

        # 2. Set active VOD subscription to Player (id: 505)
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505']})

        # 3. Request watchlist grid with my_vod filter and only_subs=1
        res = self.client.get(reverse('watchlist_grid_partial') + '?tab=watchlist&vod=my_vod&only_subs=1')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "The Shawshank Redemption")
        # Should contain direct link or provider indicator
        self.assertContains(res, "Player")

        # 4. Request by_platform view mode
        res_by_plat = self.client.get(reverse('watchlist_grid_partial') + '?tab=watchlist&view_mode=by_platform')
        self.assertEqual(res_by_plat.status_code, 200)
        self.assertContains(res_by_plat, "Player")
        self.assertContains(res_by_plat, "The Shawshank Redemption")

    def test_watchlist_empty_subscriptions_prompt(self):
        # Ensure session is in Polish
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # Clear VOD subscriptions
        self.client.post(reverse('set_vod_subscriptions'), {'services': []})
        res = self.client.get(reverse('watchlist_grid_partial') + '?tab=watchlist&vod=my_vod')
        self.assertEqual(res.status_code, 200)
        # Should prompt to select streaming services
        self.assertContains(res, "Nie zaznaczyłeś jeszcze subskrybowanych platform VOD.")

    def test_roulette_smart_vod_and_watchlist(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # 1. Add Shawshank (278) to watchlist
        self.client.post(reverse('toggle_watchlist', args=[278]))

        # 2. Subscribe to Player (id: 505)
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505']})

        # 3. Spin roulette for watchlist on my VOD
        res = self.client.get(reverse('roulette_spin_partial') + '?source=watchlist_vod&only_subs=1')
        self.assertEqual(res.status_code, 200)
        # Winner must be Shawshank and must include Player watch link and badges
        self.assertContains(res, "The Shawshank Redemption")
        self.assertContains(res, "Player")
        self.assertContains(res, "Z Twojej Watchlisty")
        self.assertContains(res, "W abonamencie")

    def test_roulette_empty_vod_prompt(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # Clear subscriptions
        self.client.post(reverse('set_vod_subscriptions'), {'services': []})

        # Spin roulette for watchlist_vod without any configured subscriptions
        res = self.client.get(reverse('roulette_spin_partial') + '?source=watchlist_vod')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Nie masz jeszcze skonfigurowanych subskrypcji VOD")
        self.assertContains(res, "Wybierz swoje platformy")

    def test_home_vod_badges_and_filters(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # Subscribe to Player (505) and Netflix (8)
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505', '8']})
        
        # Test Home Page
        res = self.client.get(reverse('index'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "VOD:")
        self.assertContains(res, "Wszystkie platformy")
        self.assertContains(res, "Tylko moje VOD")
        self.assertContains(res, "Player")
        self.assertContains(res, "Netflix")
        self.assertContains(res, "Wybierz swoje platformy")

    def test_trending_my_vod_category(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # 1. When no VOD is configured
        self.client.post(reverse('set_vod_subscriptions'), {'services': []})
        empty_res = self.client.get(reverse('trending_partial') + '?category=my_vod')
        self.assertEqual(empty_res.status_code, 200)
        self.assertContains(empty_res, "Nie zaznaczyłeś jeszcze subskrybowanych platform VOD.")
        self.assertContains(empty_res, "Wybierz swoje platformy")
        self.assertContains(empty_res, reverse('vod_subscription_modal'))

        # 2. When VOD is configured (e.g. Player 505)
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505', '8', '1899']})
        active_res = self.client.get(reverse('trending_partial') + '?category=my_vod')
        self.assertEqual(active_res.status_code, 200)
        self.assertNotContains(active_res, "Nie zaznaczyłeś jeszcze subskrybowanych platform VOD.")

    def test_movie_grid_vod_filter(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505']})

        # Test filter by my_vod
        res_my_vod = self.client.get(reverse('movie_grid_partial') + '?vod=my_vod')
        self.assertEqual(res_my_vod.status_code, 200)

        # Test filter by specific provider id
        res_provider = self.client.get(reverse('movie_grid_partial') + '?vod=505')
        self.assertEqual(res_provider.status_code, 200)

    def test_set_vod_subscriptions_hx_refresh(self):
        # When called via HTMX on home page, should return HX-Refresh
        res_home = self.client.post(
            reverse('set_vod_subscriptions'),
            {'services': ['8', '505']},
            HTTP_HX_REQUEST='true',
            HTTP_HX_CURRENT_URL='http://testserver/'
        )
        self.assertEqual(res_home.status_code, 200)
        self.assertEqual(res_home.headers.get('HX-Refresh'), 'true')

        # When called via HTMX on watchlist page, should return watchlist grid partial and closeVodModal trigger
        res_wl = self.client.post(
            reverse('set_vod_subscriptions'),
            {'services': ['8', '505']},
            HTTP_HX_REQUEST='true',
            HTTP_HX_CURRENT_URL='http://testserver/watchlist/'
        )
        self.assertEqual(res_wl.status_code, 200)
        self.assertIn('closeVodModal', res_wl.headers.get('HX-Trigger', ''))

    def test_pwa_manifest(self):
        res = self.client.get(reverse('pwa_manifest'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/manifest+json', res.headers.get('Content-Type', ''))
        data = json.loads(res.content.decode('utf-8'))
        self.assertEqual(data.get('short_name'), 'Watch Wise')
        self.assertEqual(data.get('display'), 'standalone')
        self.assertTrue(len(data.get('icons', [])) >= 3)
        self.assertTrue(len(data.get('shortcuts', [])) >= 2)

    def test_pwa_service_worker(self):
        res = self.client.get(reverse('service_worker'))
        self.assertEqual(res.status_code, 200)
        self.assertIn('application/javascript', res.headers.get('Content-Type', ''))
        self.assertEqual(res.headers.get('Service-Worker-Allowed'), '/')
        content = res.content.decode('utf-8')
        self.assertIn('CACHE_NAME', content)
        self.assertIn('/offline/', content)

    def test_pwa_offline_page(self):
        res = self.client.get(reverse('offline'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Brak połączenia z siecią")
        self.assertContains(res, "Spróbuj ponownie")

    def test_base_pwa_meta_tags(self):
        res = self.client.get(reverse('index'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'rel="manifest"')
        self.assertContains(res, 'name="theme-color"')
        self.assertContains(res, 'apple-mobile-web-app-capable')
        self.assertContains(res, 'icons/favicon')
        self.assertContains(res, 'pwa-install-btn-mobile')





