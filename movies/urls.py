from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('grid/', views.movie_grid_partial, name='movie_grid_partial'),
    path('search/', views.search_live_partial, name='search_live_partial'),
    path('movie/<int:movie_id>/', views.movie_modal_partial, name='movie_modal_partial'),
    path('roulette/', views.roulette, name='roulette'),
    path('watchlist/', views.watchlist, name='watchlist'),
    path('watchlist/toggle/<int:movie_id>/', views.toggle_watchlist, name='toggle_watchlist'),
    path('rate/<int:movie_id>/', views.rate_movie, name='rate_movie'),
    path('discover/', views.discover, name='discover'),
    path('taste-dna/', views.taste_dna, name='taste_dna'),
    path('compare/', views.compare, name='compare'),
    path('assistant/', views.assistant, name='assistant'),
    path('assistant/chat/', views.assistant_chat_partial, name='assistant_chat_partial'),
    path('profile/switch/', views.switch_profile, name='switch_profile'),
    path('profile/create/', views.create_profile, name='create_profile'),
    path('language/switch/', views.switch_language, name='switch_language'),
]
