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
]
