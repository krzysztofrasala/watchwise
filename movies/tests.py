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

    def test_nl_query_multilingual(self):
        parse = nl_query.parse_natural_query_regex
        cases = [
            # (query, genre, year_min, year_max, language)
            ("mroczny thriller z lat 90", "Thriller", 1990, 1999, None),
            ("smieszna komedia francuska", "Comedy", None, None, "fr"),  # no diacritics
            ("polskie dramaty od 1990 do 2000", "Drama", 1990, 2000, "pl"),
            ("dark 90s psychological thriller", "Thriller", 1990, 1999, None),
            ("romantic comedy from the 80s", "Romance", 1980, 1989, None),
            ("düsterer Thriller aus den 90er", "Thriller", 1990, 1999, None),
            ("beste deutsche Komödien", "Comedy", None, None, "de"),
            ("película de terror de los años 80", "Horror", 1980, 1989, None),
            ("thriller oscuro anni '90 italiano", "Thriller", 1990, 1999, "it"),
            ("comédie française des années 80", "Comedy", 1980, 1989, "fr"),
            ("horror z 1995", "Horror", 1995, 1995, None),
            ("Horrorfilm seit 2015", "Horror", 2015, None, None),
        ]
        for query, genre, y_min, y_max, language in cases:
            with self.subTest(query=query):
                r = parse(query)
                self.assertEqual(r["genre"], genre)
                self.assertEqual(r["year_min"], y_min)
                self.assertEqual(r["year_max"], y_max)
                self.assertEqual(r["language"], language)

        # "10" in "top 10" must not be read as the 2010s
        r = parse("top 10 filmow")
        self.assertIsNone(r["year_min"])
        self.assertEqual(r["vote_min"], 8.0)
        # Runtime is not a rating
        self.assertIsNone(parse("film ponad 2 godziny")["vote_min"])
        self.assertEqual(parse("movies rated above 8")["vote_min"], 8.0)
        # Recent / classic / unknown input
        self.assertEqual(parse("newest action movies")["sort_by"], "year_desc")
        self.assertEqual(parse("klasyka sci-fi")["year_max"], 1999)
        self.assertFalse(parse("hello world")["understood"])

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

    def test_roulette_my_vod_subscription_filter(self):
        self.client.post(reverse('switch_language'), {'lang': 'PL'})
        # Subscribe to Player (id: 505)
        self.client.post(reverse('set_vod_subscriptions'), {'services': ['505']})

        # Spin with the exact parameters from user's case
        res = self.client.get(
            reverse('roulette_spin_partial') +
            '?source=my_vod&target_vod=any&only_subs=1&mood=all&runtime=any&genre=all&exclude_watched=1'
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="roulette-result-container"')

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

    def test_toggle_watched_from_watchlist_card_returns_html(self):
        self.client.post(reverse('toggle_watchlist', args=[278]))
        res = self.client.post(
            reverse('toggle_watched', args=[278]) + '?tab=watchlist&vod=all',
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='watchlist-grid-container',
        )
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="watchlist-grid-container"')
        self.assertIn('watchedChanged', res.headers.get('HX-Trigger', ''))

    def test_search_movies_by_actor_tags(self):
        results = services.search_movies("Kento Yamazaki", limit=5)
        self.assertGreater(len(results), 0)

    def test_taste_profile_low_ratings_and_watched_ids(self):
        low_only = taste.compute_taste_profile({278: 1}, [])
        self.assertEqual(low_only["genre_values"], [])
        with_watched = taste.compute_taste_profile({}, [], watched_ids=[278])
        self.assertGreater(len(with_watched["genre_labels"]), 0)

    def test_compare_vibe_matchmaker_with_populated_watchlist(self):
        self.client.post(reverse('toggle_watchlist', args=[278]))
        res = self.client.get(reverse('compare') + '?preset=couple')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['vibe1'], 'Action')
        self.assertEqual(res.context['vibe2'], 'Romance')
        self.assertGreater(len(res.context['recommendations']), 0)
        self.assertIn('Action & Romance', res.context['recommendations'][0].get('match_reason', ''))

    def test_profile_export_and_import(self):
        self.client.post(reverse('toggle_watchlist', args=[278]))
        export_res = self.client.get(reverse('export_profile'))
        self.assertEqual(export_res.status_code, 200)
        payload = json.loads(export_res.content.decode('utf-8'))
        self.assertIn('profiles', payload)
        self.assertIn(278, payload['profiles']['Główny']['watchlist'])

    def test_sparse_vectors_loaded_and_recommend_for_user_returns_results(self):
        movies_df, vectors, is_dense = services.load_dataset_with_vectors()
        self.assertIsNotNone(vectors)
        self.assertFalse(is_dense)
        recs = recommender.recommend_for_user({278: 5}, [], top_n=5)
        self.assertEqual(len(recs), 5)
        self.assertNotIn(278, [r['movie_id'] for r in recs])

    def test_database_url_parsing(self):
        from config.settings import _parse_database_url

        pg_cfg = _parse_database_url('postgresql://dbuser:dbpass@db.neon.tech:5432/cinescope?sslmode=require')
        self.assertEqual(pg_cfg['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(pg_cfg['NAME'], 'cinescope')
        self.assertEqual(pg_cfg['USER'], 'dbuser')
        self.assertEqual(pg_cfg['HOST'], 'db.neon.tech')
        self.assertEqual(pg_cfg['OPTIONS']['sslmode'], 'require')

    def test_compare_two_profiles_mode(self):
        # Populate Główny and create second profile Anna
        self.client.post(reverse('toggle_watchlist', args=[278]))
        self.client.post(reverse('create_profile'), {'new_profile_name': 'Anna'})
        self.client.post(reverse('toggle_watchlist', args=[19995]))

        res = self.client.get(reverse('compare') + '?mode=profiles&p1=Główny&p2=Anna')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['compare_mode'], 'profiles')
        self.assertGreater(len(res.context['recommendations']), 0)
        self.assertContains(res, 'Anna')

    def test_discover_pro_vod_and_runtime_filters(self):
        res = self.client.get(reverse('discover') + '?genre=Drama&max_runtime=120&year_min=1990&sort_by=year_desc')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['selected_runtime'], '120')
        for m in res.context['movies']:
            self.assertLessEqual(m['runtime'], 120)
            self.assertGreaterEqual(m['year'], 1990)

    def test_taste_dna_critic_style_and_hall_of_fame(self):
        self.client.post(
            reverse('rate_movie', args=[278]),
            data=json.dumps({'stars': 5}),
            content_type='application/json',
        )
        self.client.post(reverse('toggle_watched', args=[19995]))
        res = self.client.get(reverse('taste_dna'))
        self.assertEqual(res.status_code, 200)
        td = res.context['taste_data']
        self.assertGreaterEqual(td['total_watched'], 2)
        self.assertGreater(td['avg_runtime'], 0)
        self.assertEqual(len(td['top_rated_movies']), 1)
        self.assertEqual(td['top_rated_movies'][0]['movie_id'], 278)









class HardeningTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_assistant_rate_limit(self):
        from . import views
        for _ in range(views.ASSISTANT_RATE_LIMIT):
            res = self.client.post("/assistant/chat/", {"message": "   "})
            self.assertEqual(res.status_code, 400)  # empty message, not counted
        # exhaust the counter directly, then the next real request is refused
        from django.core.cache import cache
        cache.set("rl:assistant:127.0.0.1", views.ASSISTANT_RATE_LIMIT, 3600)
        res = self.client.post("/assistant/chat/", {"message": "komedia"})
        self.assertEqual(res.status_code, 429)

    def test_import_rejects_oversized_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from . import views
        big = SimpleUploadedFile("p.json", b"x" * (views.IMPORT_MAX_BYTES + 1))
        res = self.client.post("/profile/import/", {"profile_file": big})
        self.assertEqual(res.status_code, 413)

    def test_bad_page_param_does_not_500(self):
        self.assertEqual(self.client.get("/discover/?page=abc").status_code, 200)


class AssistantSubjectTests(TestCase):
    def test_subject_extraction_strips_filler_words(self):
        from . import views
        self.assertEqual(views._assistant_subject("szukam filmu z nicolas cage"), "nicolas cage")
        self.assertEqual(views._assistant_subject("movie with Leonardo DiCaprio"), "Leonardo DiCaprio")
        self.assertEqual(views._assistant_subject("film z brucem willisem"), "brucem willisem")


class AssistantParsingTests(TestCase):
    def test_extract_similar_title(self):
        from . import nl_query
        self.assertEqual(nl_query.extract_similar_title("filmy podobne do Incepcji"), "Incepcji")
        self.assertEqual(nl_query.extract_similar_title("movies like The Matrix"), "The Matrix")
        self.assertIsNone(nl_query.extract_similar_title("komedia z lat 90"))

    def test_strip_filter_terms_keeps_only_name(self):
        from . import nl_query
        self.assertEqual(nl_query.strip_filter_terms("thriller z bruce willis po 2000"), "z bruce willis")
        self.assertEqual(nl_query.strip_filter_terms("komedia z lat 90"), "z")

    def test_trending_is_cached_decorated(self):
        from . import tmdb
        self.assertTrue(hasattr(tmdb.fetch_trending, "__wrapped__"))


class HarmonyScoreTests(TestCase):
    def test_identical_genres_give_full_harmony(self):
        from . import recommender
        self.assertEqual(recommender.get_harmony_score("Horror", "Horror"), 100)
        self.assertLess(recommender.get_harmony_score("Horror", "Romance"), 100)


class WeightedRatingTests(TestCase):
    def test_dataset_has_vote_counts_and_weighted_rating(self):
        from . import services
        df, _ = services.load_dataset()
        self.assertIn("vote_count", df.columns)
        self.assertIn("weighted_rating", df.columns)
        self.assertGreater(int(df["vote_count"].max()), 1000)

    def test_top_rated_prefers_well_voted_films(self):
        from . import services
        top = services.filter_movies(sort_by="vote_desc", per_page=10)["items"]
        self.assertGreaterEqual(len(top), 10)
        # a 9.4 from a handful of votes must not outrank films with thousands of votes
        self.assertTrue(all(m["vote_count"] >= 1000 for m in top))

    def test_lru_cache_on_load_dataset(self):
        from . import services
        self.assertTrue(hasattr(services.load_dataset, "cache_info"))
