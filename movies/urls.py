from django.urls import path
from .views import assistant, catalog, discover, insights, preferences, pwa, roulette, watchlist

urlpatterns = [
    path('', catalog.index, name='index'),
    path('trending/partial/', catalog.trending_partial, name='trending_partial'),
    path('grid/', catalog.movie_grid_partial, name='movie_grid_partial'),

    path('search/', catalog.search_live_partial, name='search_live_partial'),
    path('movie/<int:movie_id>/', catalog.movie_modal_partial, name='movie_modal_partial'),
    path('roulette/', roulette.roulette, name='roulette'),
    path('roulette/spin/', roulette.roulette_spin_partial, name='roulette_spin_partial'),
    path('watchlist/', watchlist.watchlist, name='watchlist'),
    path('watchlist/grid-partial/', watchlist.watchlist_grid_partial, name='watchlist_grid_partial'),
    path('watchlist/toggle/<int:movie_id>/', watchlist.toggle_watchlist, name='toggle_watchlist'),
    path('watchlist/toggle-watched/<int:movie_id>/', watchlist.toggle_watched, name='toggle_watched'),
    path('watchlist/vod-modal/', watchlist.vod_subscription_modal_partial, name='vod_subscription_modal'),
    path('watchlist/set-vod-subscriptions/', watchlist.set_vod_subscriptions_view, name='set_vod_subscriptions'),
    path('rate/<int:movie_id>/', watchlist.rate_movie, name='rate_movie'),
    path('discover/', discover.discover, name='discover'),
    path('taste-dna/', insights.taste_dna, name='taste_dna'),
    path('compare/', insights.compare, name='compare'),
    path('assistant/', assistant.assistant, name='assistant'),
    path('assistant/chat/', assistant.assistant_chat_partial, name='assistant_chat_partial'),
    path('profile/switch/', preferences.switch_profile, name='switch_profile'),
    path('profile/create/', preferences.create_profile, name='create_profile'),
    path('profile/delete/', preferences.delete_profile_view, name='delete_profile'),
    path('profile/export/', preferences.export_profile, name='export_profile'),
    path('profile/import/', preferences.import_profile, name='import_profile'),
    path('language/switch/', preferences.switch_language, name='switch_language'),

    # PWA Endpoints
    path('manifest.json', pwa.manifest_view, name='pwa_manifest'),
    path('sw.js', pwa.service_worker_view, name='service_worker'),
    path('offline/', pwa.offline_view, name='offline'),
]

