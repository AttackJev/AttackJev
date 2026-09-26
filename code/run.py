import os
def credential():
    value=os.environ.get("TYPESAFE_API_KEY")
    if not value: raise RuntimeError("Set TYPESAFE_API_KEY in your environment")
    return value
