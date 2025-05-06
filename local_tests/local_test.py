from test_main import reset_sold_out_items
from flask import Request
import types

class MockRequest:
    def __init__(self, config_name):
        self.args = {"config": config_name}

if __name__ == "__main__":
    mock_request = MockRequest("test.json")
    response, status_code = reset_sold_out_items(mock_request)
    print("Status Code:", status_code)
    print("Response:\n", response)
