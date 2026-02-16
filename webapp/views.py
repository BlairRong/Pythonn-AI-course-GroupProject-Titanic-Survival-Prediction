import pandas as pd
import pickle
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import FormView, ListView, DetailView
from django.urls import reverse_lazy
from django.conf import settings
from .forms import PredictionForm
from .models import PredictionRecord
from pathlib import Path
from django.contrib import messages

# To train the model-  python -m ML.model_training.train

# This loads our ML artifacts once at server startup. Efficient and clean.
MODEL_PATH = Path(settings.BASE_DIR) / "ML" / "model_training" / "artifacts" / "model.pkl"
PREPROCESSOR_PATH = Path(settings.BASE_DIR) / "ML" / "model_training" / "artifacts" / "scaler.pkl"

with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

with open(PREPROCESSOR_PATH, "rb") as f:
    preprocessor = pickle.load(f)


def home(request):
    return render(request, "webapp/home.html", {"title": "home"})


class PredictionFormView(FormView):
    """
    View for the prediction form with SibSp dropdown
    """

    template_name = "webapp/prediction_form.html"
    form_class = PredictionForm
    success_url = reverse_lazy("prediction_list")

    def form_valid(self, form):
        # Save the form data to database
        prediction = form.save(commit=False)

        # Get name from form (which isn't in the model)
        passenger_name = form.cleaned_data.get("name")

        # Store it in the session
        self.request.session["last_passenger_name"] = passenger_name

        sex_mapping = {"male": 0, "female": 1}
        sex_numeric = sex_mapping.get(prediction.sex, 0)

        embarked_mapping = {"S": 0, "C": 1, "Q": 2}
        embarked_numeric = embarked_mapping.get(prediction.embarked, 0)
        # Local variables for Feature Engineering
        age = float(prediction.age)
        sibsp = int(prediction.sibsp)
        parch = int(prediction.parch)

        # Feature Engineerd features

        # FamilySize = SibSp + Parch + 1 (the +1 accounts for the passenger themselves)
        family_size = sibsp + parch + 1

        # Determine AgeGroup label
        if age <= 2:
            age_group_label = "infant"
        elif age <= 12:
            age_group_label = "child"
        elif age <= 19:
            age_group_label = "teen"
        elif age <= 29:
            age_group_label = "young_adult"
        elif age <= 59:
            age_group_label = "adult"
        else:
            age_group_label = "senior"

        # Map to Numeric (Matches training logic)
        group_map = {"infant": 0, "child": 1, "teen": 2, "young_adult": 3, "adult": 4, "senior": 5}
        age_group_numeric = group_map.get(age_group_label, 3)

        # Convert form data into a DataFrame for the ML pipeline
        data = {
            "Pclass": int(prediction.pclass),
            "Sex": sex_numeric,
            "Age": int(age),
            "SibSp": sibsp,
            "Parch": parch,
            "Fare": float(prediction.fare) if prediction.fare is not None else 0.0,
            "Embarked": embarked_numeric,
            "FamilySize": family_size,
            "AgeGroup": age_group_numeric,
        }

        df = pd.DataFrame([data])

        # Preprocess using your saved pipeline
        X_processed = preprocessor.transform(df)

        # Predict
        pred_value = int(model.predict(X_processed)[0])
        pred_proba = float(model.predict_proba(X_processed)[0][1]) * 100

        # Save results into the Django model
        prediction.survived_prediction = bool(pred_value)
        prediction.probability = round(pred_proba, 2)

        prediction.save()
        return redirect("prediction_result", pk=prediction.pk)


def submit_rating(request, pk):
    if request.method == "POST":
        prediction = get_object_or_404(PredictionRecord, pk=pk)
        rating = request.POST.get("rating")
        if rating:
            prediction.rating = int(rating)
            prediction.save()
            messages.success(request, "Thank you for rating! ⭐")

    return redirect("prediction_result", pk=pk)


class PredictionResultView(DetailView):
    model = PredictionRecord
    template_name = "webapp/results.html"
    context_object_name = "prediction"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["passenger_name"] = self.request.session.get("last_passenger_name", "Unknown")
        return context


class PredictionListView(ListView):
    model = PredictionRecord
    template_name = "webapp/prediction_list.html"
    context_object_name = "predictions"
    ordering = ["-created_at"]  # newest first
    paginate_by = 20  # optional
