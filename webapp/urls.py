from django.urls import path
from .views import PredictionResultView, home, PredictionFormView, PredictionListView, submit_rating
from . import views

urlpatterns = [
    path("", home, name="home"),
    path("prediction_form/", PredictionFormView.as_view(), name="prediction_form"),
    path("predictions/", PredictionListView.as_view(), name="prediction_list"),
    path('result/<int:pk>/', PredictionResultView.as_view(), name='prediction_result'),
    path('rate/<int:pk>/', submit_rating, name='submit_rating'),
    path('upload/', views.upload_file, name='upload')
]


