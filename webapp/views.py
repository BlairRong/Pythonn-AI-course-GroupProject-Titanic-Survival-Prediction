import pandas as pd
import pickle
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import FormView, ListView, DetailView
from django.urls import reverse_lazy
from django.conf import settings
from .forms import PredictionForm
from .models import PredictionRecord
from pathlib import Path
from django.contrib import messages

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from azure.storage.blob import BlobServiceClient

from .cosmos_service import CosmosService
from datetime import datetime, timezone

# To train the model-  python -m ML.model_training.train
# Set up logging to catch errors in the console/logs
logger = logging.getLogger(__name__)
# This loads our ML artifacts once at server startup. Efficient and clean.
MODEL_PATH = Path(settings.BASE_DIR) / "ML" / "model_training" / "artifacts" / "model.pkl"
PREPROCESSOR_PATH = Path(settings.BASE_DIR) / "ML" / "model_training" / "artifacts" / "scaler.pkl"
try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    with open(PREPROCESSOR_PATH, "rb") as f:
        preprocessor = pickle.load(f)

except (FileNotFoundError, pickle.UnpicklingError, Exception) as e:
    logger.error(f"Critical Error: Failed to load ML artifacts. {e}")
    model = None
    preprocessor = None

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
        # Check if model is actually available
        if model is None or preprocessor is None:
            messages.error(self.request, "The prediction service is currently unavailable. Please contact the admin.")
            return self.form_invalid(form)
        try:
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
            
            #=====after prediction successfull and save into Azure Consmos DB======
            #在 PredictionFormView 的 form_valid 方法中，在预测成功并保存到 SQLite 数据库后，再调用 Cosmos DB 服务写入一条记录。
            passenger_name = self.request.session.get("last_passenger_name", "Unknown")
            try:
                cosmos = CosmosService()
                cosmos_item = {
                    "id": f"pred_{prediction.pk}",           # 唯一ID
                    "userId": self.request.user.username if self.request.user.is_authenticated else "anonymous",
                    "passengerName": passenger_name,          # 从 session 获取
                    "prediction": "Survived" if prediction.survived_prediction else "Perished",
                    "probability": prediction.probability,
                    "inputData": {
                        "pclass": prediction.pclass,
                        "sex": prediction.sex,
                        "age": prediction.age,
                        "sibsp": prediction.sibsp,
                        "parch": prediction.parch,
                        "fare": prediction.fare,
                        "embarked": prediction.embarked,
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                cosmos.create_item(cosmos_item)
            except Exception as e:
                logger.error(f"Cosmos DB error: {e}")
        # ========================================
            
            
            return redirect("prediction_result", pk=prediction.pk)
        
        except ValueError as ve:
            logger.error(f"Data transformation error: {ve}")
            messages.error(self.request, "There was an issue processing the data format.")
        except Exception as e:
            logger.error(f"Unexpected prediction error: {e}")
            messages.error(self.request, "An unexpected error occurred during prediction.")
        
        return self.form_invalid(form)


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


#upload the file to storage - Azure Blob Storage
def upload_file(request):
    message = None
    if request.method == 'POST' and request.FILES.get('myfile'):
        uploaded_file = request.FILES['myfile']
        
        # use Azure Blob Storage save file
        blob_service_client = BlobServiceClient.from_connection_string(settings.AZURE_STORAGE_CONN_STR)
        container_name = "django-uploads"
        # Ensure the container exists (create it first, but assume it has already been created manually).
        try:
            blob_service_client.create_container(container_name)
        except:
            pass  # The container already exists.
        
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=uploaded_file.name)
        blob_client.upload_blob(uploaded_file.read(), overwrite=True)
        message = f"file {uploaded_file.name} uploaded to Azure Storage"
    
    return render(request, 'webapp/upload.html', {'message': message})


#Azure Comsmos Architecture Design.
#Create and display a view that reads data from Cosmos DB.创建读取 Cosmos DB 数据并显示的视图
def cosmos_history(request):
    cosmos = CosmosService()
    try:
        # Retrieve the latest 10 records, sorted in descending order of time (if document has a timestamp field).查询最新的 10 条记录，按时间倒序（如果文档有 timestamp 字段）
        items = cosmos.get_items(query="SELECT TOP 10 * FROM c ORDER BY c.timestamp DESC")
    except Exception as e:
        items = []
        logger.error(f"Failed to fetch from Cosmos DB: {e}")
    return render(request, 'webapp/cosmos_history.html', {'items': items})
    
    if not items:
        messages.warning(request, "Cosmos DB service is currently unavailable. Showing no data.")