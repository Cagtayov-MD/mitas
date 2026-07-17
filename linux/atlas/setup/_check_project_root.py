import sys
sys.path.insert(0, "src")
from atlas.config.paths import PROJECT_ROOT
print("PROJECT_ROOT:", PROJECT_ROOT)
assert str(PROJECT_ROOT) == "/opt/atlas", "PROJECT_ROOT YANLIS!"
print("KAPI_C_PROJECT_ROOT_OK")
