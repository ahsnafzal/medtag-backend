import os
import sys
import json
import urllib.parse
import PIL.Image
import google.generativeai as genai
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from medtag.models import UserDocument 

# ✅ PDF read karne ke liye local library
try:
    import PyPDF2
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# Google Gemini API Key 
# ⚠️ WARNING: Agar yahan hardcoded key block ho chuki hai, toh aapko Google AI Studio se nayi key laani hogi
API_KEY = getattr(settings, 'GEMINI_API_KEY', '')
genai.configure(api_key=API_KEY)

# ✅ SMART DYNAMIC AUTO-FALLBACK FUNCTION
# Yeh function direct Google se list mangwayega taake 404 error kabhi na aaye
def generate_with_fallback(contents, is_vision=False):
    try:
        # Step 1: Direct Google se poochain ke is API key par konsay models allowed hain
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        raise Exception(f"API Key Error: Could not connect to Google API. Check your internet or API Key. Details: {e}")

    if not available_models:
        raise Exception("API KEY BLOCKED: Google is not allowing ANY models on this API Key. You MUST generate a new API key from aistudio.google.com and update it in your code.")

    print(f"\nGoogle authorized models for this key: {available_models}")

    # Step 2: Un allowed models mein se sabse best model automatically pick karein
    best_models_preference = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro-vision', 'models/gemini-pro']
    
    selected_model = None
    for pref in best_models_preference:
        if pref in available_models:
            selected_model = pref
            break
            
    # Agar humari pasand ka model na milay, toh API key par mojood pehla model utha lein
    if not selected_model:
        selected_model = available_models[0]

    model_name_clean = selected_model.replace('models/', '')
    print(f"Dynamically picked model: {model_name_clean}")
    
    # Step 3: Model ko data bhejein
    model = genai.GenerativeModel(model_name_clean)
    return model.generate_content(contents)


class AISymptomMatchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        symptoms = request.data.get('symptoms', '')
        
        if not symptoms:
            return Response({"error": "Symptoms are required."}, status=400)
        
        prompt = f"""
        Act as a medical routing AI. The patient says: "{symptoms}"
        Based strictly on these symptoms, choose EXACTLY ONE of these specialties: 
        Cardiologist, Dermatologist, Endocrinologist, Gastroenterologist, General Physician, Gynecologist, Neurologist, Oncologist, Ophthalmologist, Orthopedic, Pediatrician, Psychiatrist, Pulmonologist, Radiologist, Surgeon, Urologist.
        
        Return ONLY a JSON response in this exact format:
        {{"specialty": "Neurologist", "explanation": "A short 1-line reason why."}}
        """
        
        try:
            # ✅ Use Smart Fallback
            response = generate_with_fallback(prompt, is_vision=False)
            
            cleaned_text = response.text.replace('```json', '').replace('```', '').strip()
            data = json.loads(cleaned_text)
            return Response(data)
            
        except Exception as e:
            print(f"AI Error: {str(e)}")
            return Response({
                "specialty": "General Physician", 
                "explanation": "Please consult a General Physician for an initial assessment."
            })


class AIReportSummarizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_id = request.data.get('file_id')
        file_url = request.data.get('file_url') 
        
        if not file_id and not file_url:
            return Response({"error": "File ID or URL is required."}, status=400)
            
        file_path = None
        
        try:
            if file_id:
                file_obj = UserDocument.objects.get(id=file_id)
                file_path = file_obj.document.path 
        except UserDocument.DoesNotExist:
            pass
        
        if not file_path and file_url:
            try:
                parsed_url = urllib.parse.urlparse(file_url)
                path_only = parsed_url.path
                if '/media/' in path_only:
                    relative_path = path_only.split('/media/')[-1]
                    file_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            except Exception:
                pass

        if not file_path or not os.path.exists(file_path):
            return Response({"error": "Physical file not found on the server."}, status=400)

        try:
            # 1. Agar report Image hai (JPG/PNG)
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                print("\nProcessing as image...")
                img = PIL.Image.open(file_path)
                
                # ✅ Use Smart Fallback for Images
                response = generate_with_fallback([
                    "Please act as a professional medical assistant. Analyze this medical report and give me a 3-bullet point simple summary in plain English.", 
                    img
                ], is_vision=True)
                
                return Response({"summary": response.text})
            
            # 2. Agar report PDF hai
            elif file_path.lower().endswith('.pdf'):
                print("\nProcessing as PDF locally...")
                
                if not HAS_PYPDF2:
                    return Response({"error": "Backend needs PyPDF2. Please run: pip install PyPDF2"}, status=400)
                
                # PDF Text Extraction Bypass
                extracted_text = ""
                with open(file_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text = page.extract_text()
                        if text:
                            extracted_text += text + "\n"
                            
                if not extracted_text.strip():
                    return Response({"error": "Could not extract text from this PDF. It might be a scanned image."}, status=400)

                prompt = f"Please act as a professional medical assistant. Analyze this medical report text and give me a 3-bullet point simple summary in plain English.\n\nReport Content:\n{extracted_text[:15000]}"
                
                # ✅ Use Smart Fallback for Text
                response = generate_with_fallback(prompt, is_vision=False)
                
                return Response({"summary": response.text})
                
            else:
                return Response({"error": "Only Image and PDF files are supported."}, status=400)
            
        except Exception as e:
            error_str = str(e)
            print(f"\nFile AI error: {error_str}")
            return Response({"error": f"AI Engine Error: {error_str}"}, status=500)