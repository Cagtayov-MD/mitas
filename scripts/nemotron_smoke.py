import sys
import time
from PIL import Image
import os

print("Starting NVIDIA Nemotron OCR v2 smoke test...")

try:
    from nemotron_ocr.inference.pipeline_v2 import NemotronOCRV2
except ImportError as e:
    print("Error importing NemotronOCRV2:", e)
    print("Please ensure you have installed the nemotron_ocr package from the huggingface repo.")
    sys.exit(1)

print("Initializing NemotronOCRV2...")
try:
    ocr = NemotronOCRV2()
except Exception as e:
    print(f"Error initializing model: {e}")
    sys.exit(1)

print("Testing inference with dummy image...")
image_path = "dummy_nemotron.png"
Image.new('RGB', (500, 500), color='white').save(image_path)

start = time.time()
try:
    predictions = ocr(image_path)
    end = time.time()
    
    print(f"Inference completed in {end - start:.2f} seconds.")
    for pred in predictions:
        print(f" - Text: '{pred['text']}', Confidence: {pred['confidence']:.2f}")
except Exception as e:
    print(f"Inference failed: {e}")
    if os.path.exists(image_path):
        os.remove(image_path)
    sys.exit(1)

if os.path.exists(image_path):
    os.remove(image_path)

print("Smoke test PASSED!")
