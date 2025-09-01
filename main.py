import os

def main(req, res):
    print("--- MINIMAL TEST STARTED ---")
    
    test_var = os.environ.get("TEST_VARIABLE", "Variable not found!")
    print(f"The value of TEST_VARIABLE is: {test_var}")
    
    print("--- MINIMAL TEST FINISHED ---")
    
    return res.json({'status': 'ok', 'message': 'Minimal test executed successfully.'})
