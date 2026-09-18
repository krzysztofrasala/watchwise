from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('trending/partial/', views.trending_partial, name='trending_partial'),
    path('grid/', views.movie_grid_partial, name='movie_grid_partial'),

    path('search/', views.search_live_partial, name='search_live_partial'),
    path('movie/<int:movie_id>/', views.movie_modal_partial, name='movie_modal_partial'),
    path('roulette/', views.roulette, name='roulette'),
    path('watchlist/', views.watchlist, name='watchlist'),
    path('watchlist/grid-partial/', views.watchlist_grid_partial, name='watchlist_grid_partial'),
    path('watchlist/toggle/<int:movie_id>/', views.toggle_watchlist, name='toggle_watchlist'),
    path('watchlist/toggle-watched/<int:movie_id>/', views.toggle_watched, name='toggle_watched'),
    path('watchlist/vod-modal/', views.vod_subscription_modal_partial, name='vod_subscription_modal'),
    path('watchlist/set-vod-subscriptions/', views.set_vod_subscriptions_view, name='set_vod_subscriptions'),
    path('rate/<int:movie_id>/', views.rate_movie, name='rate_movie'),
    path('discover/', views.discover, name='discover'),
    path('taste-dna/', views.taste_dna, name='taste_dna'),
    path('compare/', views.compare, name='compare'),
    path('assistant/', views.assistant, name='assistant'),
    path('assistant/chat/', views.assistant_chat_partial, name='assistant_chat_partial'),
    path('profile/switch/', views.switch_profile, name='switch_profile'),
    path('profile/create/', views.create_profile, name='create_profile'),
    path('profile/export/', views.export_profile, name='export_profile'),
    path('profile/import/', views.import_profile, name='import_profile'),
    path('language/switch/', views.switch_language, name='switch_language'),
]
