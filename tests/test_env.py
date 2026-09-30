import os

def test_required_packages_imported():
    import requests
    import pandas
    import streamlit
    import plotly
    import dotenv
    assert True

def test_env_api_key_loaded():
    key = os.environ.get("DATA_GO_KR_API_KEY")
    assert key is not None
    assert len(key) > 20
